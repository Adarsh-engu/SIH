from fastapi.testclient import TestClient
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

import llm_extractor

# Mock the API keys to fail
class MockModels:
    def generate_content(self, *args, **kwargs):
        raise Exception("429 RESOURCE_EXHAUSTED Quota exceeded")

class MockClient:
    def __init__(self, api_key):
        self.models = MockModels()

llm_extractor.genai.Client = MockClient
llm_extractor.API_KEYS = [("PRIMARY", "FAKE")]

from main import app
from database import get_events

client = TestClient(app)

def test():
    print("Sending POST /report with failing API keys...")
    response = client.post("/report", json={"raw_phrase": "Test phrase that should fallback to GNN"})
    print("Status Code:", response.status_code)
    
    events = get_events()
    latest_event = events[0] if events else None
    if latest_event:
        print("Latest Event Status:", latest_event['status'])
        print("Latest Event Matched Node ID:", latest_event['matched_node_id'])
        print("Reasoning:", latest_event.get('match_reasoning', {}))
    else:
        print("No events found in DB!")

test()
