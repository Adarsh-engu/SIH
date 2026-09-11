import os
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    logger.warning("google-genai package is not installed. LLM extraction will fail.")

API_KEYS = []
primary_key = os.environ.get("GEMINI_API_KEY_PRIMARY") or os.environ.get("GEMINI_API_KEY")
if primary_key:
    API_KEYS.append(("PRIMARY", primary_key))

for k, v in sorted(os.environ.items()):
    if k.startswith("GEMINI_API_KEY_BACKUP_") and v:
        API_KEYS.append((k, v))

if not API_KEYS:
    logger.error("CRITICAL: No GEMINI_API_KEY found in environment! LLM extraction will fallback to mock.")
else:
    logger.info(f"Loaded {len(API_KEYS)} GEMINI API keys successfully.")

def _generate_with_fallback(model_name: str, prompt: str) -> str:
    """Helper to try generating content with fallback API keys on 429 or key-invalid errors."""
    if not API_KEYS or not genai:
        raise Exception("No API keys or genai client available.")
        
    last_exception = None
    for key_name, api_key in API_KEYS:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            logger.info(f"LLM call served successfully by key: {key_name}")
            return response.text
        except Exception as e:
            err_str = str(e)
            # Rotate on quota exhaustion (429) OR invalid/expired key (400 INVALID_ARGUMENT)
            should_rotate = (
                "429" in err_str or
                "RESOURCE_EXHAUSTED" in err_str or
                "quota" in err_str.lower() or
                "INVALID_ARGUMENT" in err_str or
                "API_KEY_INVALID" in err_str or
                "API key not valid" in err_str
            )
            if should_rotate:
                logger.warning(f"Key {key_name} failed (quota or invalid key). Rotating to next key if available.")
                last_exception = e
                continue
            else:
                logger.error(f"Key {key_name} encountered unexpected error: {err_str}")
                raise e  # Only stop rotation on truly unexpected errors (network, etc.)
                
    # If we get here, all keys were exhausted or invalid
    logger.error("All available API keys failed (quota exhausted or keys invalid).")
    raise last_exception or Exception("All API keys failed.")


def extract_structured_event(raw_phrase: str) -> Dict[str, Any]:
    """
    Takes a raw, messy field report and extracts structured data.
    If no GEMINI_API_KEY is found, uses a deterministic fallback for demo safety.
    """
    if API_KEYS and genai:
        try:
            prompt = f"""
            You are an assistant for Oil India Limited (OIL) infrastructure projects (well pads, flowlines, GGS).
            Extract the core activity from the following field report phrase.
            Return a JSON object with:
            - "activity_phrase": A cleaned, generic version of the core action being performed.
            - "discipline": One of [Civil, Piping, Electrical, Instrumentation, HSE]. Guess if obvious.
            - "action": A very short 1-2 word summary of the action (e.g. "Installation", "Tie-in", "Drill").
            - "activity_id": The exact activity ID if mentioned (e.g. "WELD-1042", "Ref: WELD-1042"). Null if not.
            - "quantity": Numeric quantity mentioned. Null if not.
            - "unit": Unit of quantity (e.g. "km", "joints", "m3"). Null if not.
            
            Field Report: "{raw_phrase}"
            """
            
            response_text = _generate_with_fallback('gemini-3.5-flash-lite', prompt)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"LLM Extraction failed: {e}. Falling back to mock extraction.")
    else:
        logger.warning("No GEMINI_API_KEY or google-genai package found. Using mock extractor.")
    
    # Fallback / Mock Extraction
    lower_phrase = raw_phrase.lower()
    
    discipline_keywords = {
        "Piping": ["pipe", "flowline", "tie-in"],
        "HSE": ["drill", "audit", "safety"],
        "Civil": ["civil", "tank", "foundation"],
        "Electrical": ["cable", "termination", "wire"],
        "Instrumentation": ["instrument", "calibration"]
    }
    
    discipline = "Multi"
    action = "Activity"
    
    for d, keywords in discipline_keywords.items():
        if any(kw in lower_phrase for kw in keywords):
            discipline = d
            action = f"{d} Work" if d != "HSE" else "HSE Action"
            break
        
    import re
    
    # Try to find a Ref: ID
    activity_id = None
    id_match = re.search(r"Ref:\s*([A-Z]+-\d+)", raw_phrase, re.IGNORECASE)
    if id_match:
        activity_id = id_match.group(1).upper()
        
    # Try to find quantity + unit
    quantity = None
    unit = None
    qty_match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z-]+)", raw_phrase)
    if qty_match:
        quantity = float(qty_match.group(1))
        unit = qty_match.group(2)
        
    cleaned_phrase = raw_phrase.replace("Sir, ", "").replace("FYI - ", "").replace("Site note: ", "").strip()
    cleaned_phrase = re.sub(r"\(Ref:.*?\)", "", cleaned_phrase).strip()
    
    return {
        "activity_phrase": cleaned_phrase,
        "discipline": discipline,
        "action": action,
        "activity_id": activity_id,
        "quantity": quantity,
        "unit": unit
    }

_rerank_cache = {}

def llm_rerank_candidates(raw_phrase: str, extracted_data: Dict[str, Any], candidates: list) -> Dict[str, Any]:
    """
    Passes the top-20 GNN candidates to Gemini to contextually select the correct node.
    Returns {"node_id": str, "reasoning": str, "llm_certainty": "high"|"medium"|"low"}
    """
    if not (API_KEYS and genai):
        logger.error("Reranker failed: No GEMINI API keys or genai client available.")
        return None

    model_name = 'gemini-3.5-flash-lite'
    cache_key = f"{model_name}_{raw_phrase}_" + ",".join([c["id"] for c in candidates])
    if cache_key in _rerank_cache:
        logger.info("Using cached LLM rerank result.")
        return _rerank_cache[cache_key]

    try:
        candidates_str = ""
        for i, c in enumerate(candidates):
            candidates_str += f"Rank {i+1}: ID={c['id']}, Name='{c['name']}', Discipline='{c['discipline']}', Unit='{c['unit']}'\n"
            
        prompt = f"""
        You are a scheduling assistant for Oil India Limited. 
        Your task is to select the exact activity node from a candidate list that best matches a field report.
        
        Field Report: "{raw_phrase}"
        Extracted Info: {json.dumps(extracted_data)}
        
        Candidate Nodes (ranked by semantic similarity):
        {candidates_str}
        
        Reason step-by-step to choose the best matching node based on the context. If multiple are similar, look at the discipline, action, and unit of measure.
        If no node seems correct, pick the least wrong one and set llm_certainty to "low".
        
        Return ONLY a valid JSON object matching this schema:
        {{
            "node_id": "The exact ID of the best candidate (e.g. A00123)",
            "reasoning": "A short 1-2 sentence explanation of why this node was chosen",
            "llm_certainty": "high", "medium", or "low"
        }}
        """
        
        response_text = _generate_with_fallback(model_name, prompt)
        result = json.loads(response_text)
        _rerank_cache[cache_key] = result
        return result
    except Exception as e:
        logger.error(f"Reranker errored: {str(e)}")
        return None
