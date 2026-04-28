from python.boss_logic import (
    apply_base_score_scales,
    boss_profile_from_state,
    invalid_play_reason,
    money_after_play,
)
from python.state import BalatroState, BlindState, Card, EconomyState, HandLevelState, MetaState


def _boss_state(name: str) -> BalatroState:
    return BalatroState(
        meta=MetaState(protocol_version="1.0.0", seed="BOSS", ante=3, round=1, phase="SELECTING_HAND"),
        blind=BlindState(name="Boss Blind", target_score=1200, current_score=0, boss_modifier=name, is_boss=True),
        economy=EconomyState(money=12, hands_left=3, discards_left=2, hand_size=8),
    )


def test_psychic_requires_five_cards():
    state = _boss_state("The Psychic")
    cards = [
        Card(id="c1", rank="10", suit="Spades", base_chips=10),
        Card(id="c2", rank="10", suit="Hearts", base_chips=10),
    ]
    assert invalid_play_reason(state, "Pair", cards) == "requires_five_cards"


def test_eye_forbids_repeating_same_hand_type():
    state = _boss_state("The Eye")
    state.hand_levels = {"Pair": HandLevelState(level=1, played=3, played_this_round=1)}
    cards = [
        Card(id="c1", rank="10", suit="Spades", base_chips=10),
        Card(id="c2", rank="10", suit="Hearts", base_chips=10),
    ]
    assert invalid_play_reason(state, "Pair", cards) == "repeat_hand_forbidden"


def test_mouth_locks_to_first_hand_type():
    state = _boss_state("The Mouth")
    state.hand_levels = {"Pair": HandLevelState(level=1, played=3, played_this_round=1)}
    cards = [
        Card(id="c1", rank="10", suit="Spades", base_chips=10),
        Card(id="c2", rank="9", suit="Hearts", base_chips=9),
        Card(id="c3", rank="8", suit="Clubs", base_chips=8),
        Card(id="c4", rank="7", suit="Diamonds", base_chips=7),
        Card(id="c5", rank="6", suit="Spades", base_chips=6),
    ]
    assert invalid_play_reason(state, "Straight", cards) == "locked_to_first_hand_type"


def test_flint_halves_base_hand_scalars():
    state = _boss_state("The Flint")
    chips, mult = apply_base_score_scales(state, 40.0, 4.0)
    assert chips == 20.0
    assert mult == 2.0


def test_tooth_and_ox_change_money_after_play():
    tooth_state = _boss_state("The Tooth")
    assert money_after_play(tooth_state, hand_name="Pair", cards_used=4) == 8.0

    ox_state = _boss_state("The Ox")
    ox_state.hand_levels = {"Pair": HandLevelState(level=1, played=4, played_this_round=0)}
    assert money_after_play(ox_state, hand_name="Pair", cards_used=2) == 0.0


def test_crimson_heart_adds_boss_uncertainty():
    state = _boss_state("Crimson Heart")
    profile = boss_profile_from_state(state)
    assert profile.joker_uncertainty_penalty > 0.0
