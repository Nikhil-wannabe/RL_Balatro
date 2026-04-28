from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Mapping

from action_types import ActionResponse
from logging_utils import get_logger
from rank_utils import get_rank_value
from run_planner import DUPLICATE_HANDS, FLUSH_HANDS, SMALL_HANDS, STRAIGHT_HANDS
from state import BalatroState, Card, Joker, ShopItemState
from strategy_model import StrategyModel

logger = get_logger("Pack")


PLANET_TO_HAND = {
    "Pluto": "High Card",
    "Mercury": "Pair",
    "Uranus": "Two Pair",
    "Venus": "Three of a Kind",
    "Earth": "Full House",
    "Mars": "Four of a Kind",
    "Jupiter": "Flush",
    "Saturn": "Straight",
    "Neptune": "Straight Flush",
    "Planet X": "Five of a Kind",
    "Ceres": "Flush House",
    "Eris": "Flush Five",
}

KEEPER_JOKERS = {
    "Blueprint",
    "Brainstorm",
    "Hologram",
    "Card Sharp",
    "Baron",
    "Mime",
    "Steel Joker",
    "Constellation",
    "Cavendish",
    "Acrobat",
    "Photograph",
    "Blackboard",
    "Supernova",
    "Green Joker",
    "Ride the Bus",
    "Square Joker",
    "Runner",
}

FACE_RANKS = {"Jack", "Queen", "King"}
SMALL_HAND_TARGETS = {"High Card", "Pair", "Two Pair"}
HIGH_VALUE_TAROTS = {"Hermit", "Temperance", "Judgement", "Death", "Hanged Man", "The Fool", "High Priestess"}
HIGH_VALUE_SPECTRALS = {"The Soul", "Black Hole", "Hex", "Immolate", "Ankh", "Crypt", "Ectoplasm", "Wraith"}


def _all_cards(state: BalatroState) -> list[Card]:
    cards: list[Card] = []
    cards.extend(state.hand)
    cards.extend(state.deck)
    cards.extend(state.discard_pile)
    return cards


def _dominant_suit(cards: Iterable[Card]) -> str | None:
    suit_counts = Counter(card.suit for card in cards if card.suit and card.suit != "None")
    if not suit_counts:
        return None
    return max(suit_counts.items(), key=lambda pair: (pair[1], pair[0]))[0]


def _best_keeper_joker(jokers: Iterable[Joker]) -> Joker | None:
    ranked = []
    for joker in jokers:
        score = 0.0
        if joker.name in KEEPER_JOKERS:
            score += 3.0
        if joker.edition == "Negative":
            score += 1.5
        if joker.edition == "Polychrome":
            score += 1.2
        if joker.edition in {"Holo", "Holographic", "Foil"}:
            score += 0.5
        if joker.is_perishable:
            score -= 1.2
        if joker.is_rental:
            score -= 0.8
        ranked.append((score, joker))
    ranked.sort(key=lambda pair: (pair[0], pair[1].name), reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] > 0.0 else None


class PackPlanner:
    def __init__(self):
        self.strategy_model = StrategyModel()
        self.last_trace: Dict[str, Any] = {}

    def _pack_kind(self, state: BalatroState, item: ShopItemState | None = None) -> str:
        if item is not None:
            metadata = item.metadata or {}
            kind = str(metadata.get("kind") or "").strip()
            if kind:
                return kind
            name = (item.name or "").lower()
            if "arcana" in name:
                return "Arcana"
            if "celestial" in name:
                return "Celestial"
            if "spectral" in name:
                return "Spectral"
            if "standard" in name:
                return "Standard"
            if "buffoon" in name:
                return "Buffoon"
        return str(state.meta.pack_kind or "").strip()

    def _joker_slots_free(self, state: BalatroState) -> int:
        return max(0, (state.economy.joker_slots or 5) - len(state.jokers))

    def _consumable_slots_free(self, state: BalatroState) -> int:
        return max(0, (state.economy.consumable_slots or 2) - len(state.consumables))

    def _pack_choose_count(self, item: ShopItemState) -> int:
        config = item.metadata.get("config", {}) if item.metadata else {}
        choose = config.get("choose", 1)
        try:
            return max(1, int(choose))
        except (TypeError, ValueError):
            return 1

    def _pack_card_count(self, item: ShopItemState) -> int:
        config = item.metadata.get("config", {}) if item.metadata else {}
        extra = config.get("extra", 0)
        try:
            return max(0, int(extra))
        except (TypeError, ValueError):
            return 0

    def score_shop_booster(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> Dict[str, float]:
        kind = self._pack_kind(state, item)
        run_plan = inference.get("run_plan", {})
        posterior = inference.get("posterior", {})
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        stage = str(run_plan.get("stage", "building"))
        hard_needs = set(run_plan.get("hard_needs", []))
        pack_pref = float(run_plan.get("pack_preferences", {}).get(kind, 0.0))

        base_scores = {
            "Arcana": 5.0,
            "Celestial": 4.8,
            "Spectral": 4.6,
            "Standard": 4.0,
            "Buffoon": 5.4,
        }
        total = base_scores.get(kind, 3.5)
        detail: Dict[str, float] = {"base": total}

        choose_bonus = (self._pack_choose_count(item) - 1) * 1.0
        size_bonus = max(0, self._pack_card_count(item) - 2) * 0.35
        total += choose_bonus + size_bonus
        detail["choose_bonus"] = round(choose_bonus, 6)
        detail["size_bonus"] = round(size_bonus, 6)

        stage_bonus = 0.0
        slot_penalty = 0.0
        target_bonus = 0.0
        economy_bonus = 0.0

        if kind == "Arcana":
            if stage in {"stabilization", "building"}:
                stage_bonus += 0.9
            target_bonus += 0.6 if run_plan.get("interest_important", True) else 0.2
            target_bonus += posterior.get("deck_growth", 0.0) * 1.2
            if self._consumable_slots_free(state) <= 0:
                slot_penalty += 0.5
        elif kind == "Celestial":
            target_hand = str(run_plan.get("target_hand", "Pair"))
            if target_hand in SMALL_HAND_TARGETS:
                target_bonus += 1.4
            elif target_hand in FLUSH_HANDS or target_hand in STRAIGHT_HANDS:
                target_bonus += 1.2
            if deck_flags.get("planet_focused"):
                target_bonus += 0.9
            if any(joker.name in {"Constellation", "Astronomer", "Observatory", "Telescope", "Supernova"} for joker in state.jokers):
                target_bonus += 0.8
            if self._consumable_slots_free(state) <= 0:
                slot_penalty += 0.4
        elif kind == "Spectral":
            if stage in {"stabilization", "building"}:
                stage_bonus += 0.6
            if deck_flags.get("spectral_focused"):
                target_bonus += 1.0
            if _best_keeper_joker(state.jokers) is not None:
                target_bonus += 0.8
            if len(_all_cards(state)) >= 45:
                target_bonus += 0.6
            if self._consumable_slots_free(state) <= 0:
                slot_penalty += 0.35
        elif kind == "Standard":
            if posterior.get("held_in_hand", 0.0) >= 0.15:
                target_bonus += 0.8
            if posterior.get("deck_growth", 0.0) >= 0.12:
                target_bonus += 0.8
            if posterior.get("flush", 0.0) >= 0.18 or posterior.get("straight", 0.0) >= 0.18:
                target_bonus += 0.6
        elif kind == "Buffoon":
            if stage in {"stabilization", "building"}:
                stage_bonus += 0.9
            if self._joker_slots_free(state) > 0:
                target_bonus += 1.2
            else:
                slot_penalty += 0.9
            if {"chips", "mult", "xmult"} & hard_needs:
                target_bonus += 0.7
            if deck_flags.get("need_early_tempo"):
                target_bonus += 0.5

        if item.cost <= 4 and state.economy.money >= item.cost:
            economy_bonus += 0.4
        if state.economy.money <= 6 and item.cost >= 8:
            economy_bonus -= 1.1
        if state.meta.no_interest or deck_flags.get("ignore_interest"):
            economy_bonus += 0.25
        elif state.economy.money - item.cost < 10 and stage == "stabilization":
            economy_bonus -= 0.4

        if kind == "Buffoon" and self._joker_slots_free(state) == 0 and stage == "endgame":
            slot_penalty += 0.5

        target_bonus += pack_pref * 1.15

        total += stage_bonus + target_bonus + economy_bonus - slot_penalty
        detail["stage_bonus"] = round(stage_bonus, 6)
        detail["target_bonus"] = round(target_bonus, 6)
        detail["economy_bonus"] = round(economy_bonus, 6)
        detail["slot_penalty"] = round(slot_penalty, 6)
        detail["pack_preference"] = round(pack_pref, 6)
        detail["total"] = round(total, 6)
        return detail

    def _score_planet(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> float:
        run_plan = inference.get("run_plan", {})
        accepted_hands = set(run_plan.get("accepted_hands", []))
        target_hand = str(run_plan.get("target_hand", "Pair"))
        hand_name = PLANET_TO_HAND.get(item.name, "")
        score = 2.8
        if hand_name == target_hand:
            score += 4.5
        elif hand_name in accepted_hands:
            score += 3.2
        elif target_hand in DUPLICATE_HANDS and hand_name in DUPLICATE_HANDS:
            score += 3.0
        elif target_hand in SMALL_HANDS and hand_name in SMALL_HAND_TARGETS:
            score += 1.6
        elif target_hand in FLUSH_HANDS and hand_name in {"Flush", "Straight Flush", "Flush House", "Flush Five"}:
            score += 1.8
        elif target_hand in STRAIGHT_HANDS and hand_name in {"Straight", "Straight Flush"}:
            score += 1.8
        if any(joker.name in {"Constellation", "Astronomer", "Observatory", "Supernova"} for joker in state.jokers):
            score += 1.2
        if self._consumable_slots_free(state) <= 0:
            score -= 0.4
        return score

    def _score_tarot(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> float:
        run_plan = inference.get("run_plan", {})
        stage = str(run_plan.get("stage", "building"))
        target_hand = str(run_plan.get("target_hand", "Pair"))
        hard_needs = set(run_plan.get("hard_needs", []))
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        deck_metrics = inference.get("deck_metrics", {})
        score = 1.5

        joker_sell_value = sum(joker.sell_value for joker in state.jokers)
        if item.name == "Hermit":
            score += min(6.0, max(0.0, float(state.economy.money)) * 0.35)
        elif item.name == "Temperance":
            score += min(6.0, float(joker_sell_value) * 0.18)
        elif item.name == "Judgement":
            score += 5.0 if self._joker_slots_free(state) > 0 else 2.0
        elif item.name == "Death":
            score += 4.8 if (deck_metrics.get("exact_duplication", 0.0) > 0 or deck_metrics.get("blue_seal_ratio", 0.0) > 0 or deck_metrics.get("steel_ratio", 0.0) > 0) else 2.2
        elif item.name == "Hanged Man":
            score += 4.4 if len(_all_cards(state)) >= 45 or target_hand in SMALL_HANDS else 2.0
        elif item.name == "The Fool":
            score += 3.8 if state.consumables else 2.2
        elif item.name == "High Priestess":
            score += 4.1 if target_hand in SMALL_HANDS.union(FLUSH_HANDS).union(STRAIGHT_HANDS) else 2.5
        elif item.name == "The Emperor":
            score += 3.2
        elif item.name == "The Magician":
            score += 2.6 if run_plan.get("interest_important", True) else 2.1
        elif item.name == "The Empress":
            score += 2.8 if "mult" in hard_needs else 2.0
        elif item.name == "The Hierophant":
            score += 2.8 if "chips" in hard_needs else 2.0
        elif item.name == "The Chariot":
            score += 3.8 if inference.get("posterior", {}).get("held_in_hand", 0.0) >= 0.15 else 2.0
        elif item.name == "Justice":
            score += 3.4 if "xmult" in hard_needs or stage in {"conversion", "endgame"} else 2.0
        elif item.name == "The Devil":
            score += 3.0 if run_plan.get("interest_important", True) else 2.2
        elif item.name == "Strength":
            score += 2.8 if target_hand in SMALL_HANDS or inference.get("posterior", {}).get("face_cards", 0.0) >= 0.18 else 1.8
        elif item.name == "The Lovers":
            score += 3.0 if target_hand in FLUSH_HANDS else 1.9
        elif item.name in {"The Star", "The Moon", "The Sun", "The World"}:
            score += 3.3 if target_hand in FLUSH_HANDS else 1.6
        else:
            score += 2.6 if item.name in HIGH_VALUE_TAROTS else 1.8

        if deck_flags.get("flush_focused") and item.name in {"The Lovers", "The Star", "The Moon", "The Sun", "The World"}:
            score += 0.8
        if self._consumable_slots_free(state) <= 0 and item.name not in {"Temperance", "Hermit"}:
            score -= 0.5
        return score

    def _score_spectral(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> float:
        run_plan = inference.get("run_plan", {})
        stage = str(run_plan.get("stage", "building"))
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        deck_metrics = inference.get("deck_metrics", {})
        keeper = _best_keeper_joker(state.jokers)
        score = 2.0

        if item.name == "The Soul":
            score += 12.0
        elif item.name == "Black Hole":
            score += 10.0
        elif item.name == "Hex":
            score += 7.0 if keeper is not None else 2.0
        elif item.name == "Immolate":
            score += 7.0 if stage in {"stabilization", "building"} and len(_all_cards(state)) >= 45 else 3.0
        elif item.name == "Ankh":
            score += 6.0 if keeper is not None and len(state.jokers) <= 2 else 2.0
        elif item.name == "Crypt":
            score += 6.0 if deck_metrics.get("blue_seal_ratio", 0.0) > 0 or deck_metrics.get("steel_ratio", 0.0) > 0 else 2.4
        elif item.name == "Ectoplasm":
            score += 5.6 if self._joker_slots_free(state) <= 1 and state.economy.hand_size >= 7 else 2.2
        elif item.name == "Wraith":
            score += 5.0 if self._joker_slots_free(state) > 0 and state.economy.money <= 12 else 1.8
        elif item.name == "Aura":
            score += 4.4 if keeper is not None else 2.0
        elif item.name in {"Trance", "Medium", "Deja Vu"}:
            score += 4.6
        elif item.name in {"Incantation", "Familiar", "Grim"}:
            score += 3.6 if stage in {"stabilization", "building"} else 2.4
        elif item.name in {"Sigil", "Ouija"}:
            score += 3.8 if run_plan.get("target_hand") in FLUSH_HANDS.union(STRAIGHT_HANDS) else 2.0
        else:
            score += 3.2 if item.name in HIGH_VALUE_SPECTRALS else 2.0

        if deck_flags.get("spectral_focused"):
            score += 0.8
        if self._consumable_slots_free(state) <= 0 and item.name not in {"Hex", "Ankh", "Wraith"}:
            score -= 0.4
        return score

    def _score_standard_card(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> float:
        run_plan = inference.get("run_plan", {})
        target_hand = str(run_plan.get("target_hand", "Pair"))
        posterior = inference.get("posterior", {})
        cards = _all_cards(state)
        rank_counts = Counter(card.rank for card in cards)
        dominant_suit = _dominant_suit(cards)
        score = (float(item.base_chips or 0) / 4.0) + 1.0
        item_rank_value = get_rank_value(item.rank) if item.rank else None

        if item.rank and rank_counts.get(item.rank, 0) >= 1:
            if target_hand in SMALL_HANDS or target_hand in DUPLICATE_HANDS:
                score += 2.8
            else:
                score += 1.2
        if item.rank in FACE_RANKS:
            score += posterior.get("face_cards", 0.0) * 6.0
        if item.rank == "Ace":
            score += 1.4 if target_hand in SMALL_HANDS else 0.8

        if target_hand in FLUSH_HANDS and dominant_suit and item.suit == dominant_suit:
            score += 3.0
        if target_hand in STRAIGHT_HANDS and item_rank_value is not None:
            existing_values = [get_rank_value(card.rank) for card in cards if card.rank]
            if existing_values and any(abs(item_rank_value - value) <= 2 for value in existing_values):
                score += 2.6
        if target_hand in DUPLICATE_HANDS:
            if item.rank and rank_counts.get(item.rank, 0) >= 1:
                score += 2.4
            if item.enhancement in {"Glass", "Steel"}:
                score += 1.2

        if item.enhancement == "Steel":
            score += 5.4 if posterior.get("held_in_hand", 0.0) >= 0.15 else 2.2
        elif item.enhancement == "Glass":
            score += 4.6 if run_plan.get("stage") in {"conversion", "endgame"} else 2.4
        elif item.enhancement == "Lucky":
            score += 3.8
        elif item.enhancement == "Gold":
            score += 3.4
        elif item.enhancement == "Stone":
            score += 4.2 if target_hand in SMALL_HANDS else 2.0
        elif item.enhancement == "Wild Card":
            score += 3.6 if target_hand in FLUSH_HANDS else 1.8

        if item.seal == "Blue":
            score += 5.8
        elif item.seal == "Red":
            score += 4.6
        elif item.seal == "Gold":
            score += 3.2
        elif item.seal == "Purple":
            score += 2.8

        if item.edition == "Foil":
            score += 1.0
        elif item.edition in {"Holo", "Holographic"}:
            score += 1.4
        elif item.edition == "Polychrome":
            score += 2.0
        return score

    def _score_buffoon_card(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> float:
        model = self.strategy_model.score_item(state, item, dict(inference))
        score = model["total"] + 1.4
        if self._joker_slots_free(state) > 0:
            score += 1.0
        else:
            score -= 1.6
        return score

    def score_pack_choice(self, state: BalatroState, item: ShopItemState, inference: Mapping[str, Any]) -> Dict[str, Any]:
        kind = self._pack_kind(state)
        if item.rank is not None or kind == "Standard":
            score = self._score_standard_card(state, item, inference)
            reason = "standard_card"
        elif item.set == "Planet" or kind == "Celestial":
            score = self._score_planet(state, item, inference)
            reason = "planet_alignment"
        elif item.set == "Tarot" or kind == "Arcana":
            score = self._score_tarot(state, item, inference)
            reason = "tarot_value"
        elif item.set == "Spectral" or kind == "Spectral":
            score = self._score_spectral(state, item, inference)
            reason = "spectral_value"
        elif item.set == "Joker" or kind == "Buffoon":
            score = self._score_buffoon_card(state, item, inference)
            reason = "buffoon_joker"
        else:
            model = self.strategy_model.score_item(state, item, dict(inference))
            score = model["total"]
            reason = "fallback_strategy_model"
        return {"score": round(score, 6), "reason": reason}

    def plan_action(self, state: BalatroState) -> ActionResponse:
        inference = self.strategy_model.infer(state)
        if not state.pack_items:
            self.last_trace = {
                "phase": state.meta.phase,
                "pack_kind": state.meta.pack_kind,
                "strategy": inference,
                "pack_scores": [],
                "decision_reason": "pack_inventory_pending",
            }
            logger.info("Waiting for pack inventory to populate before deciding.")
            return ActionResponse(action="NO_OP", message="pack_inventory_pending")

        scored = []
        for item in state.pack_items:
            breakdown = self.score_pack_choice(state, item, inference)
            scored.append(
                {
                    "item": item,
                    "score": breakdown["score"],
                    "reason": breakdown["reason"],
                }
            )
        scored.sort(key=lambda entry: (entry["score"], entry["item"].name, entry["item"].id), reverse=True)

        best = scored[0]
        self.last_trace = {
            "phase": state.meta.phase,
            "pack_kind": state.meta.pack_kind,
            "strategy": inference,
            "pack_scores": [
                {
                    "id": entry["item"].id,
                    "name": entry["item"].name,
                    "set": entry["item"].set,
                    "rank": entry["item"].rank,
                    "suit": entry["item"].suit,
                    "enhancement": entry["item"].enhancement,
                    "seal": entry["item"].seal,
                    "score": entry["score"],
                    "reason": entry["reason"],
                }
                for entry in scored
            ],
            "decision_reason": "take_highest_scoring_pack_item",
        }
        logger.info(
            "Taking pack item '%s' from %s pack (score %.2f).",
            best["item"].name,
            state.meta.pack_kind or "Unknown",
            best["score"],
        )
        return ActionResponse(action="TAKE_PACK_CARD", target_id=best["item"].id)
