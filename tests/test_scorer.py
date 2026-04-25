from python.scorer import Scorer
from python.state import Card

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
