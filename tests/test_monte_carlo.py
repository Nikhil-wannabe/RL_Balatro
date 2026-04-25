from python.monte_carlo import MonteCarloSimulator
from python.scorer import Scorer
from python.state import BalatroState, BlindState, EconomyState, MetaState, Card

def test_mc_stable_output():
    scorer = Scorer()
    mc = MonteCarloSimulator(scorer, num_rollouts=10, seed=42)
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase=""),
        blind=BlindState(name="Small", target_score=300, current_score=0),
        economy=EconomyState(money=0, hands_left=4, discards_left=3, hand_size=8),
        hand=[
            Card(id="1", rank="2", suit="Spades", base_chips=2),
            Card(id="2", rank="3", suit="Spades", base_chips=3),
            Card(id="3", rank="4", suit="Spades", base_chips=4),
            Card(id="4", rank="5", suit="Spades", base_chips=5),
            Card(id="5", rank="10", suit="Hearts", base_chips=10)
        ], jokers=[]
    )
    
    # We discard the outlier
    expected_improvement, clear_prob, variance, lower_quantile = mc.evaluate_discard(state, {"5"}, current_best_score=20)
    assert expected_improvement >= 0
    assert 0 <= clear_prob <= 1
    assert variance >= 0
    assert lower_quantile >= 0
    
    # Check determinism
    mc2 = MonteCarloSimulator(scorer, num_rollouts=10, seed=42)
    expected_score_2 = mc2.evaluate_discard(state, {"5"}, current_best_score=20)
    assert (expected_improvement, clear_prob, variance, lower_quantile) == expected_score_2


def test_mc_repeatability_is_independent_of_call_order():
    scorer = Scorer()
    mc = MonteCarloSimulator(scorer, num_rollouts=12, seed=42)
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="ORDER_TEST", ante=1, round=2, phase=""),
        blind=BlindState(name="Big", target_score=450, current_score=0),
        economy=EconomyState(money=3, hands_left=3, discards_left=2, hand_size=8),
        hand=[
            Card(id="1", rank="2", suit="Spades", base_chips=2),
            Card(id="2", rank="3", suit="Clubs", base_chips=3),
            Card(id="3", rank="4", suit="Hearts", base_chips=4),
            Card(id="4", rank="9", suit="Diamonds", base_chips=9),
            Card(id="5", rank="King", suit="Spades", base_chips=10),
        ],
        jokers=[],
    )

    first_eval = mc.evaluate_discard(state, {"4", "5"}, current_best_score=25)
    _ = mc.evaluate_discard(state, {"1"}, current_best_score=25)
    second_eval = mc.evaluate_discard(state, {"4", "5"}, current_best_score=25)

    assert first_eval == second_eval
