import math
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, Tuple

from boss_logic import boss_profile_from_state, locked_hand_type
from run_planner import RunPlanner
from state import BalatroState, Card, ShopItemState


ARCHETYPES = (
    "economy",
    "small_hand",
    "held_in_hand",
    "flush",
    "straight",
    "deck_growth",
    "face_cards",
)


JOKER_EVIDENCE = {
    "Blue Joker": {"small_hand": 1.0, "deck_growth": 2.2},
    "Green Joker": {"small_hand": 2.4, "economy": 0.5},
    "Half Joker": {"small_hand": 2.0},
    "Joker": {"small_hand": 0.8},
    "Jolly Joker": {"small_hand": 1.8},
    "Sly Joker": {"small_hand": 1.8},
    "Supernova": {"small_hand": 1.2},
    "Square Joker": {"small_hand": 1.8},
    "Banner": {"small_hand": 0.8, "economy": 0.4},
    "Raised Fist": {"small_hand": 1.2, "held_in_hand": 2.0},
    "Blackboard": {"small_hand": 1.6, "flush": 0.6},
    "Burnt Joker": {"small_hand": 1.8, "flush": 0.6, "straight": 0.6},
    "Mime": {"held_in_hand": 3.0},
    "Baron": {"held_in_hand": 3.4, "face_cards": 2.4},
    "Shoot the Moon": {"held_in_hand": 2.2, "face_cards": 2.0},
    "Reserved Parking": {"held_in_hand": 1.8, "face_cards": 1.5, "economy": 1.0},
    "Steel Joker": {"held_in_hand": 3.0},
    "Arrowhead": {"flush": 2.8},
    "Bloodstone": {"flush": 2.8},
    "Onyx Agate": {"flush": 2.6},
    "Rough Gem": {"flush": 2.6, "economy": 0.7},
    "Smeared Joker": {"flush": 2.8},
    "Crafty Joker": {"flush": 1.8},
    "Droll Joker": {"flush": 1.8},
    "Ancient Joker": {"flush": 2.0},
    "The Tribe": {"flush": 2.4},
    "Four Fingers": {"straight": 2.8, "flush": 1.0},
    "Shortcut": {"straight": 3.0},
    "Runner": {"straight": 2.4},
    "Superposition": {"straight": 2.0},
    "Seance": {"straight": 1.7},
    "Crazy Joker": {"straight": 1.8},
    "Devious Joker": {"straight": 1.8},
    "The Order": {"straight": 2.4},
    "Hologram": {"deck_growth": 3.0},
    "DNA": {"deck_growth": 2.4, "small_hand": 0.6},
    "Certificate": {"deck_growth": 2.1},
    "Marble Joker": {"deck_growth": 1.7, "flush": 0.4},
    "To the Moon": {"economy": 2.8},
    "Rocket": {"economy": 2.1},
    "Golden Joker": {"economy": 1.8},
    "Delayed Gratification": {"economy": 2.2},
    "Bull": {"economy": 1.8},
    "Photograph": {"face_cards": 2.4},
    "Smiley Face": {"face_cards": 2.0},
    "Pareidolia": {"face_cards": 2.2},
}


ITEM_VECTORS = {
    "Joker": {"small_hand": 0.8},
    "Half Joker": {"small_hand": 2.2},
    "Blue Joker": {"small_hand": 1.2, "deck_growth": 2.4},
    "Green Joker": {"small_hand": 2.6, "economy": 0.5},
    "Raised Fist": {"small_hand": 1.0, "held_in_hand": 2.1},
    "Blackboard": {"small_hand": 1.7, "flush": 0.7},
    "Mime": {"held_in_hand": 3.2},
    "Baron": {"held_in_hand": 3.3, "face_cards": 2.6},
    "Shoot the Moon": {"held_in_hand": 2.2, "face_cards": 2.0},
    "Reserved Parking": {"held_in_hand": 1.7, "economy": 1.1, "face_cards": 1.4},
    "Steel Joker": {"held_in_hand": 3.1},
    "Arrowhead": {"flush": 2.8},
    "Bloodstone": {"flush": 2.9},
    "Onyx Agate": {"flush": 2.7},
    "Rough Gem": {"flush": 2.4, "economy": 0.8},
    "Smeared Joker": {"flush": 3.0},
    "Crafty Joker": {"flush": 1.7},
    "Droll Joker": {"flush": 1.7},
    "Ancient Joker": {"flush": 2.0},
    "The Tribe": {"flush": 2.5},
    "Four Fingers": {"straight": 2.8, "flush": 1.0},
    "Shortcut": {"straight": 3.0},
    "Runner": {"straight": 2.3},
    "Superposition": {"straight": 1.9},
    "Seance": {"straight": 1.7},
    "Crazy Joker": {"straight": 1.8},
    "Devious Joker": {"straight": 1.8},
    "The Order": {"straight": 2.4},
    "Hologram": {"deck_growth": 3.2},
    "DNA": {"deck_growth": 2.5, "small_hand": 0.7},
    "Certificate": {"deck_growth": 2.1},
    "Marble Joker": {"deck_growth": 1.8},
    "To the Moon": {"economy": 2.9},
    "Rocket": {"economy": 2.2},
    "Golden Joker": {"economy": 1.7},
    "Delayed Gratification": {"economy": 2.1},
    "Bull": {"economy": 1.8},
    "Photograph": {"face_cards": 2.3},
    "Smiley Face": {"face_cards": 2.1},
    "Pareidolia": {"face_cards": 2.2},
    "Blueprint": {"small_hand": 0.8, "held_in_hand": 0.8, "flush": 0.8, "straight": 0.8, "deck_growth": 0.8, "face_cards": 0.8},
    "Brainstorm": {"small_hand": 0.8, "held_in_hand": 0.8, "flush": 0.8, "straight": 0.8, "deck_growth": 0.8, "face_cards": 0.8},
    "Seed Money": {"economy": 3.2},
    "Money Tree": {"economy": 3.6},
    "Reroll Surplus": {"economy": 1.9},
    "Reroll Glut": {"economy": 2.4},
    "Grabber": {"small_hand": 1.3, "straight": 0.9, "flush": 0.9},
    "Nacho Tong": {"small_hand": 1.5, "straight": 1.0, "flush": 1.0},
    "Wasteful": {"straight": 1.2, "flush": 1.0},
    "Recyclomancy": {"straight": 1.4, "flush": 1.2},
    "Telescope": {"small_hand": 2.2, "flush": 1.6, "straight": 1.6},
    "Observatory": {"small_hand": 2.4, "flush": 1.8, "straight": 1.8, "held_in_hand": 0.4},
    "Paint Brush": {"straight": 1.2, "flush": 1.2, "held_in_hand": 0.6},
    "Palette": {"straight": 1.4, "flush": 1.4, "held_in_hand": 0.8},
    "Antimatter": {"small_hand": 1.3, "held_in_hand": 1.3, "flush": 1.3, "straight": 1.3, "deck_growth": 1.3, "face_cards": 1.3},
}


PLANET_TO_ARCHETYPE = {
    "Pluto": {"small_hand": 1.8},
    "Mercury": {"small_hand": 2.0},
    "Uranus": {"small_hand": 1.2},
    "Venus": {"small_hand": 0.7, "deck_growth": 0.3},
    "Earth": {"small_hand": 0.8, "deck_growth": 0.2},
    "Mars": {"small_hand": 0.6, "deck_growth": 0.4},
    "Jupiter": {"flush": 2.4},
    "Saturn": {"straight": 2.4},
    "Neptune": {"straight": 1.4, "flush": 1.4},
    "Planet X": {"small_hand": 0.4, "deck_growth": 0.8},
    "Ceres": {"flush": 1.8},
    "Eris": {"flush": 2.0},
}

CONSUMABLE_EVIDENCE = {
    "Hermit": {"economy": 1.8},
    "Temperance": {"economy": 1.8},
    "Judgement": {"deck_growth": 0.8, "small_hand": 0.4},
    "Death": {"deck_growth": 1.2, "small_hand": 0.5, "flush": 0.4, "straight": 0.4},
    "Hanged Man": {"deck_growth": 0.8, "small_hand": 0.4, "flush": 0.3, "straight": 0.3},
    "High Priestess": {"small_hand": 1.0, "flush": 0.8, "straight": 0.8},
    "The Fool": {"deck_growth": 0.8, "economy": 0.4},
    "Hex": {"deck_growth": 0.8, "held_in_hand": 0.4, "face_cards": 0.2},
    "Immolate": {"economy": 0.8, "deck_growth": 1.0},
    "Black Hole": {"small_hand": 1.0, "flush": 0.8, "straight": 0.8},
}

BOOSTER_KIND_VECTORS = {
    "Arcana": {"economy": 0.8, "small_hand": 0.7, "flush": 0.5, "straight": 0.5, "deck_growth": 1.0},
    "Celestial": {"small_hand": 1.0, "flush": 1.0, "straight": 1.0},
    "Spectral": {"deck_growth": 1.3, "held_in_hand": 0.6, "face_cards": 0.3},
    "Standard": {"deck_growth": 1.1, "held_in_hand": 0.7, "flush": 0.5, "straight": 0.5, "face_cards": 0.4},
    "Buffoon": {"economy": 0.4, "small_hand": 1.0, "held_in_hand": 1.0, "flush": 1.0, "straight": 1.0, "deck_growth": 0.5, "face_cards": 0.7},
}


DECK_PRIORS = {
    "b_red": {"flush": 0.7, "straight": 0.7, "deck_growth": 0.3},
    "b_blue": {"small_hand": 0.8, "held_in_hand": 0.5},
    "b_yellow": {"economy": 2.2, "small_hand": 0.2},
    "b_green": {"small_hand": 1.1, "flush": 0.5, "straight": 0.5, "economy": -0.8},
    "b_black": {"small_hand": 0.8, "deck_growth": 0.9, "economy": -0.2},
    "b_magic": {"economy": 0.9, "deck_growth": 0.4, "small_hand": 0.3},
    "b_nebula": {"small_hand": 0.6, "flush": 0.9, "straight": 1.1},
    "b_ghost": {"held_in_hand": 0.6, "deck_growth": 0.6},
    "b_abandoned": {"small_hand": 2.2, "straight": 0.8, "face_cards": -5.0},
    "b_checkered": {"flush": 3.4, "straight": -0.2},
    "b_zodiac": {"economy": 1.2, "flush": 0.5, "straight": 0.5, "small_hand": 0.5},
    "b_painted": {"held_in_hand": 0.9, "flush": 0.8, "straight": 0.8},
    "b_anaglyph": {"economy": 0.6, "deck_growth": 0.4},
    "b_plasma": {"small_hand": 0.7, "deck_growth": 0.6, "economy": 0.3},
    "b_erratic": {"small_hand": 1.0, "flush": 0.4, "straight": 0.4, "deck_growth": 0.5},
}

DECK_ALIASES = {
    "red deck": "b_red",
    "blue deck": "b_blue",
    "yellow deck": "b_yellow",
    "green deck": "b_green",
    "black deck": "b_black",
    "magic deck": "b_magic",
    "nebula deck": "b_nebula",
    "ghost deck": "b_ghost",
    "abandoned deck": "b_abandoned",
    "checkered deck": "b_checkered",
    "zodiac deck": "b_zodiac",
    "painted deck": "b_painted",
    "anaglyph deck": "b_anaglyph",
    "plasma deck": "b_plasma",
    "erratic deck": "b_erratic",
}

DECK_FLAGS = {
    "b_red": {"extra_discards": True},
    "b_blue": {"extra_hands": True},
    "b_yellow": {"cash_start_bonus": True},
    "b_green": {"spend_aggressively": True, "ignore_interest": True, "tempo_deck": True},
    "b_black": {"need_early_tempo": True, "joker_capacity_bonus": True},
    "b_magic": {"consumable_start": True},
    "b_nebula": {"planet_focused": True},
    "b_ghost": {"spectral_focused": True},
    "b_abandoned": {"face_suppressed": True},
    "b_checkered": {"flush_focused": True},
    "b_zodiac": {"voucher_start": True},
    "b_painted": {"large_hand": True},
    "b_anaglyph": {"tag_value_bias": True},
    "b_plasma": {"high_scaling_pressure": True},
    "b_erratic": {"volatile_deck": True},
}

FLUSH_ITEM_NAMES = {
    "Arrowhead",
    "Bloodstone",
    "Onyx Agate",
    "Rough Gem",
    "Smeared Joker",
    "Crafty Joker",
    "Droll Joker",
    "Ancient Joker",
    "The Tribe",
    "Jupiter",
    "Ceres",
    "Eris",
}

STRAIGHT_ITEM_NAMES = {
    "Four Fingers",
    "Shortcut",
    "Runner",
    "Superposition",
    "Seance",
    "Crazy Joker",
    "Devious Joker",
    "The Order",
    "Saturn",
    "Neptune",
}

FACE_ITEM_NAMES = {
    "Baron",
    "Photograph",
    "Smiley Face",
    "Reserved Parking",
    "Shoot the Moon",
    "Scholar",
}


def _softmax(scores: Dict[str, float]) -> Dict[str, float]:
    max_score = max(scores.values())
    exps = {name: math.exp(value - max_score) for name, value in scores.items()}
    total = sum(exps.values())
    return {name: exps[name] / total for name in scores}


def _full_deck_cards(state: BalatroState) -> Iterable[Card]:
    cards = []
    cards.extend(state.hand)
    cards.extend(state.deck)
    cards.extend(state.discard_pile)
    return cards


class StrategyModel:
    def __init__(self):
        self.run_planner = RunPlanner()

    def _deck_identity(self, state: BalatroState) -> Tuple[str, str]:
        deck_key = str(getattr(state.meta, "deck_key", "") or "").strip().lower()
        deck_name = str(getattr(state.meta, "deck_name", "") or "").strip()
        if not deck_key and deck_name:
            deck_key = DECK_ALIASES.get(deck_name.lower(), "")
        return deck_key, deck_name

    def _deck_profile(self, state: BalatroState) -> Dict[str, Any]:
        deck_key, deck_name = self._deck_identity(state)
        return {
            "deck_key": deck_key,
            "deck_name": deck_name,
            "priors": dict(DECK_PRIORS.get(deck_key, {})),
            "flags": dict(DECK_FLAGS.get(deck_key, {})),
        }

    def _deck_metrics(self, state: BalatroState) -> Dict[str, float]:
        cards = list(_full_deck_cards(state))
        if not cards:
            cards = list(state.hand)
        if not cards:
            return {
                "deck_count": 0.0,
                "max_suit_share": 0.0,
                "face_ratio": 0.0,
                "steel_ratio": 0.0,
                "blue_seal_ratio": 0.0,
                "rank_duplication": 0.0,
                "exact_duplication": 0.0,
            }

        suit_counts = Counter(card.suit for card in cards)
        rank_counts = Counter(card.rank for card in cards)
        exact_counts = Counter(
            (
                card.rank,
                card.suit,
                card.base_chips,
                card.enhancement,
                card.edition,
                card.seal,
            )
            for card in cards
        )
        face_cards = sum(1 for card in cards if card.rank in {"Jack", "Queen", "King"})
        steel_cards = sum(1 for card in cards if card.enhancement == "Steel")
        blue_seals = sum(1 for card in cards if card.seal == "Blue")
        deck_count = float(len(cards))
        rank_duplication = sum(max(0, count - 1) for count in rank_counts.values()) / deck_count
        exact_duplication = sum(max(0, count - 1) for count in exact_counts.values()) / deck_count
        return {
            "deck_count": deck_count,
            "max_suit_share": max(suit_counts.values()) / deck_count,
            "face_ratio": face_cards / deck_count,
            "steel_ratio": steel_cards / deck_count,
            "blue_seal_ratio": blue_seals / deck_count,
            "rank_duplication": rank_duplication,
            "exact_duplication": exact_duplication,
        }

    def _draw_metrics(self, state: BalatroState) -> Dict[str, float]:
        draw_cards = list(getattr(state, "deck", []))
        if not draw_cards:
            return {
                "draw_count": 0.0,
                "draw_max_suit_share": 0.0,
                "draw_face_ratio": 0.0,
                "draw_rank_duplication": 0.0,
                "draw_enhanced_ratio": 0.0,
                "draw_exact_duplication": 0.0,
            }

        suit_counts = Counter(card.suit for card in draw_cards)
        rank_counts = Counter(card.rank for card in draw_cards)
        exact_counts = Counter(
            (
                card.rank,
                card.suit,
                card.base_chips,
                card.enhancement,
                card.edition,
                card.seal,
            )
            for card in draw_cards
        )
        face_cards = sum(1 for card in draw_cards if card.rank in {"Jack", "Queen", "King"})
        enhanced_cards = sum(
            1
            for card in draw_cards
            if card.enhancement != "None" or card.edition != "None" or card.seal != "None"
        )
        draw_count = float(len(draw_cards))
        rank_duplication = sum(max(0, count - 1) for count in rank_counts.values()) / draw_count
        exact_duplication = sum(max(0, count - 1) for count in exact_counts.values()) / draw_count
        return {
            "draw_count": draw_count,
            "draw_max_suit_share": max(suit_counts.values()) / draw_count,
            "draw_face_ratio": face_cards / draw_count,
            "draw_rank_duplication": rank_duplication,
            "draw_enhanced_ratio": enhanced_cards / draw_count,
            "draw_exact_duplication": exact_duplication,
        }

    def _preferred_hand(self, state: BalatroState) -> str:
        if not state.hand_levels:
            return "Pair"
        return max(
            state.hand_levels.items(),
            key=lambda pair: (pair[1].played * 2 + pair[1].level, pair[0]),
        )[0]

    def infer(self, state: BalatroState) -> Dict[str, Any]:
        scores = {name: 0.0 for name in ARCHETYPES}
        deck_metrics = self._deck_metrics(state)
        draw_metrics = self._draw_metrics(state)
        preferred_hand = self._preferred_hand(state)
        stake = float(state.meta.stake or 1)
        deck_profile = self._deck_profile(state)
        deck_flags = deck_profile["flags"]
        boss_profile = boss_profile_from_state(state).as_dict()
        boss_profile["locked_hand"] = locked_hand_type(state)

        scores["economy"] += 0.3 * stake
        scores["small_hand"] += 0.25 * stake
        if stake >= 5:
            scores["small_hand"] += 0.9
            if not deck_flags.get("flush_focused"):
                scores["flush"] -= 0.2
            scores["straight"] -= 0.1

        hand_bias = {
            "High Card": "small_hand",
            "Pair": "small_hand",
            "Two Pair": "small_hand",
            "Flush": "flush",
            "Straight": "straight",
            "Straight Flush": "straight",
            "Flush House": "flush",
            "Flush Five": "flush",
        }
        if preferred_hand in hand_bias:
            scores[hand_bias[preferred_hand]] += 2.0

        scores["flush"] += max(0.0, (deck_metrics["max_suit_share"] - 0.32) * 10.0)
        scores["face_cards"] += deck_metrics["face_ratio"] * 10.0
        scores["held_in_hand"] += deck_metrics["steel_ratio"] * 12.0 + deck_metrics["blue_seal_ratio"] * 8.0
        scores["deck_growth"] += max(0.0, (deck_metrics["deck_count"] - 52.0) / 6.0)
        scores["small_hand"] += deck_metrics["rank_duplication"] * 5.0
        scores["deck_growth"] += deck_metrics["exact_duplication"] * 8.0
        scores["flush"] += max(0.0, (draw_metrics["draw_max_suit_share"] - 0.30) * 6.0)
        scores["face_cards"] += draw_metrics["draw_face_ratio"] * 3.0
        scores["small_hand"] += draw_metrics["draw_rank_duplication"] * 3.5
        scores["deck_growth"] += draw_metrics["draw_enhanced_ratio"] * 1.5
        scores["deck_growth"] += draw_metrics["draw_exact_duplication"] * 5.0

        for archetype, weight in deck_profile["priors"].items():
            scores[archetype] += weight

        if state.economy.money >= 25:
            scores["economy"] += 1.2
        if state.economy.discards_left <= 1:
            scores["small_hand"] += 0.8
            scores["straight"] -= 0.3
            scores["flush"] -= 0.2
        if state.economy.hands_left >= 4:
            scores["small_hand"] += 0.4
        if state.economy.discards_left >= 4:
            scores["flush"] += 0.25
            scores["straight"] += 0.3
        if deck_flags.get("ignore_interest") or state.meta.no_interest:
            scores["economy"] -= 0.6
        if deck_flags.get("need_early_tempo"):
            scores["small_hand"] += 0.5
        if deck_flags.get("high_scaling_pressure"):
            scores["deck_growth"] += 0.4
        if deck_flags.get("extra_hands"):
            scores["small_hand"] += 0.5
        if deck_flags.get("extra_discards"):
            scores["flush"] += 0.35
            scores["straight"] += 0.35
        if deck_flags.get("large_hand"):
            scores["straight"] += 0.5

        if boss_profile.get("face_cards_debuffed"):
            scores["face_cards"] -= 14.0
            scores["held_in_hand"] -= 7.0
            scores["small_hand"] += 1.6
        if boss_profile.get("debuffed_suit"):
            scores["flush"] -= 0.5
        if boss_profile.get("require_five_card_play"):
            scores["small_hand"] -= 0.35
            scores["flush"] += 0.18
            scores["straight"] += 0.18
        if boss_profile.get("forbid_repeat_hands"):
            scores["deck_growth"] += 0.2
            scores["straight"] += 0.1
            scores["flush"] += 0.1
        if boss_profile.get("lock_to_first_hand_type"):
            locked = locked_hand_type(state)
            if locked == "Flush":
                scores["flush"] += 1.2
            elif locked == "Straight":
                scores["straight"] += 1.2
            elif locked:
                scores["small_hand"] += 1.2
        if boss_profile.get("immediate_clear_pressure"):
            scores["small_hand"] += float(boss_profile["immediate_clear_pressure"]) * 1.2

        for joker in state.jokers:
            for archetype, weight in JOKER_EVIDENCE.get(joker.name, {}).items():
                scores[archetype] += weight
            if joker.is_rental:
                scores["economy"] += 0.5

        for consumable in getattr(state, "consumables", []):
            for archetype, weight in CONSUMABLE_EVIDENCE.get(consumable.name, {}).items():
                scores[archetype] += weight

        posterior = _softmax(scores)
        ranked = sorted(posterior.items(), key=lambda pair: pair[1], reverse=True)
        run_plan = self.run_planner.build(
            state,
            preferred_hand=preferred_hand,
            posterior=posterior,
            deck_profile=deck_profile,
            deck_metrics=deck_metrics,
            draw_metrics=draw_metrics,
            boss_profile=boss_profile,
        )
        return {
            "preferred_hand": preferred_hand,
            "scores": scores,
            "posterior": posterior,
            "ranked_archetypes": ranked,
            "deck_metrics": deck_metrics,
            "draw_metrics": draw_metrics,
            "deck_profile": deck_profile,
            "boss_profile": boss_profile,
            "run_plan": run_plan,
        }

    def _item_vector(self, item: ShopItemState) -> Dict[str, float]:
        if item.set == "Planet":
            return PLANET_TO_ARCHETYPE.get(item.name, {})
        if item.set == "Booster":
            metadata = item.metadata or {}
            kind = str(metadata.get("kind") or "").strip()
            return BOOSTER_KIND_VECTORS.get(kind, {})
        return ITEM_VECTORS.get(item.name, {})

    def score_item(self, state: BalatroState, item: ShopItemState, inference: Dict[str, Any]) -> Dict[str, Any]:
        vector = self._item_vector(item)
        posterior = inference["posterior"]
        deck_profile = inference.get("deck_profile", {})
        deck_flags = deck_profile.get("flags", {})
        run_plan = inference.get("run_plan", {})
        expected_synergy = sum(posterior.get(arch, 0.0) * weight for arch, weight in vector.items())
        base = 0.0

        if item.set == "Voucher":
            base = 6.0
        elif item.set == "Joker":
            base = 4.5
        elif item.set == "Planet":
            base = 3.0
        elif item.set == "Booster":
            base = 2.8
        else:
            base = -1.5

        if item.name in {"Seed Money", "Money Tree", "To the Moon"} and state.economy.money < 20:
            base += 1.5
        if item.name in {"Grabber", "Nacho Tong"} and state.meta.stake and state.meta.stake >= 5:
            base += 1.0
        if item.name in {"Telescope", "Observatory"} and inference["preferred_hand"] in {"High Card", "Pair", "Flush", "Straight"}:
            base += 1.2
        if deck_flags.get("flush_focused") and item.name in FLUSH_ITEM_NAMES:
            base += 1.0
        if deck_flags.get("planet_focused") and item.set == "Planet":
            base += 0.8
        if deck_flags.get("need_early_tempo") and item.set == "Joker":
            base += 0.6
        if deck_flags.get("face_suppressed") and item.name in FACE_ITEM_NAMES:
            base -= 1.4
        if deck_flags.get("ignore_interest") and item.name in {"Seed Money", "Money Tree", "To the Moon"}:
            base -= 1.8
        if deck_flags.get("large_hand") and item.name in STRAIGHT_ITEM_NAMES.union(FLUSH_ITEM_NAMES):
            base += 0.6
        if item.set == "Booster":
            kind = str((item.metadata or {}).get("kind") or "")
            booster_pref = float(run_plan.get("pack_preferences", {}).get(kind, 0.0))
            base += booster_pref * 0.9
            if kind == "Buffoon" and (state.meta.ante or 1) <= 3:
                base += 1.0
            elif kind == "Celestial" and inference["preferred_hand"] in {"High Card", "Pair", "Flush", "Straight"}:
                base += 0.8
            elif kind == "Arcana":
                base += 0.7
            elif kind == "Spectral":
                base += 0.5
            elif kind == "Standard":
                base += 0.4
        if run_plan.get("target_hand") in {"Three of a Kind", "Full House", "Four of a Kind", "Five of a Kind"}:
            if item.name in {"Venus", "Earth", "Mars", "Planet X"}:
                base += 1.0
            if item.name in {"Death", "Hanged Man", "Certificate", "DNA", "Spare Trousers"}:
                base += 0.5

        edition_bonus = {
            "Foil": 0.8,
            "Holo": 1.2,
            "Holographic": 1.2,
            "Polychrome": 2.2,
            "Negative": 4.0,
        }.get(item.edition, 0.0)

        sticker_penalty = 0.0
        if item.is_rental:
            sticker_penalty += 4.0 if state.economy.money < 20 else 2.5
        if item.is_perishable:
            sticker_penalty += 2.0
        if item.is_eternal:
            sticker_penalty += 0.8

        ante = state.meta.ante or 1
        stage_bonus = 0.0
        if ante <= 2 and item.name in {"Joker", "Blue Joker", "Green Joker", "Half Joker", "Raised Fist"}:
            stage_bonus += 1.0
        if ante >= 4 and item.name in {"Hologram", "Baron", "Mime", "Steel Joker", "Observatory"}:
            stage_bonus += 0.8

        plan_adjustment = self.run_planner.score_item_adjustment(
            state,
            item,
            run_plan=run_plan,
            deck_flags=deck_flags,
        )
        cost_penalty = max(0.0, item.cost - 4) * 0.35
        total = (
            base
            + expected_synergy * 4.0
            + edition_bonus
            + stage_bonus
            + plan_adjustment["total"]
            - sticker_penalty
            - cost_penalty
        )
        return {
            "base": base,
            "expected_synergy": expected_synergy,
            "edition_bonus": edition_bonus,
            "stage_bonus": stage_bonus,
            "plan_adjustment": plan_adjustment,
            "sticker_penalty": sticker_penalty,
            "cost_penalty": cost_penalty,
            "total": total,
            "vector": vector,
        }
