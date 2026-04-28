import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../python')))

from server import AgentServer

def test_valid_payload_parsing():
    server = AgentServer(async_selecting_hand=False)
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "XYZ", "ante": 2, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Big Blind", "target_score": 600, "current_score": 0},
        "economy": {"money": 10, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [
            {"id": "c1", "rank": "10", "suit": "Spades", "base_chips": 10}
        ],
        "jokers": []
    }
    
    response_str = server.handle_request(json.dumps(payload))
    response = json.loads(response_str)
    
    # Even with a weak hand, it should return a valid action, like PLAY_HAND or DISCARD
    assert "action" in response
    assert response["action"] in ["PLAY_HAND", "DISCARD"]
    assert "cards" in response
    assert isinstance(response["cards"], list)
    assert len(response["cards"]) > 0

def test_malformed_json():
    server = AgentServer(async_selecting_hand=False)
    response_str = server.handle_request("{ bad json")
    response = json.loads(response_str)
    
    assert response["action"] == "ERROR"
    assert "Malformed JSON" in response["message"]

def test_missing_fields_in_payload():
    server = AgentServer(async_selecting_hand=False)
    # Missing 'economy' which is required by BalatroState
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "XYZ", "ante": 2, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Big Blind", "target_score": 600, "current_score": 0},
        "hand": [],
        "jokers": []
    }
    
    response_str = server.handle_request(json.dumps(payload))
    response = json.loads(response_str)
    
    assert response["action"] == "ERROR"
