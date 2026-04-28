import json
import time
from python.server import AgentServer
from python.action_types import ActionResponse

def test_malformed_json_returns_error():
    server = AgentServer()
    # Send bad JSON
    response_str = server.handle_request("{ bad_json: true }")
    response = json.loads(response_str)
    assert response["action"] == "ERROR"
    assert "Malformed" in response["message"]


def test_server_accepts_empty_list_for_blind_choices():
    server = AgentServer(async_selecting_hand=False)
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "XYZ", "ante": 2, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Big Blind", "target_score": 600, "current_score": 0},
        "economy": {"money": 10, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [
            {"id": "c1", "rank": "10", "suit": "Spades", "base_chips": 10}
        ],
        "jokers": [],
        "blind_choices": []
    }

    response_str = server.handle_request(json.dumps(payload))
    response = json.loads(response_str)

    assert response["action"] in ["PLAY_HAND", "DISCARD"]


def test_server_caches_identical_requests():
    server = AgentServer(async_selecting_hand=False)
    calls = {"count": 0}

    def fake_plan_action(_state):
        calls["count"] += 1
        return ActionResponse(action="NO_OP")

    server.planner.plan_action = fake_plan_action

    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "XYZ", "ante": 2, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Big Blind", "target_score": 600, "current_score": 0},
        "economy": {"money": 10, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [],
        "jokers": [],
    }
    raw = json.dumps(payload)

    response_1 = server.handle_request(raw)
    response_2 = server.handle_request(raw)

    assert calls["count"] == 1
    assert response_1 == response_2


def test_server_async_selecting_hand_returns_no_op_until_ready():
    calls = {"count": 0}

    class SlowPlanner:
        def plan_action(self, _state):
            calls["count"] += 1
            time.sleep(0.15)
            return ActionResponse(action="PLAY_HAND", cards=["c1"])

    server = AgentServer(planner_factory=lambda: SlowPlanner(), async_selecting_hand=True)
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "XYZ", "ante": 2, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Big Blind", "target_score": 600, "current_score": 0},
        "economy": {"money": 10, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [{"id": "c1", "rank": "10", "suit": "Spades", "base_chips": 10}],
        "jokers": [],
    }
    raw = json.dumps(payload)

    first = json.loads(server.handle_request(raw))
    assert first["action"] == "NO_OP"

    time.sleep(0.25)
    second = json.loads(server.handle_request(raw))
    assert second["action"] == "PLAY_HAND"
    assert second["cards"] == ["c1"]
    assert calls["count"] == 1
