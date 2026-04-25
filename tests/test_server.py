import json
from python.server import AgentServer

def test_malformed_json_returns_error():
    server = AgentServer()
    # Send bad JSON
    response_str = server.handle_request("{ bad_json: true }")
    response = json.loads(response_str)
    assert response["action"] == "ERROR"
    assert "Malformed" in response["message"]
