from python.planner import Planner
from python.state import BalatroState
import os

def test_planner_lethal():
    import json
    
    # We load from the examples folder.
    file_path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'sample_playable.json')
    with open(file_path, 'r') as f:
        state = BalatroState(**json.load(f))
    planner = Planner()
    action = planner.plan_action(state)
    assert action.action == "PLAY_HAND"
    assert len(action.cards) > 0
