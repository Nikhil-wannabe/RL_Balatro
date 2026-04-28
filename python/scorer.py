from __future__ import annotations

import itertools
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from boss_logic import apply_base_score_scales, boss_profile_from_state, invalid_play_reason
from rank_utils import get_rank_value
from state import BalatroState, Card, Joker

SUITS = ("Spades", "Hearts", "Clubs", "Diamonds")
BLACK_SUITS = {"Spades", "Clubs"}
RED_SUITS = {"Hearts", "Diamonds"}
FACE_RANKS = {"Jack", "Queen", "King"}
FIBONACCI_RANKS = {2, 3, 5, 8, 14}
EVEN_RANKS = {2, 4, 6, 8, 10}
ODD_RANKS = {3, 5, 7, 9}

DEFAULT_HAND_LEVELS = {
    "Flush Five": (160, 16),
    "Flush House": (140, 14),
    "Five of a Kind": (120, 12),
    "Straight Flush": (100, 8),
    "Four of a Kind": (60, 7),
    "Full House": (40, 4),
    "Flush": (35, 4),
    "Straight": (30, 4),
    "Three of a Kind": (30, 3),
    "Two Pair": (20, 2),
    "Pair": (10, 2),
    "High Card": (5, 1),
}

HAND_PRIORITY = [
    "Flush Five",
    "Flush House",
    "Five of a Kind",
    "Straight Flush",
    "Four of a Kind",
    "Full House",
    "Flush",
    "Straight",
    "Three of a Kind",
    "Two Pair",
    "Pair",
    "High Card",
]

MULT_HAND_JOKERS = {
    "Jolly Joker": "Pair",
    "Zany Joker": "Three of a Kind",
    "Mad Joker": "Two Pair",
    "Crazy Joker": "Straight",
    "Droll Joker": "Flush",
}

CHIP_HAND_JOKERS = {
    "Sly Joker": "Pair",
    "Wily Joker": "Three of a Kind",
    "Clever Joker": "Two Pair",
    "Devious Joker": "Straight",
    "Crafty Joker": "Flush",
}

SUIT_MULT_JOKERS = {
    "Greedy Joker": "Diamonds",
    "Lusty Joker": "Hearts",
    "Wrathful Joker": "Spades",
    "Gluttonous Joker": "Clubs",
}

PERSISTENT_XMULT_JOKERS = {
    "Cavendish",
    "Hologram",
    "Constellation",
    "Campfire",
    "Obelisk",
    "Vampire",
    "Throwback",
    "Glass Joker",
    "Ramen",
}
PERSISTENT_MULT_JOKERS = {"Green Joker", "Fortune Teller", "Spare Trousers", "Flash Card", "Popcorn"}
PERSISTENT_CHIP_JOKERS = {"Square Joker", "Runner"}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_enhancement(value: str) -> str:
    effect = _normalize_text(value).lower()
    if "bonus" in effect:
        return "bonus"
    if "mult" in effect and "x" not in effect:
        return "mult"
    if "wild" in effect:
        return "wild"
    if "glass" in effect:
        return "glass"
    if "steel" in effect:
        return "steel"
    if "stone" in effect:
        return "stone"
    if "gold" in effect:
        return "gold"
    if "lucky" in effect:
        return "lucky"
    return "none"


def _extract_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(\.\d+)?", value)
        if match:
            return float(match.group(0))
    return default


def _ordered_subsets(cards: Sequence[Card], size: int) -> Iterable[List[Card]]:
    for combo in itertools.combinations(cards, size):
        yield list(combo)


class Scorer:
    BASE_SCORES = DEFAULT_HAND_LEVELS

    def evaluate_play(
        self,
        played_cards: List[Card],
        held_cards: List[Card],
        jokers: List[Joker],
        state: Optional[BalatroState] = None,
    ) -> int:
        active_jokers = [joker for joker in jokers if not joker.is_debuffed]
        if not played_cards:
            return 0

        hand_type, scoring_cards = self.classify_hand(played_cards, active_jokers)
        if self._has_joker(active_jokers, "Splash"):
            scoring_cards = list(played_cards)
        if invalid_play_reason(state, hand_type, played_cards):
            return 0

        base_chips, base_mult = self._hand_level(hand_type, state)
        base_chips, base_mult = apply_base_score_scales(state, base_chips, base_mult)
        chips = float(base_chips)
        mult = float(base_mult)
        x_mult = 1.0

        scoring_ids = {card.id for card in scoring_cards}
        ordered_scoring = [
            card
            for card in played_cards
            if card.id in scoring_ids and not self._card_is_debuffed(card, state, active_jokers)
        ]
        photograph_used = False
        scoring_faces = 0

        for card in ordered_scoring:
            chips += self._card_chip_bonus(card)
            mult += self._card_mult_bonus(card)
            x_mult *= self._card_x_mult(card)
            chips, mult, x_mult = self._apply_edition(card.edition, chips, mult, x_mult)

            is_face = self._is_face_card(card, active_jokers)
            if is_face:
                scoring_faces += 1

            if is_face and self._has_joker(active_jokers, "Scary Face"):
                chips += self._joker_number(active_jokers, "Scary Face", ("extra",), default=30.0)
            if is_face and self._has_joker(active_jokers, "Smiley Face"):
                mult += self._joker_number(active_jokers, "Smiley Face", ("extra",), default=5.0)
            if is_face and self._has_joker(active_jokers, "Photograph") and not photograph_used:
                x_mult *= max(1.0, self._joker_number(active_jokers, "Photograph", ("extra",), ("x_mult",), default=2.0))
                photograph_used = True

            rank_value = self._card_rank_value(card)
            if rank_value == 14 and self._has_joker(active_jokers, "Scholar"):
                chips += self._joker_number(active_jokers, "Scholar", ("extra", "chips"), default=20.0)
                mult += self._joker_number(active_jokers, "Scholar", ("extra", "mult"), default=4.0)

            if rank_value in FIBONACCI_RANKS and self._has_joker(active_jokers, "Fibonacci"):
                mult += self._joker_number(active_jokers, "Fibonacci", ("extra",), default=8.0)

            if rank_value in {4, 10} and self._has_joker(active_jokers, "Walkie Talkie"):
                chips += self._joker_number(active_jokers, "Walkie Talkie", ("extra", "chips"), default=10.0)
                mult += self._joker_number(active_jokers, "Walkie Talkie", ("extra", "mult"), default=4.0)

            if rank_value in EVEN_RANKS and self._has_joker(active_jokers, "Even Steven"):
                mult += self._joker_number(active_jokers, "Even Steven", ("extra",), default=4.0)
            if rank_value in ODD_RANKS and self._has_joker(active_jokers, "Odd Todd"):
                chips += self._joker_number(active_jokers, "Odd Todd", ("extra",), default=31.0)

            for joker_name, suit in SUIT_MULT_JOKERS.items():
                if self._has_joker(active_jokers, joker_name) and self._card_matches_suit(card, suit, active_jokers):
                    mult += self._joker_number(
                        active_jokers,
                        joker_name,
                        ("extra", "s_mult"),
                        ("extra",),
                        default=3.0,
                    )
            if self._has_joker(active_jokers, "Arrowhead") and self._card_matches_suit(card, "Spades", active_jokers):
                chips += self._joker_number(active_jokers, "Arrowhead", ("extra",), default=50.0)
            if self._has_joker(active_jokers, "Onyx Agate") and self._card_matches_suit(card, "Clubs", active_jokers):
                mult += self._joker_number(active_jokers, "Onyx Agate", ("extra",), default=7.0)
            if self._has_joker(active_jokers, "Bloodstone") and self._card_matches_suit(card, "Hearts", active_jokers):
                odds = max(1.0, self._joker_number(active_jokers, "Bloodstone", ("extra", "odds"), default=2.0))
                proc_x = max(1.0, self._joker_number(active_jokers, "Bloodstone", ("extra", "Xmult"), ("extra", "x_mult"), default=1.5))
                x_mult *= max(1.0, 1.0 + ((proc_x - 1.0) / odds))

            ancient_suit = self._joker_current_suit(active_jokers, "Ancient Joker")
            if ancient_suit and self._card_matches_suit(card, ancient_suit, active_jokers):
                x_mult *= max(1.0, self._joker_number(active_jokers, "Ancient Joker", ("extra",), default=1.5))

        active_held_cards = [
            card for card in held_cards if not self._card_is_debuffed(card, state, active_jokers)
        ]
        for card in active_held_cards:
            x_mult *= self._held_card_x_mult(card)

        total_cards = self._deck_card_count(state, played_cards, held_cards)
        played_faces = scoring_faces
        hand_played_count = self._hand_played_count(state, hand_type)
        hand_played_this_round = self._hand_played_this_round(state, hand_type)
        all_held_black = bool(active_held_cards) and all(
            self._card_is_black(card, active_jokers) for card in active_held_cards
        )

        for joker in active_jokers:
            name = joker.name

            if name == "Joker":
                mult += self._joker_number([joker], name, ("mult",), default=4.0)
            elif name == "Gros Michel":
                mult += self._joker_number([joker], name, ("extra", "mult"), ("mult",), ("extra",), default=15.0)
            elif name in MULT_HAND_JOKERS and hand_type == MULT_HAND_JOKERS[name]:
                mult += self._joker_number([joker], name, ("t_mult",), ("extra",), default=8.0)
            elif name in CHIP_HAND_JOKERS and hand_type == CHIP_HAND_JOKERS[name]:
                chips += self._joker_number([joker], name, ("t_chips",), ("extra",), default=50.0)
            elif name == "Half Joker":
                max_size = int(round(self._joker_number([joker], name, ("extra", "size"), default=3.0)))
                if len(played_cards) <= max_size:
                    mult += self._joker_number([joker], name, ("extra", "mult"), ("mult",), default=20.0)
            elif name == "Banner" and state is not None:
                chips += self._joker_number([joker], name, ("extra",), default=30.0) * max(0, state.economy.discards_left)
            elif name == "Mystic Summit" and state is not None and state.economy.discards_left <= 0:
                mult += self._joker_number([joker], name, ("extra",), ("mult",), default=15.0)
            elif name == "Abstract Joker":
                chips_per = self._joker_number([joker], name, ("extra",), default=3.0)
                mult += chips_per * len(active_jokers)
            elif name == "Blue Joker":
                chips += self._joker_number([joker], name, ("extra",), default=2.0) * total_cards
            elif name in PERSISTENT_MULT_JOKERS:
                mult += self._joker_number([joker], name, ("mult",), ("extra", "mult"), default=0.0)
            elif name == "Bootstraps" and state is not None:
                mult_per_step = self._joker_number([joker], name, ("extra", "mult"), default=2.0)
                dollars_per_step = max(1.0, self._joker_number([joker], name, ("extra", "dollars"), default=5.0))
                mult += mult_per_step * float(int(state.economy.money // dollars_per_step))
            elif name == "Supernova":
                mult += max(
                    self._joker_number([joker], name, ("mult",), ("extra",), default=0.0),
                    float(hand_played_count),
                )
            elif name == "Ride the Bus" and played_faces <= 0:
                mult += self._joker_number([joker], name, ("mult",), ("extra",), default=0.0)
            elif name in PERSISTENT_CHIP_JOKERS:
                chips += self._joker_number([joker], name, ("chips",), ("extra", "chips"), default=0.0)
            elif name == "Bull" and state is not None:
                chips += self._joker_number([joker], name, ("extra",), default=2.0) * float(state.economy.money)
            elif name == "Blackboard" and all_held_black:
                x_mult *= max(1.0, self._joker_number([joker], name, ("extra",), ("x_mult",), default=3.0))
            elif name == "Acrobat" and state is not None and state.economy.hands_left <= 1:
                x_mult *= max(1.0, self._joker_number([joker], name, ("extra",), ("x_mult",), default=3.0))
            elif name == "Card Sharp" and hand_played_this_round >= 1:
                x_mult *= max(1.0, self._joker_number([joker], name, ("extra",), ("x_mult",), default=3.0))
            elif name == "Baron":
                king_count = sum(1 for card in active_held_cards if self._card_rank_value(card) == 13)
                if king_count > 0:
                    x_mult *= max(1.0, self._joker_number([joker], name, ("extra",), ("x_mult",), default=1.5)) ** king_count
            elif name == "Driver's License" and state is not None and self._count_enhanced_cards(state) >= 16:
                x_mult *= max(1.0, self._joker_number([joker], name, ("extra",), ("x_mult",), default=3.0))
            elif name in PERSISTENT_XMULT_JOKERS:
                x_mult *= max(1.0, self._joker_number([joker], name, ("x_mult",), ("Xmult",), ("extra",), default=1.0))
            elif name == "Steel Joker":
                x_amount = self._joker_number([joker], name, ("x_mult",), default=0.0)
                if x_amount > 1.0:
                    x_mult *= x_amount
                else:
                    steel_tally = self._joker_number([joker], name, ("steel_tally",), default=0.0)
                    increment = self._joker_number([joker], name, ("extra",), default=0.2)
                    x_mult *= max(1.0, 1.0 + (increment * steel_tally))
            elif name == "Stone Joker":
                chip_amount = self._joker_number([joker], name, ("chips",), default=0.0)
                if chip_amount > 0.0:
                    chips += chip_amount
                else:
                    stone_tally = self._joker_number([joker], name, ("stone_tally",), default=0.0)
                    increment = self._joker_number([joker], name, ("extra",), default=25.0)
                    chips += increment * stone_tally
            chips, mult, x_mult = self._apply_edition(joker.edition, chips, mult, x_mult)

        final_score = max(0.0, chips * mult * x_mult)
        return int(round(final_score))

    def estimate_money_delta(
        self,
        played_cards: List[Card],
        held_cards: List[Card],
        jokers: List[Joker],
        state: Optional[BalatroState] = None,
    ) -> float:
        active_jokers = [joker for joker in jokers if not joker.is_debuffed]
        if not played_cards:
            return 0.0

        _, scoring_cards = self.classify_hand(played_cards, active_jokers)
        if self._has_joker(active_jokers, "Splash"):
            scoring_cards = list(played_cards)
        scoring_cards = [
            card for card in scoring_cards if not self._card_is_debuffed(card, state, active_jokers)
        ]

        money_delta = 0.0
        if self._has_joker(active_jokers, "Rough Gem"):
            per_card = self._joker_number(active_jokers, "Rough Gem", ("extra",), default=1.0)
            money_delta += per_card * sum(
                1 for card in scoring_cards if self._card_matches_suit(card, "Diamonds", active_jokers)
            )
        return money_delta

    def classify_hand(
        self,
        cards: List[Card],
        jokers: Optional[List[Joker]] = None,
    ) -> Tuple[str, List[Card]]:
        if not cards:
            return "High Card", []

        jokers = [joker for joker in (jokers or []) if not joker.is_debuffed]
        for hand_name in HAND_PRIORITY:
            subset = self._best_subset_for_hand(hand_name, cards, jokers)
            if subset:
                return hand_name, subset
        return "High Card", [max(cards, key=self._card_sort_key)]

    def _best_subset_for_hand(self, hand_name: str, cards: List[Card], jokers: List[Joker]) -> List[Card]:
        best_subset: List[Card] = []
        max_size = min(5, len(cards))
        for size in range(1, max_size + 1):
            for subset in _ordered_subsets(cards, size):
                if self._subset_matches_hand(hand_name, subset, jokers):
                    if not best_subset or self._subset_sort_key(subset) > self._subset_sort_key(best_subset):
                        best_subset = subset
        return best_subset

    def _subset_matches_hand(self, hand_name: str, subset: List[Card], jokers: List[Joker]) -> bool:
        rank_counts = Counter(card.rank for card in subset if not self._is_stone(card))
        count_values = sorted(rank_counts.values(), reverse=True)
        is_flush = self._is_flush_subset(subset, jokers)
        is_straight = self._is_straight_subset(subset, jokers)

        if hand_name == "Flush Five":
            return len(subset) == 5 and is_flush and count_values == [5]
        if hand_name == "Flush House":
            return len(subset) == 5 and is_flush and count_values == [3, 2]
        if hand_name == "Five of a Kind":
            return len(subset) == 5 and count_values == [5]
        if hand_name == "Straight Flush":
            return is_flush and is_straight
        if hand_name == "Four of a Kind":
            return len(subset) == 4 and count_values == [4]
        if hand_name == "Full House":
            return len(subset) == 5 and count_values == [3, 2]
        if hand_name == "Flush":
            return is_flush
        if hand_name == "Straight":
            return is_straight
        if hand_name == "Three of a Kind":
            return len(subset) == 3 and count_values == [3]
        if hand_name == "Two Pair":
            return len(subset) == 4 and count_values == [2, 2]
        if hand_name == "Pair":
            return len(subset) == 2 and count_values == [2]
        if hand_name == "High Card":
            return len(subset) == 1
        return False

    def _is_flush_subset(self, subset: List[Card], jokers: List[Joker]) -> bool:
        required = self._flush_requirement(jokers)
        if len(subset) < required:
            return False
        return any(all(self._card_matches_suit(card, suit, jokers) for card in subset) for suit in SUITS)

    def _is_straight_subset(self, subset: List[Card], jokers: List[Joker]) -> bool:
        required = self._straight_requirement(jokers)
        if len(subset) < required:
            return False
        if any(self._is_stone(card) for card in subset):
            return False

        values = [self._card_rank_value(card) for card in subset]
        if len(set(values)) != len(values):
            return False

        can_skip = self._has_joker(jokers, "Shortcut")
        return self._values_form_straight(values, can_skip)

    def _values_form_straight(self, values: Sequence[int], can_skip: bool) -> bool:
        ordered = sorted(values, reverse=True)
        if self._straight_run_ok(ordered, can_skip):
            return True
        if 14 not in ordered:
            return False
        ace_low = sorted(((1 if value == 14 else value) for value in values), reverse=True)
        return self._straight_run_ok(ace_low, can_skip)

    def _straight_run_ok(self, values: Sequence[int], can_skip: bool) -> bool:
        skip_used = False
        for left, right in zip(values, values[1:]):
            gap = left - right
            if gap == 1:
                continue
            if can_skip and not skip_used and gap == 2:
                skip_used = True
                continue
            return False
        return True

    def _flush_requirement(self, jokers: List[Joker]) -> int:
        return 4 if self._has_joker(jokers, "Four Fingers") else 5

    def _straight_requirement(self, jokers: List[Joker]) -> int:
        return 4 if self._has_joker(jokers, "Four Fingers") else 5

    def _hand_level(self, hand_name: str, state: Optional[BalatroState]) -> Tuple[float, float]:
        base_chips, base_mult = self.BASE_SCORES.get(hand_name, self.BASE_SCORES["High Card"])
        if state is None:
            return float(base_chips), float(base_mult)
        info = state.hand_levels.get(hand_name)
        if info is None:
            return float(base_chips), float(base_mult)
        return float(info.chips or base_chips), float(info.mult or base_mult)

    def _deck_card_count(
        self,
        state: Optional[BalatroState],
        played_cards: Sequence[Card],
        held_cards: Sequence[Card],
    ) -> int:
        if state is None:
            return len(played_cards) + len(held_cards)
        visible_total = len(state.hand) + len(state.deck) + len(state.discard_pile)
        if visible_total > 0:
            return visible_total
        return len(played_cards) + len(held_cards)

    def _hand_played_count(self, state: Optional[BalatroState], hand_name: str) -> int:
        if state is None:
            return 0
        info = state.hand_levels.get(hand_name)
        return int(info.played) if info is not None else 0

    def _hand_played_this_round(self, state: Optional[BalatroState], hand_name: str) -> int:
        if state is None:
            return 0
        info = state.hand_levels.get(hand_name)
        return int(info.played_this_round) if info is not None else 0

    def _card_chip_bonus(self, card: Card) -> float:
        enhancement = _normalize_enhancement(card.enhancement)
        if enhancement == "stone":
            return float(card.base_chips or 50)
        chips = float(card.base_chips)
        if enhancement == "bonus":
            chips += 30.0
        return chips

    def _card_mult_bonus(self, card: Card) -> float:
        enhancement = _normalize_enhancement(card.enhancement)
        if enhancement == "mult":
            return 4.0
        if enhancement == "lucky":
            return 4.0
        return 0.0

    def _card_x_mult(self, card: Card) -> float:
        enhancement = _normalize_enhancement(card.enhancement)
        if enhancement == "glass":
            return 2.0
        return 1.0

    def _held_card_x_mult(self, card: Card) -> float:
        if _normalize_enhancement(card.enhancement) == "steel":
            return 1.5
        return 1.0

    def _apply_edition(self, edition: str, chips: float, mult: float, x_mult: float) -> Tuple[float, float, float]:
        edition_name = _normalize_text(edition).lower()
        if edition_name == "foil":
            chips += 50.0
        elif edition_name in {"holo", "holographic"}:
            mult += 10.0
        elif edition_name == "polychrome":
            x_mult *= 1.5
        return chips, mult, x_mult

    def _has_joker(self, jokers: Sequence[Joker], name: str) -> bool:
        return any(joker.name == name and not joker.is_debuffed for joker in jokers)

    def _joker_by_name(self, jokers: Sequence[Joker], name: str) -> Optional[Joker]:
        return next((joker for joker in jokers if joker.name == name and not joker.is_debuffed), None)

    def _joker_number(
        self,
        jokers: Sequence[Joker],
        name: str,
        *paths: Tuple[str, ...],
        default: float,
    ) -> float:
        joker = self._joker_by_name(jokers, name)
        if joker is None:
            return default

        for path in paths:
            value = self._lookup_path(joker.internal_state, path)
            if value is not None:
                return _extract_number(value, default)
        return default

    def _lookup_path(self, mapping: Dict[str, Any], path: Tuple[str, ...]) -> Any:
        current: Any = mapping
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def _is_stone(self, card: Card) -> bool:
        return _normalize_enhancement(card.enhancement) == "stone"

    def _is_wild(self, card: Card) -> bool:
        return _normalize_enhancement(card.enhancement) == "wild"

    def _card_rank_value(self, card: Card) -> int:
        if self._is_stone(card):
            return 0
        return get_rank_value(card.rank)

    def _is_face_card(self, card: Card, jokers: Sequence[Joker]) -> bool:
        return card.rank in FACE_RANKS or self._has_joker(jokers, "Pareidolia")

    def _count_enhanced_cards(self, state: BalatroState) -> int:
        return sum(
            1
            for card in list(getattr(state, "hand", [])) + list(getattr(state, "deck", [])) + list(getattr(state, "discard_pile", []))
            if _normalize_enhancement(card.enhancement) != "none" or _normalize_text(card.edition) != "None" or _normalize_text(card.seal) != "None"
        )

    def _joker_current_suit(self, jokers: Sequence[Joker], name: str) -> str:
        joker = self._joker_by_name(jokers, name)
        if joker is None:
            return ""
        return self._find_suit_value(joker.internal_state)

    def _find_suit_value(self, value: Any) -> str:
        if isinstance(value, str):
            normalized = _normalize_text(value)
            return normalized if normalized in SUITS else ""
        if isinstance(value, dict):
            for nested in value.values():
                suit = self._find_suit_value(nested)
                if suit:
                    return suit
        if isinstance(value, (list, tuple)):
            for nested in value:
                suit = self._find_suit_value(nested)
                if suit:
                    return suit
        return ""

    def _card_matches_suit(self, card: Card, suit: str, jokers: Sequence[Joker]) -> bool:
        if self._is_stone(card):
            return False
        if self._is_wild(card):
            return True
        if self._has_joker(jokers, "Smeared Joker"):
            return ((card.suit in RED_SUITS) == (suit in RED_SUITS)) or ((card.suit in BLACK_SUITS) == (suit in BLACK_SUITS))
        return card.suit == suit

    def _card_is_black(self, card: Card, jokers: Sequence[Joker]) -> bool:
        if self._is_stone(card):
            return False
        if self._is_wild(card):
            return True
        return card.suit in BLACK_SUITS

    def _card_is_debuffed(
        self,
        card: Card,
        state: Optional[BalatroState],
        jokers: Sequence[Joker],
    ) -> bool:
        if card.is_debuffed:
            return True
        profile = boss_profile_from_state(state)
        if profile.face_cards_debuffed and self._is_face_card(card, jokers):
            return True
        if profile.debuffed_suit and self._card_matches_suit(card, profile.debuffed_suit, jokers):
            return True
        return False

    def _subset_sort_key(self, subset: Sequence[Card]) -> Tuple:
        rank_values = tuple(sorted((self._card_rank_value(card) for card in subset), reverse=True))
        card_value = sum(
            (50.0 if self._is_stone(card) else float(card.base_chips))
            + (5.0 if card.edition != "None" else 0.0)
            + (6.0 if _normalize_enhancement(card.enhancement) != "none" else 0.0)
            for card in subset
        )
        return (
            len(subset),
            card_value,
            rank_values,
            tuple(sorted(card.id for card in subset)),
        )

    def _card_sort_key(self, card: Card) -> Tuple:
        return (
            self._card_rank_value(card),
            float(card.base_chips),
            card.id,
        )
