from python.state import BalatroState, BlindState, EconomyState, MetaState, Joker, Card
from python.strategy_model import StrategyModel


def test_deck_growth_archetype_inference():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="A", ante=3, round=4, phase="SHOP", stake=5),
        blind=BlindState(name="Big Blind", target_score=1200, current_score=0),
        economy=EconomyState(money=18, hands_left=4, discards_left=2, hand_size=8),
        jokers=[
            Joker(id="j1", name="Blue Joker"),
            Joker(id="j2", name="Hologram"),
            Joker(id="j3", name="DNA"),
        ],
        deck=[Card(id=f"d{i}", rank="2", suit="Spades", base_chips=2) for i in range(20)],
    )
    inference = model.infer(state)
    assert inference["posterior"]["deck_growth"] > inference["posterior"]["flush"]


def test_held_in_hand_archetype_inference():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="B", ante=5, round=2, phase="SHOP", stake=7),
        blind=BlindState(name="Boss Blind", target_score=4000, current_score=0),
        economy=EconomyState(money=22, hands_left=3, discards_left=2, hand_size=8),
        jokers=[
            Joker(id="j1", name="Mime"),
            Joker(id="j2", name="Baron"),
            Joker(id="j3", name="Steel Joker"),
        ],
        deck=[
            Card(id="c1", rank="King", suit="Spades", base_chips=10, enhancement="Steel"),
            Card(id="c2", rank="King", suit="Hearts", base_chips=10, enhancement="Steel", seal="Blue"),
            Card(id="c3", rank="Queen", suit="Clubs", base_chips=10),
        ],
    )
    inference = model.infer(state)
    assert inference["posterior"]["held_in_hand"] > inference["posterior"]["straight"]
