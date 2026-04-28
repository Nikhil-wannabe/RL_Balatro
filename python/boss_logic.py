from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional, Sequence, Tuple

from state import BalatroState, Card


SUIT_DEBUFF_BOSSES = {
    "The Club": "Clubs",
    "The Goad": "Spades",
    "The Head": "Hearts",
    "The Window": "Diamonds",
}


@dataclass(frozen=True)
class BossProfile:
    name: str = ""
    debuffed_suit: Optional[str] = None
    face_cards_debuffed: bool = False
    require_five_card_play: bool = False
    forbid_repeat_hands: bool = False
    lock_to_first_hand_type: bool = False
    money_to_zero_on_most_played: bool = False
    money_loss_per_card: int = 0
    one_hand_only: bool = False
    base_chips_scale: float = 1.0
    base_mult_scale: float = 1.0
    future_penalty: float = 0.0
    joker_uncertainty_penalty: float = 0.0
    immediate_clear_pressure: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def boss_name(state: Optional[BalatroState]) -> str:
    if state is None:
        return ""
    explicit = str(getattr(state.blind, "boss_modifier", "") or "").strip()
    if explicit:
        return explicit
    if getattr(state.blind, "is_boss", False):
        return str(getattr(state.blind, "name", "") or "").strip()
    return ""


def boss_profile_from_state(state: Optional[BalatroState]) -> BossProfile:
    name = boss_name(state)
    if not name:
        return BossProfile()

    base = BossProfile(name=name, debuffed_suit=SUIT_DEBUFF_BOSSES.get(name))
    overrides = {
        "The Plant": dict(face_cards_debuffed=True, future_penalty=0.08),
        "The Psychic": dict(require_five_card_play=True, immediate_clear_pressure=0.08),
        "The Eye": dict(forbid_repeat_hands=True, future_penalty=0.10),
        "The Mouth": dict(lock_to_first_hand_type=True, future_penalty=0.10),
        "The Needle": dict(one_hand_only=True, immediate_clear_pressure=0.20),
        "The Flint": dict(base_chips_scale=0.5, base_mult_scale=0.5, immediate_clear_pressure=0.12),
        "The Tooth": dict(money_loss_per_card=1),
        "The Ox": dict(money_to_zero_on_most_played=True),
        "The Hook": dict(future_penalty=0.18),
        "The Fish": dict(future_penalty=0.12),
        "The Arm": dict(future_penalty=0.16),
        "Crimson Heart": dict(joker_uncertainty_penalty=0.10, future_penalty=0.10),
        "Verdant Leaf": dict(joker_uncertainty_penalty=0.08, future_penalty=0.08),
        "Cerulean Bell": dict(joker_uncertainty_penalty=0.08, future_penalty=0.12),
        "Amber Acorn": dict(joker_uncertainty_penalty=0.05),
        "Violet Vessel": dict(immediate_clear_pressure=0.10),
    }
    merged = base.as_dict()
    merged.update(overrides.get(name, {}))
    return BossProfile(**merged)


def hand_played_this_round(state: Optional[BalatroState], hand_name: str) -> int:
    if state is None or not hand_name:
        return 0
    info = state.hand_levels.get(hand_name)
    return int(getattr(info, "played_this_round", 0)) if info is not None else 0


def locked_hand_type(state: Optional[BalatroState]) -> str:
    if state is None:
        return ""
    positive = [
        (name, int(getattr(info, "played_this_round", 0)), int(getattr(info, "played", 0)))
        for name, info in state.hand_levels.items()
        if int(getattr(info, "played_this_round", 0)) > 0
    ]
    if not positive:
        return ""
    positive.sort(key=lambda item: (item[1], item[2], item[0]), reverse=True)
    return positive[0][0]


def most_played_hand(state: Optional[BalatroState]) -> str:
    if state is None:
        return ""
    tallies = [
        (name, int(getattr(info, "played", 0)), int(getattr(info, "level", 1)))
        for name, info in state.hand_levels.items()
    ]
    if not tallies:
        return ""
    tallies.sort(key=lambda item: (item[1], item[2], item[0]), reverse=True)
    return tallies[0][0]


def invalid_play_reason(
    state: Optional[BalatroState],
    hand_name: str,
    played_cards: Sequence[Card],
) -> str:
    profile = boss_profile_from_state(state)
    if not profile.name:
        return ""
    if profile.require_five_card_play and len(played_cards) < 5:
        return "requires_five_cards"
    if profile.forbid_repeat_hands and hand_played_this_round(state, hand_name) > 0:
        return "repeat_hand_forbidden"
    if profile.lock_to_first_hand_type:
        locked = locked_hand_type(state)
        if locked and hand_name != locked:
            return "locked_to_first_hand_type"
    return ""


def apply_base_score_scales(
    state: Optional[BalatroState],
    base_chips: float,
    base_mult: float,
) -> Tuple[float, float]:
    profile = boss_profile_from_state(state)
    return base_chips * profile.base_chips_scale, base_mult * profile.base_mult_scale


def money_after_play(
    state: Optional[BalatroState],
    *,
    hand_name: str,
    cards_used: int,
    money_delta: float = 0.0,
) -> float:
    if state is None:
        return money_delta
    money = float(state.economy.money) + float(money_delta)
    profile = boss_profile_from_state(state)
    if profile.money_to_zero_on_most_played:
        most_played = most_played_hand(state)
        if most_played and hand_name == most_played:
            money = 0.0
    if profile.money_loss_per_card > 0:
        money -= profile.money_loss_per_card * cards_used
    return max(0.0, money)


def future_penalty_scale(
    state: Optional[BalatroState],
    hand_name: str,
    *,
    hands_after_action: int,
) -> float:
    if state is None or hands_after_action <= 0:
        return 0.0
    profile = boss_profile_from_state(state)
    penalty = profile.future_penalty
    if profile.name == "The Arm":
        info = state.hand_levels.get(hand_name)
        if info is not None and int(getattr(info, "level", 1)) <= 1:
            penalty *= 0.5
    if profile.name == "The Needle":
        penalty = max(penalty, 0.20)
    return penalty
