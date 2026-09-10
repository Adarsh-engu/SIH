import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

import llm_extractor
from llm_extractor import _generate_with_fallback
import logging

logging.basicConfig(level=logging.INFO)

# Monkeypatch genai to mock 429 exceptions
class MockResponse:
    text = '{"node_id": "A00123", "reasoning": "mock", "llm_certainty": "high"}'

class MockModels:
    def __init__(self, key):
        self.key = key
    def generate_content(self, *args, **kwargs):
        if self.key == 'BAD_KEY_1':
            raise Exception("429 RESOURCE_EXHAUSTED Quota exceeded")
        if self.key == 'BAD_KEY_2':
            raise Exception("429 Too Many Requests")
        if self.key == 'GOOD_KEY':
            return MockResponse()
        if self.key == 'ALL_BAD_KEY':
            raise Exception("429 Quota Exceeded!")

class MockClient:
    def __init__(self, api_key):
        self.models = MockModels(api_key)

llm_extractor.genai.Client = MockClient

def test_rotation():
    print("--- Test 1: Single Key Rotation (2 bad, 1 good) ---")
    llm_extractor.API_KEYS = [
        ("PRIMARY", "BAD_KEY_1"),
        ("GEMINI_API_KEY_BACKUP_1", "BAD_KEY_2"),
        ("GEMINI_API_KEY_BACKUP_2", "GOOD_KEY")
    ]
    try:
        res = _generate_with_fallback('test-model', 'test-prompt')
        print("Result:", res)
        print("Test 1 Passed: Successfully rotated to good key.")
    except Exception as e:
        print("Test 1 Failed:", e)

def test_exhaustion():
    print("\n--- Test 2: All Keys Exhausted ---")
    llm_extractor.API_KEYS = [
        ("PRIMARY", "ALL_BAD_KEY"),
        ("GEMINI_API_KEY_BACKUP_1", "ALL_BAD_KEY")
    ]
    try:
        _generate_with_fallback('test-model', 'test-prompt')
        print("Test 2 Failed: Should have thrown an exception!")
    except Exception as e:
        print("Test 2 Passed: Raised exception when all keys exhausted -", str(e))

if __name__ == "__main__":
    test_rotation()
    test_exhaustion()
