from python.belief_model import BeliefModel
from python.exact_clear import ExactClearSolver
from python.monte_carlo import MonteCarloSimulator
from python.scorer import Scorer
from python.state import BalatroState, BlindState, EconomyState, Joker, MetaState, Card


def test_belief_model_creates_rule_uncertainty_for_active_jokers():
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="BELIEF", ante=2, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Big Blind", target_score=400, current_score=0),
        economy=EconomyState(money=5, hands_left=3, discards_left=2, hand_size=8),
        hand=[Card(id="h1", rank="Ace", suit="Spades", base_chips=11)],
        jokers=[Joker(id="j1", name="Mime")],
    )

    belief = BeliefModel().from_state(state)

    assert belief.unresolved_jokers == 1
    assert [model.model_id for model in belief.rule_models] == ["lower", "nominal", "upper"]


def test_exact_clear_solver_matches_simple_one_draw_probability():
    scorer = Scorer()
    solver = ExactClearSolver(scorer, exact_draw_enum_cap=1000)
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="EXACT", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Small Blind", target_score=100, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=5),
        hand=[
            Card(id="h1", rank="2", suit="Spades", base_chips=2),
            Card(id="h2", rank="3", suit="Spades", base_chips=3),
            Card(id="h3", rank="4", suit="Spades", base_chips=4),
            Card(id="h4", rank="5", suit="Spades", base_chips=5),
            Card(id="h5", rank="9", suit="Hearts", base_chips=9),
        ],
        deck=[
            Card(id="d1", rank="6", suit="Spades", base_chips=6),
            Card(id="d2", rank="9", suit="Clubs", base_chips=9),
        ],
        jokers=[],
    )

    belief = BeliefModel().from_state(state)
    result = solver.exact_discard_stats(state, belief, {"h5"}, current_best_score=14)

    assert result is not None
    assert result.combinations_evaluated == 2
    assert result.stats.clear_probability == 0.5
    assert result.stats.clear_probability_lcb > 0.0


def test_exact_clear_solver_collapses_duplicate_mutated_cards():
    scorer = Scorer()
    solver = ExactClearSolver(scorer, exact_draw_enum_cap=1000)
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="EXACT2", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Small Blind", target_score=100, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=5),
        hand=[
            Card(id="h1", rank="2", suit="Spades", base_chips=2),
            Card(id="h2", rank="3", suit="Spades", base_chips=3),
            Card(id="h3", rank="4", suit="Spades", base_chips=4),
            Card(id="h4", rank="5", suit="Spades", base_chips=5),
            Card(id="h5", rank="9", suit="Hearts", base_chips=9),
        ],
        deck=[
            Card(id="d1", rank="6", suit="Spades", base_chips=6, enhancement="Bonus"),
            Card(id="d2", rank="6", suit="Spades", base_chips=6, enhancement="Bonus"),
            Card(id="d3", rank="9", suit="Clubs", base_chips=9),
        ],
        jokers=[],
    )

    belief = BeliefModel().from_state(state)
    result = solver.exact_discard_stats(state, belief, {"h5"}, current_best_score=14)

    assert result is not None
    assert result.method == "exact_category_aggregation"
    assert result.combinations_evaluated == 2
    assert result.stats.clear_probability == 2 / 3


def test_tilted_shared_pool_is_deterministic():
    scorer = Scorer()
    mc = MonteCarloSimulator(scorer, num_rollouts=8, seed=42)
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="POOL", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
        hand=[
            Card(id="1", rank="2", suit="Spades", base_chips=2),
            Card(id="2", rank="3", suit="Spades", base_chips=3),
            Card(id="3", rank="4", suit="Hearts", base_chips=4),
            Card(id="4", rank="King", suit="Clubs", base_chips=10),
        ],
        jokers=[],
    )

    pool_a = mc.build_shared_pool(state, 2, rollout_count=6, proposal="tilted")
    pool_b = mc.build_shared_pool(state, 2, rollout_count=6, proposal="tilted")

    assert [(sample.draw_cards, sample.weight) for sample in pool_a] == [
        (sample.draw_cards, sample.weight) for sample in pool_b
    ]
