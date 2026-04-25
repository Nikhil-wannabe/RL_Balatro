from python.brain import Brain, TacticalMode, ActionFeatures
from python.state import BalatroState, BlindState, EconomyState, MetaState

def test_lethal_mode():
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase=""),
        blind=BlindState(name="Small", target_score=300, current_score=0),
        economy=EconomyState(money=0, hands_left=4, discards_left=3, hand_size=8),
        hand=[], jokers=[]
    )
    brain = Brain()
    mode = brain.determine_mode(state, 350, 1.0)
    assert mode == TacticalMode.LETHAL

def test_desperation_mode():
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase=""),
        blind=BlindState(name="Small", target_score=1000, current_score=0),
        economy=EconomyState(money=0, hands_left=1, discards_left=3, hand_size=8),
        hand=[], jokers=[]
    )
    brain = Brain()
    mode = brain.determine_mode(state, 50, 0.1)
    assert mode == TacticalMode.DESPERATION

def test_lethal_efficiency():
    brain = Brain()
    util_2 = brain.calculate_utility(ActionFeatures(
        action_type="PLAY_HAND",
        cards=["a", "b"],
        clear_probability=1.0,
        expected_score=350,
        score_variance=0.0,
        score_margin_vs_blind=50,
        hands_remaining=3,
        discards_remaining=3,
        money_after_action=0,
        cards_used=2,
        discard_quality=0.0,
        future_hand_strength_estimate=0.0,
        overkill=50.0,
    ), TacticalMode.LETHAL)
    util_5 = brain.calculate_utility(ActionFeatures(
        action_type="PLAY_HAND",
        cards=["a", "b", "c", "d", "e"],
        clear_probability=1.0,
        expected_score=350,
        score_variance=0.0,
        score_margin_vs_blind=50,
        hands_remaining=3,
        discards_remaining=3,
        money_after_action=0,
        cards_used=5,
        discard_quality=0.0,
        future_hand_strength_estimate=0.0,
        overkill=50.0,
    ), TacticalMode.LETHAL)
    assert util_2 > util_5
