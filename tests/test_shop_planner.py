from python.shop_planner import ShopPlanner
from python.state import BalatroState, BlindState, EconomyState, MetaState, ShopItemState


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
