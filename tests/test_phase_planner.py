from python.planner import Planner
from python.state import BalatroState, BlindState, EconomyState, MetaState, ShopItemState


def test_round_eval_cash_out():
    planner = Planner()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase="ROUND_EVAL"),
        blind=BlindState(name="Small Blind", target_score=300, current_score=300),
        economy=EconomyState(money=4, hands_left=0, discards_left=0, hand_size=8),
    )
    action = planner.plan_action(state)
    assert action.action == "CASH_OUT"


def test_blind_select_defaults_to_select():
    planner = Planner()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=2, round=1, phase="BLIND_SELECT", blind_on_deck="Small"),
        blind=BlindState(name="Unknown", target_score=0, current_score=0),
        economy=EconomyState(money=4, hands_left=0, discards_left=0, hand_size=8),
    )
    action = planner.plan_action(state)
    assert action.action == "SELECT_BLIND"


def test_pack_choice_routes_to_take_pack_card():
    planner = Planner()
    state = BalatroState(
        meta=MetaState(
            protocol_version="1.0.0",
            seed="PACK",
            ante=1,
            round=1,
            phase="PACK_CHOICE",
            pack_kind="Buffoon",
        ),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
        pack_items=[
            ShopItemState(id="PK_1", name="Joker", set="Joker", cost=0),
            ShopItemState(id="PK_2", name="Green Joker", set="Joker", cost=0),
        ],
    )
    action = planner.plan_action(state)
    assert action.action == "TAKE_PACK_CARD"
    assert action.target_id == "PK_2"
