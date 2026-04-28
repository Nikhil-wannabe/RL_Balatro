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


def test_desperation_ranking_can_prefer_discard_over_weak_play():
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Big", target_score=450, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
        hand=[], jokers=[]
    )
    brain = Brain()

    weak_play = brain.rank_action(
        state,
        ActionFeatures(
            action_type="PLAY_HAND",
            cards=["p1"],
            clear_probability=0.15,
            clear_probability_lcb=0.05,
            expected_score=30,
            score_variance=0.0,
            score_margin_vs_blind=-420,
            hands_remaining=3,
            discards_remaining=3,
            money_after_action=4,
            cards_used=1,
            discard_quality=0.0,
            future_hand_strength_estimate=-20.0,
            overkill=0.0,
        ),
        TacticalMode.DESPERATION,
    )
    strong_discard = brain.rank_action(
        state,
        ActionFeatures(
            action_type="DISCARD",
            cards=["d1", "d2"],
            clear_probability=0.20,
            clear_probability_lcb=0.10,
            expected_score=110,
            score_variance=0.0,
            score_margin_vs_blind=-340,
            hands_remaining=4,
            discards_remaining=2,
            money_after_action=4,
            cards_used=2,
            discard_quality=25.0,
            future_hand_strength_estimate=50.0,
            overkill=0.0,
        ),
        TacticalMode.DESPERATION,
    )

    ranked = brain.sort_ranked_actions([weak_play, strong_discard])
    assert ranked[0].features.action_type == "DISCARD"
