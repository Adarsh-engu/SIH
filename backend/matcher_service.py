import os
import json
import torch
import torch.nn as nn
import torch.nn.functional as F

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
CONFIDENCE_THRESHOLD = 0.35

class MatcherService:
    def __init__(self):
        print("Loading matcher model and data...")
        ckpt = torch.load(f"{DATA_DIR}/setu_matcher.pt", weights_only=False)
        self.node_ids = ckpt["node_ids"]
        self.node_embeddings = ckpt["node_embeddings"]
        
        with open(f"{DATA_DIR}/schedule_graph.json") as f:
            self.schedule = json.load(f)
        self.nodes_by_id = {n["id"]: n for n in self.schedule["nodes"]}
        
        try:
            from sentence_transformers import SentenceTransformer
            _st = SentenceTransformer("all-MiniLM-L6-v2")
            def encode(texts):
                with torch.no_grad():
                    return torch.tensor(_st.encode(texts, show_progress_bar=False))
            self.encode = encode
        except Exception:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.decomposition import TruncatedSVD
            with open(f"{DATA_DIR}/labeled_reports.json") as f:
                reports = json.load(f)
            node_texts = [self.nodes_by_id[nid]["name"] for nid in self.node_ids]
            corpus = node_texts + [r["phrase"] for r in reports]
            vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2)).fit(corpus)
            svd = TruncatedSVD(n_components=128, random_state=0).fit(vec.transform(corpus))
            def encode(texts):
                return torch.tensor(svd.transform(vec.transform(texts)), dtype=torch.float32)
            self.encode = encode

        self.proj_text = nn.Linear(ckpt["in_dim"] - len(ckpt["disciplines"]), self.node_embeddings.shape[1])
        state = ckpt["model_state"]
        self.proj_text.weight.data = state["proj_text.weight"]
        self.proj_text.bias.data = state["proj_text.bias"]

    def find_match(self, phrase, extracted_data=None, top_k=5):
        extracted_data = extracted_data or {}
        
        # Explicit ID Check
        explicit_node = None
        if extracted_data.get("activity_id"):
            for nid, node in self.nodes_by_id.items():
                if node.get("level") == 5 and node.get("activity_id") == extracted_data["activity_id"]:
                    explicit_node = node
                    break
        
        if explicit_node:
            reasoning = {
                "semantic_score": 1.0,
                "id_match": True,
                "discipline_match": True,
                "unit_match": True,
                "qty_match": True,
                "llm_reasoning": "Explicit Activity ID match. Bypassed GNN."
            }
            return {
                "matched_node_id": explicit_node["id"],
                "matched_node_name": explicit_node["name"],
                "discipline": explicit_node["discipline"],
                "confidence": 1.0,
                "status": "auto-updated",
                "top_k": [{"node_id": explicit_node["id"], "activity_name": explicit_node["name"], "discipline": explicit_node["discipline"], "confidence": 1.0, "reasoning": reasoning}],
                "reasoning": reasoning
            }

        with torch.no_grad():
            p_raw = self.encode([phrase])
            p_emb = F.normalize(self.proj_text(p_raw), dim=1)
            sims = (p_emb @ self.node_embeddings.t()).squeeze(0)
            
        sims_list = sims.tolist()
        
        for i, nid in enumerate(self.node_ids):
            if self.nodes_by_id[nid].get("level") != 5:
                sims_list[i] = -1e9
                
        sims_tensor = torch.tensor(sims_list)
        top_20 = torch.topk(sims_tensor, 20)
        
        candidates = []
        for score, idx in zip(top_20.values.tolist(), top_20.indices.tolist()):
            nid = self.node_ids[idx]
            n = self.nodes_by_id[nid]
            candidates.append({
                "id": nid,
                "name": n["name"],
                "discipline": n["discipline"],
                "unit": n.get("unit"),
                "base_score": score
            })
            
        from llm_extractor import llm_rerank_candidates
        llm_result = llm_rerank_candidates(phrase, extracted_data, candidates)
        
        gnn_top1_id = candidates[0]["id"]
        
        import logging
        logger = logging.getLogger(__name__)

        if not llm_result or not llm_result.get("node_id"):
            logger.error("Reranker failed. Falling back to GNN rank-1 with needs-review.")
            selected_id = gnn_top1_id
            status = "needs-review"
            llm_reason = "Fallback: LLM reranker failed."
        else:
            selected_id = llm_result["node_id"]
            if selected_id not in [c["id"] for c in candidates]:
                logger.error("Reranker returned invalid node ID. Falling back to GNN rank-1.")
                selected_id = gnn_top1_id
                status = "needs-review"
                llm_reason = "Fallback: LLM returned invalid node ID."
            else:
                logger.info(f"Reranker selected {selected_id} (GNN rank-1 was {gnn_top1_id})")
                certainty = llm_result.get("llm_certainty", "low").lower()
                if selected_id == gnn_top1_id and certainty == "high":
                    status = "auto-updated"
                else:
                    status = "needs-review"
                llm_reason = llm_result.get("reasoning", "")
                
        selected_node = self.nodes_by_id[selected_id]
        
        # Populate existing reasoning fields
        reasoning = {
            "semantic_score": round(sims_list[self.node_ids.index(selected_id)], 2),
            "id_match": False,
            "discipline_match": False,
            "unit_match": False,
            "qty_match": False,
            "llm_reasoning": llm_reason
        }
        
        top_k_out = []
        for c in candidates[:top_k]:
            top_k_out.append({
                "node_id": c["id"],
                "activity_name": c["name"],
                "discipline": c["discipline"],
                "confidence": round(c["base_score"], 4),
                "reasoning": {}
            })
            
        return {
            "matched_node_id": selected_id,
            "matched_node_name": selected_node["name"],
            "discipline": selected_node["discipline"],
            "confidence": 0.99 if status == "auto-updated" else 0.5,
            "status": status,
            "top_k": top_k_out,
            "reasoning": reasoning
        }

    def check_dependencies(self, matched_node_id, completed_node_ids):
        violations = []
        for edge in self.schedule.get("edges", []):
            if edge.get("type") == "predecessor" and edge.get("target") == matched_node_id:
                pred_id = edge.get("source")
                if pred_id not in completed_node_ids:
                    pred_name = self.nodes_by_id.get(pred_id, {}).get("name", "Unknown Activity")
                    violations.append({
                        "predecessor_id": pred_id,
                        "predecessor_name": pred_name,
                        "reason": f"Predecessor '{pred_name}' has not been confirmed complete."
                    })
        return {
            "is_consistent": len(violations) == 0,
            "violations": violations
        }

matcher_service = MatcherService()
