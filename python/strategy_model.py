import math
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, Tuple

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
    "Jupiter": {"flush": 2.4},
    "Saturn": {"straight": 2.4},
    "Earth": {"small_hand": 0.3},
    "Mars": {"small_hand": 0.2},
    "Neptune": {"straight": 1.4, "flush": 1.4},
    "Planet X": {"small_hand": 0.2, "deck_growth": 0.4},
    "Ceres": {"flush": 1.8},
    "Eris": {"flush": 2.0},
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
            }

        suit_counts = Counter(card.suit for card in cards)
        rank_counts = Counter(card.rank for card in cards)
        face_cards = sum(1 for card in cards if card.rank in {"Jack", "Queen", "King"})
        steel_cards = sum(1 for card in cards if card.enhancement == "Steel")
        blue_seals = sum(1 for card in cards if card.seal == "Blue")
        deck_count = float(len(cards))
        rank_duplication = sum(max(0, count - 1) for count in rank_counts.values()) / deck_count
        return {
            "deck_count": deck_count,
            "max_suit_share": max(suit_counts.values()) / deck_count,
            "face_ratio": face_cards / deck_count,
            "steel_ratio": steel_cards / deck_count,
            "blue_seal_ratio": blue_seals / deck_count,
            "rank_duplication": rank_duplication,
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
        preferred_hand = self._preferred_hand(state)
        stake = float(state.meta.stake or 1)

        scores["economy"] += 0.3 * stake
        scores["small_hand"] += 0.25 * stake

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

        if state.economy.money >= 25:
            scores["economy"] += 1.2
        if state.economy.discards_left <= 1:
            scores["small_hand"] += 0.8
            scores["straight"] -= 0.3
            scores["flush"] -= 0.2

        for joker in state.jokers:
            for archetype, weight in JOKER_EVIDENCE.get(joker.name, {}).items():
                scores[archetype] += weight
            if joker.is_rental:
                scores["economy"] += 0.5

        posterior = _softmax(scores)
        ranked = sorted(posterior.items(), key=lambda pair: pair[1], reverse=True)
        return {
            "preferred_hand": preferred_hand,
            "scores": scores,
            "posterior": posterior,
            "ranked_archetypes": ranked,
            "deck_metrics": deck_metrics,
        }

    def _item_vector(self, item: ShopItemState) -> Dict[str, float]:
        if item.set == "Planet":
            return PLANET_TO_ARCHETYPE.get(item.name, {})
        return ITEM_VECTORS.get(item.name, {})

    def score_item(self, state: BalatroState, item: ShopItemState, inference: Dict[str, Any]) -> Dict[str, Any]:
        vector = self._item_vector(item)
        posterior = inference["posterior"]
        expected_synergy = sum(posterior.get(arch, 0.0) * weight for arch, weight in vector.items())
        base = 0.0

        if item.set == "Voucher":
            base = 6.0
        elif item.set == "Joker":
            base = 4.5
        elif item.set == "Planet":
            base = 3.0
        else:
            base = -1.5

        if item.name in {"Seed Money", "Money Tree", "To the Moon"} and state.economy.money < 20:
            base += 1.5
        if item.name in {"Grabber", "Nacho Tong"} and state.meta.stake and state.meta.stake >= 5:
            base += 1.0
        if item.name in {"Telescope", "Observatory"} and inference["preferred_hand"] in {"High Card", "Pair", "Flush", "Straight"}:
            base += 1.2

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

        cost_penalty = max(0.0, item.cost - 4) * 0.35
        total = base + expected_synergy * 4.0 + edition_bonus + stage_bonus - sticker_penalty - cost_penalty
        return {
            "base": base,
            "expected_synergy": expected_synergy,
            "edition_bonus": edition_bonus,
            "stage_bonus": stage_bonus,
            "sticker_penalty": sticker_penalty,
            "cost_penalty": cost_penalty,
            "total": total,
            "vector": vector,
        }
