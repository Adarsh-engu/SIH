"""
match_phrase.py -- Inference/demo: given a NEW, messy supervisor phrase (never
seen in training), find the top-k matching L5 schedule activities + confidence.

This is the function your FastAPI backend calls on every incoming voice/text
report. Run it directly for a quick sanity check:

    python3 match_phrase.py "pipe erected near tank 12"
    python3 match_phrase.py "PPE audit done at height zone"

Confidence < CONFIDENCE_THRESHOLD -> route to "Needs Review" queue instead of
auto-updating the schedule (this is the audit-trail / flag-unmatched behavior
your problem statement explicitly requires).
"""
import sys
import json
import torch
import torch.nn.functional as F

DATA_DIR = "d:/Projects/Tel-Setu/data"
CONFIDENCE_THRESHOLD = 0.35  # tune this against your val set once real embeddings are in

ckpt = torch.load(f"{DATA_DIR}/setu_matcher.pt", weights_only=False)
node_ids = ckpt["node_ids"]
node_embeddings = ckpt["node_embeddings"]  # already graph-refined, precomputed

with open(f"{DATA_DIR}/schedule_graph.json") as f:
    schedule = json.load(f)
nodes_by_id = {n["id"]: n for n in schedule["nodes"]}

# Re-encode the query phrase with the SAME text encoder used at training time.
# (In production, load this once at server startup, not per-request.)
try:
    from sentence_transformers import SentenceTransformer
    _st = SentenceTransformer("all-MiniLM-L6-v2")
    def encode(texts):
        with torch.no_grad():
            return torch.tensor(_st.encode(texts, show_progress_bar=False))
except Exception:
    # matches the TF-IDF fallback path in train_gnn.py -- for a real deployment
    # you'd persist the fitted vectorizer/svd alongside the checkpoint instead
    # of refitting; this inline refit is only for this sandbox's demo run.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    with open(f"{DATA_DIR}/labeled_reports.json") as f:
        reports = json.load(f)
    node_texts = [nodes_by_id[nid]["name"] for nid in node_ids]
    corpus = node_texts + [r["phrase"] for r in reports]
    vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2)).fit(corpus)
    svd = TruncatedSVD(n_components=128, random_state=0).fit(vec.transform(corpus))
    def encode(texts):
        return torch.tensor(svd.transform(vec.transform(texts)), dtype=torch.float32)

# Rebuild just the text-projection head from the checkpoint to map phrase
# embeddings into the same space as the (precomputed) node embeddings.
import torch.nn as nn
proj_text = nn.Linear(ckpt["in_dim"] - len(ckpt["disciplines"]), node_embeddings.shape[1])
state = ckpt["model_state"]
proj_text.weight.data = state["proj_text.weight"]
proj_text.bias.data = state["proj_text.bias"]


def match(phrase, top_k=5):
    with torch.no_grad():
        p_raw = encode([phrase])
        p_emb = F.normalize(proj_text(p_raw), dim=1)
        sims = (p_emb @ node_embeddings.t()).squeeze(0)
        probs = F.softmax(sims / 0.07, dim=0)
    top = torch.topk(probs, top_k)
    results = []
    for score, idx in zip(top.values.tolist(), top.indices.tolist()):
        nid = node_ids[idx]
        results.append({
            "node_id": nid,
            "activity_name": nodes_by_id[nid]["name"],
            "discipline": nodes_by_id[nid]["discipline"],
            "confidence": round(score, 4),
        })
    return results


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "pipe erected near tank 12"
    print(f"\nQuery phrase: \"{query}\"\n")
    results = match(query)
    top1_conf = results[0]["confidence"]
    status = "AUTO-UPDATE SCHEDULE" if top1_conf >= CONFIDENCE_THRESHOLD else "-> NEEDS REVIEW QUEUE"
    print(f"Decision: {status}  (top-1 confidence={top1_conf})\n")
    for r in results:
        print(f"  [{r['confidence']:.3f}] {r['node_id']}  ({r['discipline']:15s}) {r['activity_name']}")
