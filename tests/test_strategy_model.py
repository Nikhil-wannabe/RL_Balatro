from python.state import BalatroState, BlindState, EconomyState, MetaState, Joker, Card, HandLevelState
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


def test_duplicate_heavy_run_targets_rank_stack_hand():
    model = StrategyModel()
    duplicate_card = Card(id="dup0", rank="7", suit="Hearts", base_chips=7)
    state = BalatroState(
        meta=MetaState(
            protocol_version="1.0.0",
            seed="DUPES",
            ante=4,
            round=2,
            phase="SHOP",
            stake=6,
            deck_name="Erratic Deck",
            deck_key="b_erratic",
        ),
        blind=BlindState(name="Big Blind", target_score=1200, current_score=0),
        economy=EconomyState(money=18, hands_left=4, discards_left=3, hand_size=8),
        jokers=[
            Joker(id="j1", name="DNA"),
            Joker(id="j2", name="Square Joker"),
        ],
        deck=[
            duplicate_card.model_copy(update={"id": f"dup{i}"})
            for i in range(1, 10)
        ],
    )
    inference = model.infer(state)
    assert inference["run_plan"]["target_hand"] in {"Three of a Kind", "Full House", "Four of a Kind", "Five of a Kind"}
    assert inference["run_plan"]["hand_family"] == "duplicate"


def test_checkered_deck_prefers_celestial_packs():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(
            protocol_version="1.0.0",
            seed="CHK",
            ante=2,
            round=2,
            phase="SHOP",
            stake=4,
            deck_name="Checkered Deck",
            deck_key="b_checkered",
        ),
        blind=BlindState(name="Big Blind", target_score=450, current_score=0),
        economy=EconomyState(money=10, hands_left=4, discards_left=4, hand_size=8),
    )
    inference = model.infer(state)
    prefs = inference["run_plan"]["pack_preferences"]
    assert prefs["Celestial"] > prefs["Buffoon"]
    assert inference["run_plan"]["target_hand"] == "Flush"


def test_plant_boss_suppresses_face_card_plan():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="PLANT", ante=4, round=1, phase="SELECTING_HAND", stake=6),
        blind=BlindState(name="Boss Blind", target_score=1500, current_score=0, boss_modifier="The Plant", is_boss=True),
        economy=EconomyState(money=20, hands_left=3, discards_left=2, hand_size=8),
        jokers=[
            Joker(id="j1", name="Baron"),
            Joker(id="j2", name="Photograph"),
        ],
        deck=[
            Card(id="c1", rank="King", suit="Spades", base_chips=10),
            Card(id="c2", rank="Queen", suit="Hearts", base_chips=10),
            Card(id="c3", rank="Jack", suit="Clubs", base_chips=10),
        ],
    )
    inference = model.infer(state)
    assert inference["boss_profile"]["face_cards_debuffed"] is True
    assert inference["posterior"]["face_cards"] < inference["posterior"]["small_hand"]


def test_mouth_boss_locks_run_plan_to_existing_hand():
    model = StrategyModel()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="MOUTH", ante=3, round=1, phase="SELECTING_HAND", stake=4),
        blind=BlindState(name="Boss Blind", target_score=1200, current_score=0, boss_modifier="The Mouth", is_boss=True),
        economy=EconomyState(money=12, hands_left=3, discards_left=2, hand_size=8),
        hand_levels={"Pair": HandLevelState(level=2, played=4, played_this_round=1)},
    )
    inference = model.infer(state)
    assert inference["boss_profile"]["locked_hand"] == "Pair"
    assert inference["run_plan"]["target_hand"] == "Pair"
