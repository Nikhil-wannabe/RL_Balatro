import json
from python.state import BalatroState

def test_state_parsing():
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "TEST", "ante": 1, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Small Blind", "target_score": 300, "current_score": 0},
        "economy": {"money": 5, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [{"id": "C1", "rank": "10", "suit": "Spades", "base_chips": 10}],
        "jokers": []
    }
    state = BalatroState(**payload)
    assert state.hand[0].rank == "10"
    assert state.meta.ante == 1
