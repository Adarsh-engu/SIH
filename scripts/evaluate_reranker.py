import json
import time
import torch
import torch.nn.functional as F
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from matcher_service import matcher_service
from llm_extractor import llm_rerank_candidates

def evaluate():
    with open('data/labeled_reports.json') as f:
        all_reports = json.load(f)
        
    with open('data/train_test_split.json') as f:
        splits = json.load(f)
        test_node_ids = set(splits.get('test_node_ids', []))
        
    test_reports = [r for r in all_reports if r['true_node_id'] in test_node_ids]
    # Limit to 100 max
    test_reports = test_reports[:100]
    
    print(f"Evaluating on {len(test_reports)} test reports...")
    
    gnn_correct_total = 0
    gnn_correct_valid = 0
    llm_correct = 0
    llm_failed = 0
    
    fixed_example = None
    
    for idx, r in enumerate(test_reports):
        true_id = r['true_node_id']
        phrase = r['phrase']
        extracted = {"activity_phrase": r['phrase']} # mock basic extraction for testing
        
        with torch.no_grad():
            p_raw = matcher_service.encode([phrase])
            p_emb = F.normalize(matcher_service.proj_text(p_raw), dim=1)
            sims = (p_emb @ matcher_service.node_embeddings.t()).squeeze(0)
            
        sims_list = sims.tolist()
        for i, nid in enumerate(matcher_service.node_ids):
            if matcher_service.nodes_by_id[nid].get("level") != 5:
                sims_list[i] = -1e9
                
        sims_tensor = torch.tensor(sims_list)
        top_20 = torch.topk(sims_tensor, 20)
        
        candidates = []
        for score, i in zip(top_20.values.tolist(), top_20.indices.tolist()):
            nid = matcher_service.node_ids[i]
            n = matcher_service.nodes_by_id[nid]
            candidates.append({
                "id": nid,
                "name": n["name"],
                "discipline": n["discipline"],
                "unit": n.get("unit"),
                "base_score": score
            })
            
        gnn_top1_id = candidates[0]['id']
        if gnn_top1_id == true_id:
            gnn_correct_total += 1
            
        # Backoff logic
        max_retries = 3
        llm_result = None
        for attempt in range(max_retries):
            try:
                llm_result = llm_rerank_candidates(phrase, extracted, candidates)
                break
            except Exception as e:
                err_msg = str(e)
                if '429' in err_msg or '503' in err_msg or 'quota' in err_msg.lower() or 'exhausted' in err_msg.lower() or 'unavailable' in err_msg.lower():
                    wait_time = 5 * (attempt + 1)
                    print(f"Rate limited or unavailable. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"LLM API Error: {err_msg}")
                    break
        
        if not llm_result or not llm_result.get('node_id'):
            llm_failed += 1
        else:
            selected_id = llm_result['node_id']
            if gnn_top1_id == true_id:
                gnn_correct_valid += 1
            if selected_id == true_id:
                llm_correct += 1
                if gnn_top1_id != true_id and not fixed_example:
                    fixed_example = (phrase, gnn_top1_id, true_id, llm_result.get('reasoning'))
        
        # Avoid hitting free tier limits too fast
        time.sleep(1)
        if (idx+1) % 10 == 0:
            print(f"Processed {idx+1}/{len(test_reports)}")
            
    print("=" * 40)
    print("EVALUATION RESULTS")
    print(f"Total Test Cases: {len(test_reports)}")
    print(f"GNN Top-1 (All): {gnn_correct_total} ({(gnn_correct_total/len(test_reports))*100:.1f}%)")
    
    valid_llm_calls = len(test_reports) - llm_failed
    print(f"LLM API Failures/Timeouts: {llm_failed}")
    if valid_llm_calls > 0:
        print(f"--- Apples-to-Apples (Valid Calls Only) ---")
        print(f"GNN Top-1 Correct: {gnn_correct_valid} ({(gnn_correct_valid/valid_llm_calls)*100:.1f}%)")
        print(f"LLM Top-1 Correct: {llm_correct} ({(llm_correct/valid_llm_calls)*100:.1f}%)")
    
    if fixed_example:
        print("\n--- Example of LLM correcting GNN ---")
        print(f"Phrase: {fixed_example[0]}")
        print(f"GNN Guessed: {fixed_example[1]}")
        print(f"True Node: {fixed_example[2]}")
        print(f"LLM Reasoning: {fixed_example[3]}")
        
if __name__ == '__main__':
    evaluate()
