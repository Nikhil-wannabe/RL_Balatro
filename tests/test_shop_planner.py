from python.shop_planner import ShopPlanner
from python.state import BalatroState, BlindState, EconomyState, MetaState, ShopItemState
from python.strategy_model import StrategyModel


def test_shop_planner_buys_strong_voucher():
    planner = ShopPlanner()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="SHOP", ante=2, round=3, phase="SHOP", stake=4),
        blind=BlindState(name="Big Blind", target_score=600, current_score=0),
        economy=EconomyState(money=12, hands_left=4, discards_left=3, hand_size=8, reroll_cost=5),
        shop_items=[
            ShopItemState(id="SV_1", name="Overstock", set="Voucher", cost=10),
            ShopItemState(id="SJ_1", name="Joker", set="Joker", cost=2),
        ],
    )

    action = planner.plan_action(state)
    assert action.action == "BUY_CARD"
    assert action.target_id == "SV_1"


def test_shop_planner_buys_early_low_cost_tempo_joker():
    planner = ShopPlanner()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="SHOP2", ante=1, round=1, phase="SHOP", stake=1),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8, reroll_cost=5),
        shop_items=[
            ShopItemState(id="SJ_1", name="Jolly Joker", set="Joker", cost=4),
        ],
    )

    action = planner.plan_action(state)
    assert action.action == "BUY_CARD"
    assert action.target_id == "SJ_1"


def test_shop_planner_waits_for_inventory_before_leaving():
    planner = ShopPlanner()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="SHOP3", ante=1, round=1, phase="SHOP", stake=1),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8, reroll_cost=5),
        shop_items=[],
    )

    action = planner.plan_action(state)
    assert action.action == "NO_OP"
    assert action.message == "shop_inventory_pending"


def test_strategy_model_uses_deck_specific_priors():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(
            protocol_version="1.0.0",
            seed="DECK",
            ante=1,
            round=1,
            phase="SHOP",
            stake=1,
            deck_name="Checkered Deck",
            deck_key="b_checkered",
        ),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8, reroll_cost=5),
        shop_items=[],
    )

    inference = model.infer(state)
    assert inference["deck_profile"]["deck_key"] == "b_checkered"
    assert inference["posterior"]["flush"] > inference["posterior"]["straight"]


def test_shop_planner_buys_celestial_pack_for_nebula_planet_build():
    planner = ShopPlanner()
    state = BalatroState(
        meta=MetaState(
            protocol_version="1.0.0",
            seed="SHOP4",
            ante=2,
            round=2,
            phase="SHOP",
            stake=4,
            deck_name="Nebula Deck",
            deck_key="b_nebula",
        ),
        blind=BlindState(name="Big Blind", target_score=450, current_score=0),
        economy=EconomyState(money=8, hands_left=4, discards_left=4, hand_size=8, reroll_cost=5),
        shop_items=[
            ShopItemState(
                id="SB_1",
                name="Celestial Pack",
                set="Booster",
                cost=4,
                metadata={"kind": "Celestial", "config": {"extra": 3, "choose": 1}},
            ),
            ShopItemState(
                id="SB_2",
                name="Buffoon Pack",
                set="Booster",
                cost=4,
                metadata={"kind": "Buffoon", "config": {"extra": 2, "choose": 1}},
            ),
        ],
    )

    action = planner.plan_action(state)
    assert action.action == "BUY_CARD"
    assert action.target_id == "SB_1"
