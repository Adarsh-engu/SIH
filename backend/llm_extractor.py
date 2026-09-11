import os
import json
import logging
import requests
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

OLLAMA_HOST  = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
TIMEOUT      = 25  # seconds — explicit timeout for all remote Ollama calls

# Module-level status dict — imported by main.py for /stats and frontend badge
OLLAMA_STATUS: Dict[str, Any] = {"available": False, "reason": "not checked yet"}


def _check_ollama_health() -> None:
    """
    Startup connectivity and model availability check.
    Fails loudly via CRITICAL log. Populates OLLAMA_STATUS in place.
    """
    # Step 1: Network reachability
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        msg = f"Cannot reach {OLLAMA_HOST}. Is Ollama running on that machine? ({e})"
        logger.critical(f"OLLAMA STARTUP FAIL — NETWORK ERROR: {msg}")
        OLLAMA_STATUS.update(available=False, reason=msg)
        return
    except requests.exceptions.Timeout:
        msg = f"Health check timed out connecting to {OLLAMA_HOST}."
        logger.critical(f"OLLAMA STARTUP FAIL — NETWORK ERROR: {msg}")
        OLLAMA_STATUS.update(available=False, reason=msg)
        return
    except Exception as e:
        msg = f"Unexpected error during health check: {e}"
        logger.critical(f"OLLAMA STARTUP FAIL — HEALTH CHECK: {msg}")
        OLLAMA_STATUS.update(available=False, reason=msg)
        return

    # Step 2: Model availability — distinct from network failure
    pulled_models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
    target_model  = OLLAMA_MODEL.split(":")[0]
    if target_model not in pulled_models:
        msg = f"Model '{OLLAMA_MODEL}' NOT pulled on {OLLAMA_HOST}. Available: {pulled_models}"
        logger.critical(f"OLLAMA STARTUP FAIL — MODEL MISSING: {msg}")
        OLLAMA_STATUS.update(available=False, reason=msg)
        return

    logger.info(f"Ollama health check PASSED — host={OLLAMA_HOST}, model={OLLAMA_MODEL}")
    OLLAMA_STATUS.update(available=True, reason="ok")


_check_ollama_health()


def _ollama_generate(prompt: str, schema: Dict) -> str:
    """
    Call Ollama /api/chat with structured JSON output.

    Strategy:
      Attempt 1 — JSON schema format (Ollama v0.5+, most reliable)
      Attempt 2 — generic format:"json" + strict prompt (older Ollama)
      Attempt 3 — repair pass if JSON is malformed

    Raises on all failures; caller handles via existing GNN fallback.
    """
    base_payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }

    # Attempt 1: JSON schema format (Ollama v0.5+)
    try:
        payload = {**base_payload, "format": schema}
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=TIMEOUT)
        if r.status_code == 400:
            # Schema-constrained format not supported — fall through to attempt 2
            logger.warning("Ollama returned 400 on schema format — retrying with format:'json'")
        else:
            r.raise_for_status()
            text = r.json()["message"]["content"]
            return json.loads(text)  # raises JSONDecodeError if malformed → attempt 2
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"NETWORK ERROR: Ollama unreachable at {OLLAMA_HOST}: {e}") from e
    except requests.exceptions.Timeout:
        raise TimeoutError(f"NETWORK ERROR: Ollama call timed out after {TIMEOUT}s")
    except json.JSONDecodeError:
        logger.warning("Attempt 1 produced malformed JSON — trying repair pass")
        raw_text = r.json()["message"]["content"] if r.ok else ""
        return _repair_json(raw_text, schema)
    except Exception:
        pass  # fall through to attempt 2

    # Attempt 2: generic format:"json" with strict prompting
    strict_prompt = (
        prompt
        + f"\n\nCRITICAL: Return ONLY a valid JSON object matching this schema: {json.dumps(schema)}. "
        "No markdown, no explanation, no trailing text."
    )
    try:
        payload = {**base_payload, "format": "json", "messages": [{"role": "user", "content": strict_prompt}]}
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        text = r.json()["message"]["content"]
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Attempt 2 produced malformed JSON — trying repair pass")
        raw_text = r.json()["message"]["content"] if r.ok else ""
        return _repair_json(raw_text, schema)
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"NETWORK ERROR: Ollama unreachable at {OLLAMA_HOST}: {e}") from e
    except requests.exceptions.Timeout:
        raise TimeoutError(f"NETWORK ERROR: Ollama call timed out after {TIMEOUT}s")


def _repair_json(broken_text: str, schema: Dict) -> Dict:
    """Attempt 3: ask the model to fix its own malformed JSON output."""
    repair_prompt = (
        f"The following text was supposed to be valid JSON matching this schema:\n{json.dumps(schema)}\n\n"
        f"Broken text:\n{broken_text}\n\n"
        "Return ONLY the corrected, valid JSON object. No markdown, no explanation."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": repair_prompt}],
        "format": "json",
    }
    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    # If this also fails, let JSONDecodeError propagate — caller treats it as MALFORMED RESPONSE
    result = json.loads(text)
    logger.info("MALFORMED RESPONSE repaired successfully on attempt 3.")
    return result


# ─── Extraction ────────────────────────────────────────────────────────────────

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "activity_phrase": {"type": "string"},
        "discipline": {
            "oneOf": [
                {"type": "string", "enum": ["Civil", "Piping", "Electrical", "Instrumentation", "HSE"]},
                {"type": "null"}
            ]
        },
        "action":       {"type": "string"},
        "activity_id":  {"type": ["string", "null"]},
        "quantity":     {"type": ["number", "null"]},
        "unit":         {"type": ["string", "null"]},
    },
    "required": ["activity_phrase", "discipline", "action", "activity_id", "quantity", "unit"],
}


def extract_structured_event(raw_phrase: str) -> Dict[str, Any]:
    """
    Extracts structured activity data from a raw field report phrase.
    Falls back to regex-based mock extraction if Ollama is unavailable.
    """
    if OLLAMA_STATUS["available"]:
        prompt = f"""You are an assistant for Oil India Limited (OIL) infrastructure projects (well pads, flowlines, GGS).
Extract the core activity from the following field report phrase.
Return a JSON object with:
- "activity_phrase": A cleaned, generic version of the core action being performed.
- "discipline": One of [Civil, Piping, Electrical, Instrumentation, HSE]. Return null if genuinely uncertain.
- "action": A very short 1-2 word summary of the action (e.g. "Installation", "Tie-in", "Drill").
- "activity_id": The exact activity ID if mentioned (e.g. "WELD-1042", "Ref: WELD-1042"). Null if not.
- "quantity": Numeric quantity mentioned. Null if not.
- "unit": Unit of quantity (e.g. "km", "joints", "m3"). Null if not.

Field Report: "{raw_phrase}"
"""
        try:
            return _ollama_generate(prompt, EXTRACT_SCHEMA)
        except ConnectionError as e:
            logger.error(f"LLM Extraction failed — {e}. Falling back to mock extraction.")
        except TimeoutError as e:
            logger.error(f"LLM Extraction failed — {e}. Falling back to mock extraction.")
        except json.JSONDecodeError:
            logger.error("LLM Extraction failed — MALFORMED RESPONSE: could not parse JSON after 3 attempts. Falling back to mock extraction.")
        except Exception as e:
            logger.error(f"LLM Extraction failed — unexpected error: {e}. Falling back to mock extraction.")
    else:
        logger.warning(f"Ollama unavailable ({OLLAMA_STATUS['reason']}). Using mock extractor.")

    # ── Mock / GNN Fallback ──────────────────────────────────────────────────
    import re

    lower_phrase = raw_phrase.lower()
    discipline_keywords = {
        "Piping":          ["pipe", "flowline", "tie-in", "weld"],
        "HSE":             ["drill", "audit", "safety", "hse"],
        "Civil":           ["civil", "tank", "foundation", "excavat", "concrete", "shuttering"],
        "Electrical":      ["cable", "termination", "wire", "electrical", "mcc", "panel"],
        "Instrumentation": ["instrument", "calibration", "sensor", "transmitter"],
    }

    discipline = None
    action = "Activity"
    for d, keywords in discipline_keywords.items():
        if any(kw in lower_phrase for kw in keywords):
            discipline = d
            action = f"{d} Work" if d != "HSE" else "HSE Action"
            break

    activity_id = None
    id_match = re.search(r"Ref:\s*([A-Z]+-\d+)", raw_phrase, re.IGNORECASE)
    if id_match:
        activity_id = id_match.group(1).upper()

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
        "unit": unit,
    }


# ─── Reranking ─────────────────────────────────────────────────────────────────

RERANK_SCHEMA = {
    "type": "object",
    "properties": {
        "node_id":       {"type": "string"},
        "reasoning":     {"type": "string"},
        "llm_certainty": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["node_id", "reasoning", "llm_certainty"],
}

_rerank_cache: Dict[str, Any] = {}


def llm_rerank_candidates(raw_phrase: str, extracted_data: Dict[str, Any], candidates: list) -> Optional[Dict[str, Any]]:
    """
    Passes the top GNN candidates to Ollama to contextually select the correct node.
    Returns {"node_id": str, "reasoning": str, "llm_certainty": "high"|"medium"|"low"}
    Returns None on failure — caller falls back to GNN rank-1 + needs-review.
    """
    if not OLLAMA_STATUS["available"]:
        logger.error(f"Reranker skipped: Ollama unavailable ({OLLAMA_STATUS['reason']})")
        return None

    cache_key = f"{OLLAMA_MODEL}_{raw_phrase}_" + ",".join([c["id"] for c in candidates])
    if cache_key in _rerank_cache:
        logger.info("Using cached LLM rerank result.")
        return _rerank_cache[cache_key]

    candidates_str = ""
    for i, c in enumerate(candidates):
        candidates_str += f"Rank {i+1}: ID={c['id']}, Name='{c['name']}', Discipline='{c['discipline']}', Unit='{c['unit']}'\n"

    prompt = f"""You are a scheduling assistant for Oil India Limited.
Your task is to select the exact activity node from a candidate list that best matches a field report.

Field Report: "{raw_phrase}"
Extracted Info: {json.dumps(extracted_data)}

Candidate Nodes (ranked by semantic similarity):
{candidates_str}

Reason step-by-step to choose the best matching node based on the context.
If multiple are similar, look at the discipline, action, and unit of measure.
If no node seems correct, pick the least wrong one and set llm_certainty to "low".

Return ONLY a valid JSON object with fields: node_id, reasoning, llm_certainty.
"""

    try:
        result = _ollama_generate(prompt, RERANK_SCHEMA)
        _rerank_cache[cache_key] = result
        return result
    except ConnectionError as e:
        logger.error(f"Reranker failed — {e}. Falling back to GNN rank-1.")
    except TimeoutError as e:
        logger.error(f"Reranker failed — {e}. Falling back to GNN rank-1.")
    except json.JSONDecodeError:
        logger.error("Reranker failed — MALFORMED RESPONSE: could not parse JSON after 3 attempts. Falling back to GNN rank-1.")
    except Exception as e:
        logger.error(f"Reranker failed — unexpected error: {e}. Falling back to GNN rank-1.")
    return None
