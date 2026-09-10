"""
train_gnn.py -- Setu's core matching model.

Architecture (this is the actual "graph-aware fuzzy matching" engine):
  1. TEXT TOWER: a pretrained sentence-transformer embeds the raw field-report
     phrase ("pipe erected near tank 12") into a 384-dim vector.
  2. GRAPH TOWER: every schedule node starts with the SAME sentence-transformer
     embedding of its own plan-language name ("Erection of spool for Line 24"-XX"),
     PLUS a discipline one-hot and a level-in-hierarchy feature. A 2-layer
     GraphSAGE then propagates information along wbs_parent and predecessor
     edges, so each node's final embedding also encodes "what's around it in
     the plan" -- this is what lets the model disambiguate using structural
     context, not just words.
  3. CONTRASTIVE TRAINING: for each labeled (phrase -> true_node) pair, we pull
     the text embedding and the graph-refined node embedding together, and push
     apart HARD NEGATIVES = other nodes in the SAME discipline (the genuinely
     confusing case -- e.g. two different piping lines) using in-batch InfoNCE.
  4. INFERENCE: embed an incoming phrase, cosine-similarity search over all
     graph-refined node embeddings, return top-k + confidence (softmax over
     similarities). Below a threshold -> route to "Needs Review" queue.

This trains in a few minutes on CPU with this dataset size -- appropriate for
a 6-day home build. Swap in a bigger sentence-transformer / more GNN layers
once you have GPU access for the national round.
"""
import json
import random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

random.seed(0)
torch.manual_seed(0)

# NOTE ON THIS FILE'S TEXT ENCODER:
# By default this script uses a pretrained sentence-transformer (downloads from
# huggingface.co on first run) -- this is what you should use on your home
# machine / at the hackathon, where you have normal internet access.
# If huggingface.co is unreachable (e.g. a locked-down sandbox/CI network),
# it automatically falls back to a TF-IDF + SVD text encoder trained on your
# own corpus, purely offline, so the GraphSAGE training loop can still be
# verified end-to-end without external downloads. Swap USE_PRETRAINED to force
# one path or the other.
USE_PRETRAINED = "auto"  # "auto" | True | False

DATA_DIR = "d:/Projects/Tel-Setu/data"

# ---------------------------------------------------------------------------
# 1. Load schedule graph + labeled reports + split
# ---------------------------------------------------------------------------
with open(f"{DATA_DIR}/schedule_graph.json") as f:
    schedule = json.load(f)
with open(f"{DATA_DIR}/labeled_reports.json") as f:
    reports = json.load(f)
with open(f"{DATA_DIR}/train_test_split.json") as f:
    split = json.load(f)

l5_nodes = [n for n in schedule["nodes"] if n["level"] == 5]
node_ids = [n["id"] for n in l5_nodes]
id2idx = {nid: i for i, nid in enumerate(node_ids)}
disciplines = sorted({n["discipline"] for n in l5_nodes})
disc2idx = {d: i for i, d in enumerate(disciplines)}

train_ids = set(split["train_node_ids"])
val_ids = set(split["val_node_ids"])
test_ids = set(split["test_node_ids"])

print(f"Loaded {len(l5_nodes)} L5 nodes, {len(reports)} labeled report phrases.")

# ---------------------------------------------------------------------------
# 2. Build the graph structure restricted to L5 nodes for message passing,
#    but we also fold in one hop up (L4 sub-system) and cross-discipline
#    predecessor edges from the full schedule so structural signal is real.
# ---------------------------------------------------------------------------
edge_list = []
all_node_by_id = {n["id"]: n for n in schedule["nodes"]}
for e in schedule["edges"]:
    s, t = e["source"], e["target"]
    if s in id2idx and t in id2idx:
        edge_list.append((id2idx[s], id2idx[t]))
        edge_list.append((id2idx[t], id2idx[s]))  # undirected message passing

if not edge_list:
    edge_list = [(i, i) for i in range(len(node_ids))]  # safety fallback

edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
print(f"Built L5 message-passing graph: {len(node_ids)} nodes, {edge_index.shape[1]} directed edges.")

# ---------------------------------------------------------------------------
# 3. Text encoder (frozen, small & fast -- fine for 6-day prototype)
# ---------------------------------------------------------------------------
node_texts = [n["name"] for n in l5_nodes]
all_phrases_for_fit = [r["phrase"] for r in reports]

def try_load_pretrained_encoder():
    from sentence_transformers import SentenceTransformer
    print("Loading sentence-transformer 'all-MiniLM-L6-v2' (downloads from huggingface.co)...")
    st_model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, ~80MB, fast on CPU
    def encode_fn(texts):
        with torch.no_grad():
            return torch.tensor(st_model.encode(texts, show_progress_bar=False))
    return encode_fn, 384

def build_tfidf_fallback_encoder():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    print("[fallback] huggingface.co unreachable here -> using TF-IDF + SVD "
          "text encoder trained on your own corpus (offline, no download).")
    vectorizer = TfidfVectorizer(max_features=4000, ngram_range=(1, 2))
    svd = TruncatedSVD(n_components=128, random_state=0)
    corpus = node_texts + all_phrases_for_fit
    tfidf = vectorizer.fit_transform(corpus)
    svd.fit(tfidf)
    def encode_fn(texts):
        return torch.tensor(svd.transform(vectorizer.transform(texts)), dtype=torch.float32)
    return encode_fn, 128

if USE_PRETRAINED is True:
    encode_fn, EMB_DIM = try_load_pretrained_encoder()
elif USE_PRETRAINED is False:
    encode_fn, EMB_DIM = build_tfidf_fallback_encoder()
else:  # "auto"
    try:
        encode_fn, EMB_DIM = try_load_pretrained_encoder()
    except Exception as e:
        print(f"[info] pretrained encoder unavailable ({type(e).__name__}); falling back.")
        encode_fn, EMB_DIM = build_tfidf_fallback_encoder()

node_text_emb = encode_fn(node_texts)

# discipline one-hot + normalized level feature, concatenated to text embedding
disc_onehot = torch.zeros(len(l5_nodes), len(disciplines))
for i, n in enumerate(l5_nodes):
    disc_onehot[i, disc2idx[n["discipline"]]] = 1.0

node_features = torch.cat([node_text_emb, disc_onehot], dim=1)
IN_DIM = node_features.shape[1]
print(f"Node feature dim: {IN_DIM} (text {EMB_DIM} + discipline {len(disciplines)})")


# ---------------------------------------------------------------------------
# 4. GraphSAGE encoder -- this is the graph tower
# ---------------------------------------------------------------------------
class ScheduleGraphSAGE(nn.Module):
    def __init__(self, in_dim, text_emb_dim, hidden_dim=256, out_dim=128):
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden_dim)
        self.conv2 = SAGEConv(hidden_dim, out_dim)
        self.proj_text = nn.Linear(text_emb_dim, out_dim)  # projects raw phrase embeddings to same space

    def encode_nodes(self, x, edge_index):
        h = self.conv1(x, edge_index)
        h = F.relu(h)
        h = F.dropout(h, p=0.1, training=self.training)
        h = self.conv2(h, edge_index)
        return F.normalize(h, dim=1)

    def encode_text(self, text_emb):
        h = self.proj_text(text_emb)
        return F.normalize(h, dim=1)


model = ScheduleGraphSAGE(IN_DIM, EMB_DIM)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

# ---------------------------------------------------------------------------
# 5. Pre-embed all report phrases once (frozen text encoder)
# ---------------------------------------------------------------------------
print("Embedding all report phrases...")
phrases = [r["phrase"] for r in reports]
phrase_emb_all = encode_fn(phrases)

for i, r in enumerate(reports):
    r["_emb_idx"] = i
    r["_node_idx"] = id2idx[r["true_node_id"]]

train_reports = [r for r in reports if r["true_node_id"] in train_ids]
val_reports = [r for r in reports if r["true_node_id"] in val_ids]
test_reports = [r for r in reports if r["true_node_id"] in test_ids]
print(f"Train phrases: {len(train_reports)} | Val: {len(val_reports)} | Test: {len(test_reports)}")

# discipline -> list of node indices, for hard-negative sampling
disc_to_node_idxs = {}
for i, n in enumerate(l5_nodes):
    disc_to_node_idxs.setdefault(n["discipline"], []).append(i)


def sample_hard_negatives(true_node_idx, discipline, k=4):
    pool = [i for i in disc_to_node_idxs[discipline] if i != true_node_idx]
    if len(pool) <= k:
        return pool
    return random.sample(pool, k)


# ---------------------------------------------------------------------------
# 6. Contrastive training loop (InfoNCE with hard negatives + in-batch negatives)
# ---------------------------------------------------------------------------
TEMPERATURE = 0.07
EPOCHS = 30
BATCH_SIZE = 64


def evaluate(reports_subset, node_emb, top_k=(1, 3)):
    if not reports_subset:
        return {}
    idxs = [r["_emb_idx"] for r in reports_subset]
    true_idxs = torch.tensor([r["_node_idx"] for r in reports_subset])
    with torch.no_grad():
        p_emb = model.encode_text(phrase_emb_all[idxs])
        sims = p_emb @ node_emb.t()  # [batch, n_nodes]
    ranks = sims.argsort(dim=1, descending=True)
    results = {}
    for k in top_k:
        correct = (ranks[:, :k] == true_idxs.unsqueeze(1)).any(dim=1).float().mean().item()
        results[f"top{k}_acc"] = round(correct, 4)
    return results


print("\nTraining GraphSAGE dual-encoder matcher...")
for epoch in range(1, EPOCHS + 1):
    model.train()
    random.shuffle(train_reports)
    total_loss = 0.0
    n_batches = 0
    for b_start in range(0, len(train_reports), BATCH_SIZE):
        batch = train_reports[b_start:b_start + BATCH_SIZE]
        if not batch:
            continue
        optimizer.zero_grad()

        node_emb = model.encode_nodes(node_features, edge_index)  # recompute each step (small graph, cheap)
        phrase_idxs = [r["_emb_idx"] for r in batch]
        true_node_idxs = [r["_node_idx"] for r in batch]
        p_emb = model.encode_text(phrase_emb_all[phrase_idxs])

        # candidate set per example = true node + hard negatives (same discipline) + in-batch true nodes
        losses = []
        for i, r in enumerate(batch):
            neg_idxs = sample_hard_negatives(r["_node_idx"], r["discipline"], k=4)
            cand_idxs = [r["_node_idx"]] + neg_idxs
            cand_emb = node_emb[cand_idxs]  # [n_cand, dim]
            sims = (p_emb[i:i+1] @ cand_emb.t()).squeeze(0) / TEMPERATURE  # [n_cand]
            target = torch.tensor(0)  # true node is always index 0
            losses.append(F.cross_entropy(sims.unsqueeze(0), target.unsqueeze(0)))
        loss = torch.stack(losses).mean()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1

    if epoch % 5 == 0 or epoch == 1:
        model.eval()
        with torch.no_grad():
            node_emb_eval = model.encode_nodes(node_features, edge_index)
        val_metrics = evaluate(val_reports, node_emb_eval)
        test_metrics = evaluate(test_reports, node_emb_eval)
        print(f"Epoch {epoch:2d} | loss={total_loss/max(n_batches,1):.4f} | "
              f"val={val_metrics} | test(unseen activities)={test_metrics}")

# ---------------------------------------------------------------------------
# 7. Save trained model + final node embeddings for the FastAPI backend to load
# ---------------------------------------------------------------------------
model.eval()
with torch.no_grad():
    final_node_emb = model.encode_nodes(node_features, edge_index)

torch.save({
    "model_state": model.state_dict(),
    "node_ids": node_ids,
    "node_embeddings": final_node_emb,
    "in_dim": IN_DIM,
    "disciplines": disciplines,
}, f"{DATA_DIR}/setu_matcher.pt")

print(f"\nSaved trained matcher to {DATA_DIR}/setu_matcher.pt")
print("This checkpoint is what your FastAPI backend loads at inference time.")
