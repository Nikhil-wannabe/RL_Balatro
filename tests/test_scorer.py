from python.scorer import Scorer
from python.state import BalatroState, BlindState, Card, EconomyState, HandLevelState, Joker, MetaState

def test_scorer_full_house():
    scorer = Scorer()
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
        Card(id="3", rank="10", suit="Clubs", base_chips=10),
        Card(id="4", rank="5", suit="Diamonds", base_chips=5),
        Card(id="5", rank="5", suit="Spades", base_chips=5)
    ]
    score = scorer.evaluate_play(played, [], [])
    # 40 base + 30 + 10 = 80 chips. 80 * 4 = 320
    assert score == 320

def test_scorer_flush():
    scorer = Scorer()
    played = [Card(id=str(i), rank=str(i+2), suit="Spades", base_chips=i+2) for i in range(5)]
    hand_type, _ = scorer.classify_hand(played)
    assert hand_type == "Straight Flush"

def test_scorer_ace_low_straight():
    scorer = Scorer()
    played = [
        Card(id="1", rank="Ace", suit="Spades", base_chips=11),
        Card(id="2", rank="2", suit="Hearts", base_chips=2),
        Card(id="3", rank="3", suit="Clubs", base_chips=3),
        Card(id="4", rank="4", suit="Diamonds", base_chips=4),
        Card(id="5", rank="5", suit="Spades", base_chips=5)
    ]
    hand_type, _ = scorer.classify_hand(played)
    assert hand_type == "Straight"

def test_scoring_cards_only():
    scorer = Scorer()
    # Play 3 cards: a pair of 10s and a 2.
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
        Card(id="3", rank="2", suit="Clubs", base_chips=2)
    ]
    score = scorer.evaluate_play(played, [], [])
    # Hand is Pair. Base chips = 10, Mult = 2.
    # Scoring cards are ONLY the two 10s. Base chips = 10 + 10 + 10 = 30. Mult = 2.
    # Score = 60. The "2" does not contribute base chips!
    assert score == 60


def test_scorer_flush_five_uses_balatro_hand_level():
    scorer = Scorer()
    played = [
        Card(id="1", rank="King", suit="Spades", base_chips=10),
        Card(id="2", rank="King", suit="Spades", base_chips=10, enhancement="Wild Card"),
        Card(id="3", rank="King", suit="Spades", base_chips=10),
        Card(id="4", rank="King", suit="Spades", base_chips=10),
        Card(id="5", rank="King", suit="Spades", base_chips=10),
    ]
    hand_type, scoring = scorer.classify_hand(played)
    assert hand_type == "Flush Five"
    assert len(scoring) == 5
    assert scorer.evaluate_play(played, [], []) == 3360


def test_scorer_uses_state_hand_levels_and_blue_joker():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="X", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
        hand=[],
        deck=[Card(id=f"d{i}", rank="2", suit="Spades", base_chips=2) for i in range(10)],
        discard_pile=[Card(id="x", rank="3", suit="Hearts", base_chips=3)],
        hand_levels={"Pair": HandLevelState(level=3, chips=20, mult=3)},
    )
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    jokers = [Joker(id="j1", name="Blue Joker", internal_state={"extra": 2})]
    score = scorer.evaluate_play(played, [], jokers, state)
    # Pair hand level gives 20 chips / 3 mult, pair adds two tens, Blue Joker uses visible deck total 11.
    assert score == 186


def test_scorer_baron_and_photograph_stack_xmult():
    scorer = Scorer()
    played = [
        Card(id="1", rank="Queen", suit="Spades", base_chips=10),
        Card(id="2", rank="Queen", suit="Hearts", base_chips=10),
    ]
    held = [
        Card(id="3", rank="King", suit="Clubs", base_chips=10),
        Card(id="4", rank="King", suit="Spades", base_chips=10),
    ]
    jokers = [
        Joker(id="j1", name="Photograph", internal_state={"extra": 2}),
        Joker(id="j2", name="Baron", internal_state={"extra": 1.5}),
    ]
    score = scorer.evaluate_play(played, held, jokers)
    # Pair: (10 base + 20 pair chips) * 2 mult * Photograph x2 * Baron x1.5^2
    assert score == 270


def test_scorer_psychic_invalidates_short_play():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="PSY", ante=2, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=450, current_score=0, boss_modifier="The Psychic", is_boss=True),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
    )
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(played, [], [], state) == 0


def test_debuffed_cards_still_define_hand_type_but_do_not_score():
    scorer = Scorer()
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10, is_debuffed=True),
        Card(id="2", rank="10", suit="Hearts", base_chips=10, is_debuffed=True),
    ]

    hand_type, scoring = scorer.classify_hand(played)

    assert hand_type == "Pair"
    assert len(scoring) == 2
    assert scorer.evaluate_play(played, [], []) == 20


def test_boss_debuffed_cards_keep_hand_type_with_only_base_score():
    scorer = Scorer()
    plant_state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="PLANT", ante=3, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=600, current_score=0, boss_modifier="The Plant", is_boss=True),
        economy=EconomyState(money=4, hands_left=3, discards_left=2, hand_size=8),
    )
    face_pair = [
        Card(id="1", rank="King", suit="Spades", base_chips=10),
        Card(id="2", rank="King", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(face_pair, [], [], plant_state) == 20

    head_state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="HEAD", ante=3, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=600, current_score=0, boss_modifier="The Head", is_boss=True),
        economy=EconomyState(money=4, hands_left=3, discards_left=2, hand_size=8),
    )
    heart_flush = [
        Card(id="3", rank="2", suit="Hearts", base_chips=2),
        Card(id="4", rank="4", suit="Hearts", base_chips=4),
        Card(id="5", rank="6", suit="Hearts", base_chips=6),
        Card(id="6", rank="8", suit="Hearts", base_chips=8),
        Card(id="7", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(heart_flush, [], [], head_state) == 140


def test_scorer_eye_blocks_repeated_hand_type():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="EYE", ante=3, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=600, current_score=0, boss_modifier="The Eye", is_boss=True),
        economy=EconomyState(money=4, hands_left=3, discards_left=2, hand_size=8),
        hand_levels={"Pair": HandLevelState(level=1, played=3, played_this_round=1)},
    )
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(played, [], [], state) == 0


def test_scorer_flint_halves_base_hand_only():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="FLINT", ante=3, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=600, current_score=0, boss_modifier="The Flint", is_boss=True),
        economy=EconomyState(money=4, hands_left=3, discards_left=2, hand_size=8),
    )
    played = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(played, [], [], state) == 25


def test_scorer_bootstraps_arrowhead_and_onyx_agate():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="BOOST", ante=2, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Big Blind", target_score=600, current_score=0),
        economy=EconomyState(money=15, hands_left=4, discards_left=3, hand_size=8),
    )
    played_bootstraps = [
        Card(id="1", rank="10", suit="Spades", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    bootstraps = [Joker(id="j1", name="Bootstraps")]
    assert scorer.evaluate_play(played_bootstraps, [], bootstraps, state) == 240

    played_arrow = [
        Card(id="3", rank="10", suit="Spades", base_chips=10),
        Card(id="4", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(played_arrow, [], [Joker(id="j2", name="Arrowhead")], state) == 160

    played_onyx = [
        Card(id="5", rank="10", suit="Clubs", base_chips=10),
        Card(id="6", rank="10", suit="Hearts", base_chips=10),
    ]
    assert scorer.evaluate_play(played_onyx, [], [Joker(id="j3", name="Onyx Agate")], state) == 270


def test_scorer_drivers_license_and_money_delta():
    scorer = Scorer()
    state = BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="DL", ante=4, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Big Blind", target_score=1200, current_score=0),
        economy=EconomyState(money=10, hands_left=4, discards_left=3, hand_size=8),
        deck=[
            Card(id=f"d{i}", rank="2", suit="Spades", base_chips=2, enhancement="Bonus")
            for i in range(16)
        ],
    )
    played = [
        Card(id="1", rank="10", suit="Diamonds", base_chips=10),
        Card(id="2", rank="10", suit="Hearts", base_chips=10),
    ]
    jokers = [
        Joker(id="j1", name="Driver's License"),
        Joker(id="j2", name="Rough Gem"),
    ]
    assert scorer.evaluate_play(played, [], jokers, state) == 180
    assert scorer.estimate_money_delta(played, [], jokers, state) == 1.0
