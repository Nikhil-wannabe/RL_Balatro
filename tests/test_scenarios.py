import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../python')))

from state import BalatroState, MetaState, BlindState, EconomyState, Card
from planner import Planner

def create_base_state() -> BalatroState:
    return BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="TEST", ante=1, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Small Blind", target_score=300, current_score=0),
        economy=EconomyState(money=4, hands_left=4, discards_left=3, hand_size=8),
        hand=[],
        jokers=[]
    )

def test_lethal_case():
    """Scenario: Immediate clear exists and should be chosen over discard or weak plays."""
    state = create_base_state()
    # Need 300 score. Give a strong hand (e.g., Straight Flush) that easily clears.
    state.hand = [
        Card(id="c1", rank="10", suit="Spades", base_chips=10),
        Card(id="c2", rank="9", suit="Spades", base_chips=9),
        Card(id="c3", rank="8", suit="Spades", base_chips=8),
        Card(id="c4", rank="7", suit="Spades", base_chips=7),
        Card(id="c5", rank="6", suit="Spades", base_chips=6),
        Card(id="c6", rank="2", suit="Hearts", base_chips=2),
        Card(id="c7", rank="3", suit="Clubs", base_chips=3)
    ]
    
    planner = Planner()
    action = planner.plan_action(state)
    
    assert action.action == "PLAY_HAND"
    # Should select the straight flush
    assert len(action.cards) == 5
    assert set(action.cards) == {"c1", "c2", "c3", "c4", "c5"}

def test_desperation_discard():
    """Scenario: Cannot clear with current hand, must discard to survive."""
    state = create_base_state()
    state.blind.target_score = 60 # High enough that we can't clear, but low enough MC finds clears
    state.economy.hands_left = 1 # Only 1 hand left, must improve!
    state.economy.discards_left = 1
    
    # Hand is junk, high cards won't get 10k.
    state.hand = [
        Card(id="c1", rank="2", suit="Spades", base_chips=2),
        Card(id="c2", rank="4", suit="Hearts", base_chips=4),
        Card(id="c3", rank="7", suit="Clubs", base_chips=7),
        Card(id="c4", rank="9", suit="Diamonds", base_chips=9),
        Card(id="c5", rank="Jack", suit="Spades", base_chips=10),
        Card(id="c6", rank="3", suit="Hearts", base_chips=3),
        Card(id="c7", rank="5", suit="Clubs", base_chips=5)
    ]
    
    planner = Planner()
    action = planner.plan_action(state)
    
    assert action.action == "DISCARD"
    # The exact solver may choose one or more low-value setup discards, but it should never keep all junk.
    assert len(action.cards) >= 1
    assert any(card_id in action.cards for card_id in {"c1", "c2", "c6", "c7"})

def test_preserve_scaling_case():
    """Scenario: Target is easy, but we have many hands left. Prefer efficient play."""
    state = create_base_state()
    state.blind.target_score = 50
    
    # We have a high pair that clears, and a straight that also clears.
    # The pair uses fewer cards, preserving deck/efficiency.
    state.hand = [
        Card(id="c1", rank="Ace", suit="Spades", base_chips=11),
        Card(id="c2", rank="Ace", suit="Hearts", base_chips=11),
        Card(id="c3", rank="King", suit="Clubs", base_chips=10),
        Card(id="c4", rank="Queen", suit="Diamonds", base_chips=10),
        Card(id="c5", rank="Jack", suit="Spades", base_chips=10),
        Card(id="c6", rank="10", suit="Hearts", base_chips=10),
        Card(id="c7", rank="2", suit="Clubs", base_chips=2)
    ]
    
    planner = Planner()
    action = planner.plan_action(state)
    
    assert action.action == "PLAY_HAND"
    # Should play the pair of Aces (c1, c2) as it's more efficient than burning 5 cards
    assert "c1" in action.cards
    assert "c2" in action.cards
    assert len(action.cards) == 2

def test_deterministic_tie_breaking():
    """Scenario: Two identical pairs. Should deterministically pick one (stable sort)."""
    state = create_base_state()
    state.blind.target_score = 10
    
    # Two identical pairs of 3s
    state.hand = [
        Card(id="c1", rank="3", suit="Spades", base_chips=3),
        Card(id="c2", rank="3", suit="Hearts", base_chips=3),
        Card(id="c3", rank="3", suit="Clubs", base_chips=3),
        Card(id="c4", rank="3", suit="Diamonds", base_chips=3),
        Card(id="c5", rank="2", suit="Spades", base_chips=2)
    ]
    
    planner = Planner()
    action1 = planner.plan_action(state)
    action2 = planner.plan_action(state)
    
    # Must pick the exact same pair both times
    assert action1.action == action2.action
    assert action1.cards == action2.cards

def test_mc_repeatability():
    """Scenario: Monte Carlo should return identical results for identical seeds."""
    state = create_base_state()
    state.blind.target_score = 5000
    state.economy.hands_left = 2
    state.hand = [
        Card(id="c1", rank="2", suit="Spades", base_chips=2),
        Card(id="c2", rank="4", suit="Hearts", base_chips=4),
        Card(id="c3", rank="7", suit="Clubs", base_chips=7),
        Card(id="c4", rank="9", suit="Diamonds", base_chips=9),
        Card(id="c5", rank="Jack", suit="Spades", base_chips=10)
    ]
    
    planner1 = Planner()
    action1 = planner1.plan_action(state)
    
    planner2 = Planner()
    action2 = planner2.plan_action(state)
    
    # Due to fixed seed in config, MC evaluations should exactly match
    assert action1.action == action2.action
    assert action1.cards == action2.cards

def test_no_hands_fallback():
    """Scenario: 0 hands left should return NO_OP gracefully."""
    state = create_base_state()
    state.economy.hands_left = 0
    state.hand = [Card(id="c1", rank="2", suit="Spades", base_chips=2)]
    
    planner = Planner()
    action = planner.plan_action(state)
    
    assert action.action == "NO_OP"
