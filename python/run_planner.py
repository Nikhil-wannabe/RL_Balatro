from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Mapping

from state import BalatroState, Joker, ShopItemState


STAGES = ("stabilization", "building", "conversion", "endgame")
ROLE_NAMES = ("chips", "mult", "xmult", "economy", "value", "consistency")

SMALL_HANDS = {"High Card", "Pair", "Two Pair"}
FLUSH_HANDS = {"Flush", "Straight Flush", "Flush House", "Flush Five"}
STRAIGHT_HANDS = {"Straight", "Straight Flush"}
DUPLICATE_HANDS = {"Three of a Kind", "Full House", "Four of a Kind", "Five of a Kind"}

DECK_BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "b_red": {
        "family_bias": {"flush": 0.35, "straight": 0.25, "pair": 0.10, "duplicate": 0.05},
        "pack_bias": {"Celestial": 0.20, "Standard": 0.10},
        "economy_floor_delta": 0,
        "reroll_delta": 0.10,
    },
    "b_blue": {
        "family_bias": {"pair": 0.35, "duplicate": 0.10},
        "pack_bias": {"Arcana": 0.10, "Buffoon": 0.10},
        "economy_floor_delta": 1,
        "reroll_delta": 0.00,
    },
    "b_yellow": {
        "family_bias": {"pair": 0.15, "duplicate": 0.10},
        "pack_bias": {"Buffoon": 0.25, "Arcana": 0.15},
        "economy_floor_delta": -1,
        "reroll_delta": 0.20,
    },
    "b_green": {
        "family_bias": {"pair": 0.35, "duplicate": 0.10},
        "pack_bias": {"Buffoon": 0.20, "Standard": 0.10, "Arcana": 0.10},
        "economy_floor_delta": -4,
        "reroll_delta": 0.35,
    },
    "b_black": {
        "family_bias": {"pair": 0.45, "duplicate": 0.15, "flush": -0.10},
        "pack_bias": {"Buffoon": 0.40, "Arcana": 0.10, "Celestial": -0.10},
        "economy_floor_delta": -2,
        "reroll_delta": 0.25,
    },
    "b_magic": {
        "family_bias": {"pair": 0.15, "duplicate": 0.05},
        "pack_bias": {"Arcana": 0.45, "Spectral": 0.10},
        "economy_floor_delta": -1,
        "reroll_delta": 0.10,
    },
    "b_nebula": {
        "family_bias": {"pair": 0.10, "flush": 0.15, "straight": 0.20},
        "pack_bias": {"Celestial": 0.50},
        "economy_floor_delta": 0,
        "reroll_delta": 0.10,
    },
    "b_ghost": {
        "family_bias": {"pair": 0.10, "duplicate": 0.10},
        "pack_bias": {"Spectral": 0.45, "Arcana": 0.05},
        "economy_floor_delta": 0,
        "reroll_delta": 0.10,
    },
    "b_abandoned": {
        "family_bias": {"pair": 0.35, "straight": 0.25, "duplicate": 0.35, "flush": -0.20},
        "pack_bias": {"Standard": 0.20, "Celestial": 0.20},
        "economy_floor_delta": -1,
        "reroll_delta": 0.15,
    },
    "b_checkered": {
        "family_bias": {"flush": 1.00, "straight": -0.10, "pair": -0.10},
        "pack_bias": {"Celestial": 0.55, "Standard": 0.35},
        "economy_floor_delta": 0,
        "reroll_delta": 0.05,
    },
    "b_zodiac": {
        "family_bias": {"pair": 0.10, "flush": 0.10, "straight": 0.10},
        "pack_bias": {"Arcana": 0.35, "Celestial": 0.25, "Buffoon": 0.15},
        "economy_floor_delta": -1,
        "reroll_delta": 0.15,
    },
    "b_painted": {
        "family_bias": {"straight": 0.55, "flush": 0.45, "pair": -0.10},
        "pack_bias": {"Celestial": 0.35, "Standard": 0.25},
        "economy_floor_delta": 0,
        "reroll_delta": 0.10,
    },
    "b_anaglyph": {
        "family_bias": {"pair": 0.10, "duplicate": 0.10},
        "pack_bias": {"Buffoon": 0.15, "Arcana": 0.15},
        "economy_floor_delta": 0,
        "reroll_delta": 0.10,
    },
    "b_plasma": {
        "family_bias": {"pair": 0.25, "duplicate": 0.15},
        "pack_bias": {"Buffoon": 0.25, "Celestial": 0.10},
        "economy_floor_delta": -1,
        "reroll_delta": 0.20,
    },
    "b_erratic": {
        "family_bias": {"duplicate": 0.10},
        "pack_bias": {"Standard": 0.30, "Arcana": 0.20, "Celestial": 0.15},
        "economy_floor_delta": 0,
        "reroll_delta": 0.15,
    },
}

JOKER_ROLE_HINTS: Dict[str, Dict[str, float]] = {
    "Joker": {"mult": 0.6},
    "Half Joker": {"mult": 1.1},
    "Blue Joker": {"chips": 1.3},
    "Green Joker": {"mult": 1.2},
    "Banner": {"chips": 0.8},
    "Scary Face": {"chips": 0.9},
    "Smiley Face": {"mult": 0.8},
    "Odd Todd": {"chips": 0.8},
    "Scholar": {"chips": 0.8, "mult": 0.4},
    "Abstract Joker": {"mult": 0.8},
    "Ride the Bus": {"mult": 1.2},
    "Supernova": {"mult": 1.2},
    "Red Card": {"mult": 1.1},
    "Runner": {"chips": 1.2, "consistency": 0.3},
    "Square Joker": {"chips": 1.2},
    "Wee Joker": {"chips": 1.0},
    "Bull": {"chips": 1.2, "economy": 0.5},
    "Castle": {"chips": 1.0},
    "Arrowhead": {"chips": 1.2},
    "Hologram": {"xmult": 1.5, "value": 0.2},
    "Card Sharp": {"xmult": 1.3},
    "Vampire": {"xmult": 1.4},
    "Constellation": {"xmult": 1.3},
    "Acrobat": {"xmult": 1.1},
    "Cavendish": {"xmult": 1.2},
    "Blackboard": {"xmult": 1.0, "consistency": 0.2},
    "Photograph": {"xmult": 1.0},
    "Baron": {"xmult": 1.3, "consistency": 0.2},
    "Mime": {"xmult": 0.8, "value": 0.4},
    "Steel Joker": {"xmult": 1.1},
    "To the Moon": {"economy": 1.3},
    "Golden Joker": {"economy": 1.1},
    "Rocket": {"economy": 1.0},
    "Business Card": {"economy": 0.8, "value": 0.3},
    "Mail-In Rebate": {"economy": 1.0, "value": 0.2},
    "Delayed Gratification": {"economy": 0.9},
    "Hallucination": {"value": 1.0},
    "Vagabond": {"value": 1.2, "economy": 0.4},
    "Cartomancer": {"value": 1.1},
    "Burnt Joker": {"value": 0.8, "consistency": 0.5},
    "Four Fingers": {"consistency": 1.2},
    "Shortcut": {"consistency": 1.3},
    "Troubadour": {"consistency": 0.8},
    "Juggler": {"consistency": 0.7},
    "Drunkard": {"consistency": 0.8},
    "Merry Andy": {"economy": 0.6, "consistency": 0.6},
    "Burglar": {"economy": 0.6, "consistency": 0.8},
    "Spare Trousers": {"mult": 1.0},
    "Fortune Teller": {"mult": 1.0, "value": 0.4},
    "Bootstraps": {"mult": 1.1, "economy": 0.5},
    "Reserved Parking": {"economy": 0.8, "value": 0.3},
}

ITEM_ROLE_HINTS: Dict[str, Dict[str, float]] = {
    "Joker": {"mult": 0.4},
    "Half Joker": {"mult": 0.9},
    "Blue Joker": {"chips": 1.1},
    "Green Joker": {"mult": 1.0},
    "Raised Fist": {"mult": 0.8},
    "Abstract Joker": {"mult": 0.7},
    "Banner": {"chips": 0.7},
    "Scary Face": {"chips": 0.8},
    "Smiley Face": {"mult": 0.7},
    "Scholar": {"chips": 0.7, "mult": 0.3},
    "Supernova": {"mult": 1.0},
    "Ride the Bus": {"mult": 1.0},
    "Red Card": {"mult": 1.0},
    "Runner": {"chips": 1.0, "consistency": 0.2},
    "Square Joker": {"chips": 1.0},
    "Wee Joker": {"chips": 0.9},
    "Bull": {"chips": 1.1, "economy": 0.4},
    "Castle": {"chips": 0.9},
    "Arrowhead": {"chips": 1.0},
    "Hologram": {"xmult": 1.4, "value": 0.2},
    "Card Sharp": {"xmult": 1.3},
    "Vampire": {"xmult": 1.3},
    "Constellation": {"xmult": 1.2},
    "Acrobat": {"xmult": 1.0},
    "Cavendish": {"xmult": 1.1},
    "Blackboard": {"xmult": 0.9},
    "Photograph": {"xmult": 0.8},
    "Baron": {"xmult": 1.2},
    "Mime": {"xmult": 0.7, "value": 0.3},
    "Steel Joker": {"xmult": 1.0},
    "To the Moon": {"economy": 1.1},
    "Golden Joker": {"economy": 0.9},
    "Rocket": {"economy": 0.9},
    "Business Card": {"economy": 0.8, "value": 0.3},
    "Mail-In Rebate": {"economy": 0.9, "value": 0.2},
    "Delayed Gratification": {"economy": 0.8},
    "Hallucination": {"value": 0.9},
    "Vagabond": {"value": 1.1, "economy": 0.3},
    "Cartomancer": {"value": 1.0},
    "Burnt Joker": {"value": 0.8, "consistency": 0.5},
    "Four Fingers": {"consistency": 1.1},
    "Shortcut": {"consistency": 1.2},
    "Grabber": {"consistency": 0.7},
    "Nacho Tong": {"consistency": 0.9},
    "Paint Brush": {"consistency": 0.7},
    "Palette": {"consistency": 0.8},
    "Telescope": {"value": 0.8, "consistency": 0.6},
    "Observatory": {"xmult": 0.9, "value": 0.6},
    "Seed Money": {"economy": 1.2},
    "Money Tree": {"economy": 1.5},
    "Clearance Sale": {"economy": 0.9},
    "Liquidation": {"economy": 1.0},
    "Director's Cut": {"consistency": 0.8},
    "Reroll Surplus": {"economy": 0.8, "value": 0.2},
    "Reroll Glut": {"economy": 0.9, "value": 0.2},
}

EARLY_TEMPO_ITEMS = {
    "Joker",
    "Half Joker",
    "Blue Joker",
    "Green Joker",
    "Raised Fist",
    "Abstract Joker",
    "Banner",
    "Scary Face",
    "Smiley Face",
    "Odd Todd",
    "Scholar",
}

LATE_CONVERSION_ITEMS = {
    "Hologram",
    "Card Sharp",
    "Vampire",
    "Constellation",
    "Acrobat",
    "Cavendish",
    "Blackboard",
    "Baron",
    "Mime",
    "Steel Joker",
    "Observatory",
}

PURE_ECON_ITEMS = {
    "Seed Money",
    "Money Tree",
    "To the Moon",
    "Rocket",
    "Golden Joker",
    "Business Card",
    "Mail-In Rebate",
    "Delayed Gratification",
}

PAIR_ITEMS = {
    "Mercury",
    "Pluto",
    "Uranus",
    "Square Joker",
    "Green Joker",
    "Supernova",
    "Ride the Bus",
    "Half Joker",
    "Blue Joker",
    "Card Sharp",
}

FLUSH_ITEMS = {
    "Jupiter",
    "Neptune",
    "Ceres",
    "Eris",
    "Arrowhead",
    "Bloodstone",
    "Onyx Agate",
    "Rough Gem",
    "Smeared Joker",
    "Crafty Joker",
    "Droll Joker",
    "Ancient Joker",
    "The Tribe",
}

STRAIGHT_ITEMS = {
    "Saturn",
    "Neptune",
    "Four Fingers",
    "Shortcut",
    "Runner",
    "Superposition",
    "Seance",
    "Crazy Joker",
    "Devious Joker",
    "The Order",
}

SLOW_SCALERS = {
    "Yorick",
    "Rocket",
    "Campfire",
    "Lucky Cat",
    "Glass Joker",
    "Fortune Teller",
    "Spare Trousers",
    "Red Card",
}

DUPLICATE_PLANET_ITEMS = {"Venus", "Earth", "Mars", "Planet X"}


class RunPlanner:
    def build(
        self,
        state: BalatroState,
        *,
        preferred_hand: str,
        posterior: Mapping[str, float],
        deck_profile: Mapping[str, Any],
        deck_metrics: Mapping[str, float],
        draw_metrics: Mapping[str, float],
        boss_profile: Mapping[str, Any],
    ) -> Dict[str, Any]:
        deck_flags = dict(deck_profile.get("flags", {}))
        blueprint = DECK_BLUEPRINTS.get(str(deck_profile.get("deck_key", "")), {})
        base_stage = self._base_stage(state)
        target_hand = self._target_hand(
            state,
            preferred_hand=preferred_hand,
            posterior=posterior,
            deck_flags=deck_flags,
            deck_metrics=deck_metrics,
            draw_metrics=draw_metrics,
            stage=base_stage,
            blueprint=blueprint,
            boss_profile=boss_profile,
        )
        provisional_scores = self._role_scores(
            state,
            target_hand=target_hand,
            posterior=posterior,
            deck_flags=deck_flags,
            deck_metrics=deck_metrics,
            draw_metrics=draw_metrics,
        )
        stage = self._refine_stage(
            state,
            base_stage=base_stage,
            target_hand=target_hand,
            role_scores=provisional_scores,
            deck_flags=deck_flags,
        )
        if stage != base_stage:
            target_hand = self._target_hand(
                state,
                preferred_hand=preferred_hand,
                posterior=posterior,
                deck_flags=deck_flags,
                deck_metrics=deck_metrics,
                draw_metrics=draw_metrics,
                stage=stage,
                blueprint=blueprint,
                boss_profile=boss_profile,
            )
        accepted_hands = self._accepted_hands(target_hand)
        role_scores = self._role_scores(
            state,
            target_hand=target_hand,
            posterior=posterior,
            deck_flags=deck_flags,
            deck_metrics=deck_metrics,
            draw_metrics=draw_metrics,
        )
        role_targets = self._role_targets(
            state,
            stage=stage,
            target_hand=target_hand,
            deck_flags=deck_flags,
        )
        role_deficits = {
            role: max(0.0, round(role_targets.get(role, 0.0) - role_scores.get(role, 0.0), 6))
            for role in ROLE_NAMES
        }
        hard_needs = [
            role
            for role, deficit in sorted(role_deficits.items(), key=lambda pair: pair[1], reverse=True)
            if deficit >= 0.55
        ]
        pack_preferences = self._pack_preferences(
            target_hand=target_hand,
            stage=stage,
            deck_flags=deck_flags,
            blueprint=blueprint,
        )
        conversion_ready = (
            role_scores["chips"] >= role_targets["chips"] * 0.85
            and role_scores["mult"] >= role_targets["mult"] * 0.85
            and (state.economy.money >= 25 or state.meta.no_interest or deck_flags.get("spend_aggressively"))
        )
        economy_floor = self._economy_floor(
            state,
            stage=stage,
            deck_flags=deck_flags,
            blueprint=blueprint,
        )
        reroll_aggression = self._reroll_aggression(
            stage=stage,
            hard_needs=hard_needs,
            highest_deficit=max(role_deficits.values()) if role_deficits else 0.0,
            deck_flags=deck_flags,
            blueprint=blueprint,
        )
        return {
            "stage": stage,
            "base_stage": base_stage,
            "target_hand": target_hand,
            "hand_family": self._hand_family(target_hand),
            "accepted_hands": sorted(accepted_hands),
            "backup_hands": sorted(set(accepted_hands) - {target_hand}),
            "role_scores": role_scores,
            "role_targets": role_targets,
            "role_deficits": role_deficits,
            "hard_needs": hard_needs,
            "highest_deficit": max(role_deficits.values()) if role_deficits else 0.0,
            "conversion_ready": conversion_ready,
            "spend_aggressively": bool(deck_flags.get("spend_aggressively") or state.meta.no_interest),
            "interest_important": not bool(deck_flags.get("ignore_interest") or state.meta.no_interest),
            "pack_preferences": pack_preferences,
            "economy_floor": economy_floor,
            "reroll_aggression": reroll_aggression,
            "boss_profile": dict(boss_profile),
        }

    def score_item_adjustment(
        self,
        state: BalatroState,
        item: ShopItemState,
        *,
        run_plan: Mapping[str, Any],
        deck_flags: Mapping[str, Any],
    ) -> Dict[str, float]:
        stage = str(run_plan.get("stage", "building"))
        role_deficits = run_plan.get("role_deficits", {})
        role_scores = run_plan.get("role_scores", {})
        target_hand = str(run_plan.get("target_hand", "Pair"))

        role_bonus = 0.0
        for role, weight in ITEM_ROLE_HINTS.get(item.name, {}).items():
            role_bonus += float(role_deficits.get(role, 0.0)) * weight

        target_bonus = 0.0
        if target_hand in SMALL_HANDS and item.name in PAIR_ITEMS:
            target_bonus += 0.8
        if target_hand in FLUSH_HANDS and item.name in FLUSH_ITEMS:
            target_bonus += 0.9
        if target_hand in STRAIGHT_HANDS and item.name in STRAIGHT_ITEMS:
            target_bonus += 0.9

        stage_bonus = 0.0
        if stage == "stabilization" and item.name in EARLY_TEMPO_ITEMS:
            stage_bonus += 1.0
        if stage in {"conversion", "endgame"} and item.name in LATE_CONVERSION_ITEMS:
            stage_bonus += 0.9
        if stage in {"conversion", "endgame"} and item.name in PURE_ECON_ITEMS:
            stage_bonus -= 0.9 if role_scores.get("economy", 0.0) >= 0.8 else 0.3
        if stage == "endgame" and item.name in SLOW_SCALERS:
            stage_bonus -= 1.0

        deck_bonus = 0.0
        if deck_flags.get("flush_focused") and item.name in FLUSH_ITEMS:
            deck_bonus += 0.6
        if deck_flags.get("planet_focused") and item.set == "Planet":
            deck_bonus += 0.5
        if deck_flags.get("large_hand") and item.name in STRAIGHT_ITEMS.union(FLUSH_ITEMS):
            deck_bonus += 0.4
        if deck_flags.get("need_early_tempo") and stage == "stabilization" and item.set == "Joker":
            deck_bonus += 0.4
        if deck_flags.get("face_suppressed") and item.name in {"Baron", "Photograph", "Smiley Face", "Reserved Parking"}:
            deck_bonus -= 1.1
        if deck_flags.get("ignore_interest") and item.name in {"Seed Money", "Money Tree", "To the Moon"}:
            deck_bonus -= 1.4

        penalty = 0.0
        if item.set == "Booster":
            booster_kind = str((item.metadata or {}).get("kind") or "")
            penalty += 0.4
            if booster_kind == "Buffoon" and stage in {"stabilization", "building"}:
                stage_bonus += 0.6
            elif booster_kind == "Celestial":
                target_bonus += 0.6 if target_hand in SMALL_HANDS.union(FLUSH_HANDS).union(STRAIGHT_HANDS) else 0.2
            elif booster_kind == "Arcana":
                target_bonus += 0.5
            elif booster_kind == "Spectral" and stage in {"building", "conversion"}:
                stage_bonus += 0.4
            elif booster_kind == "Standard" and target_hand in FLUSH_HANDS.union(STRAIGHT_HANDS):
                target_bonus += 0.35
        if item.is_rental and stage == "stabilization":
            penalty += 1.2
        if item.is_perishable and item.name in SLOW_SCALERS:
            penalty += 0.8

        total = role_bonus + target_bonus + stage_bonus + deck_bonus - penalty
        return {
            "role_bonus": round(role_bonus, 6),
            "target_bonus": round(target_bonus, 6),
            "stage_bonus": round(stage_bonus, 6),
            "deck_bonus": round(deck_bonus, 6),
            "plan_penalty": round(penalty, 6),
            "total": round(total, 6),
        }

    def _base_stage(self, state: BalatroState) -> str:
        ante = int(state.meta.ante or 1)
        if ante <= 2:
            return "stabilization"
        if ante <= 5:
            return "building"
        if ante <= 7:
            return "conversion"
        return "endgame"

    def _refine_stage(
        self,
        state: BalatroState,
        *,
        base_stage: str,
        target_hand: str,
        role_scores: Mapping[str, float],
        deck_flags: Mapping[str, Any],
    ) -> str:
        ante = int(state.meta.ante or 1)
        chips = float(role_scores.get("chips", 0.0))
        mult = float(role_scores.get("mult", 0.0))
        xmult = float(role_scores.get("xmult", 0.0))
        consistency = float(role_scores.get("consistency", 0.0))
        strong_core = chips >= 0.90 and mult >= 0.95
        scaling_online = xmult >= 0.95 or (xmult >= 0.70 and consistency >= 0.65)
        target_is_greedy = target_hand in FLUSH_HANDS.union(STRAIGHT_HANDS).union(DUPLICATE_HANDS)

        if base_stage in {"building", "conversion"} and ante <= 4 and (chips < 0.70 or mult < 0.78):
            return "stabilization"
        if base_stage == "conversion" and not strong_core:
            return "building"
        if base_stage == "endgame" and not (strong_core and scaling_online):
            return "conversion"
        if (
            base_stage in {"building", "conversion"}
            and strong_core
            and (scaling_online or ante >= 6 or deck_flags.get("high_scaling_pressure"))
        ):
            return "conversion"
        if base_stage == "building" and target_is_greedy and consistency < 0.48 and ante <= 4:
            return "stabilization"
        return base_stage

    def _duplicate_pressure(
        self,
        state: BalatroState,
        *,
        deck_metrics: Mapping[str, float],
        draw_metrics: Mapping[str, float],
        posterior: Mapping[str, float],
        deck_flags: Mapping[str, Any],
    ) -> float:
        pressure = 0.0
        pressure += float(deck_metrics.get("rank_duplication", 0.0)) * 3.4
        pressure += float(draw_metrics.get("draw_rank_duplication", 0.0)) * 2.4
        pressure += float(deck_metrics.get("exact_duplication", 0.0)) * 4.6
        pressure += float(draw_metrics.get("draw_exact_duplication", 0.0)) * 3.8
        pressure += float(posterior.get("deck_growth", 0.0)) * 0.9
        if deck_flags.get("volatile_deck"):
            pressure += 0.4
        if deck_flags.get("face_suppressed"):
            pressure += 0.3
        if any(joker.name in {"DNA", "Hologram", "Certificate", "Spare Trousers", "Square Joker"} for joker in state.jokers):
            pressure += 0.8
        return pressure

    def _duplicate_target_hand(
        self,
        state: BalatroState,
        *,
        deck_metrics: Mapping[str, float],
        draw_metrics: Mapping[str, float],
    ) -> str:
        rank_dup = float(deck_metrics.get("rank_duplication", 0.0)) + float(draw_metrics.get("draw_rank_duplication", 0.0))
        exact_dup = float(deck_metrics.get("exact_duplication", 0.0)) + float(draw_metrics.get("draw_exact_duplication", 0.0))
        level = lambda name: float(getattr(state.hand_levels.get(name), "level", 1))
        scores = {
            "Three of a Kind": 1.8 + rank_dup * 2.2 + level("Three of a Kind") * 0.35,
            "Full House": 1.7 + rank_dup * 1.9 + exact_dup * 0.8 + level("Full House") * 0.40,
            "Four of a Kind": 1.2 + rank_dup * 1.4 + exact_dup * 2.8 + level("Four of a Kind") * 0.42,
            "Five of a Kind": 0.6 + exact_dup * 4.2 + level("Five of a Kind") * 0.48,
        }
        return max(scores.items(), key=lambda pair: (pair[1], pair[0]))[0]

    def _hand_family(self, hand_name: str) -> str:
        if hand_name in SMALL_HANDS:
            return "pair"
        if hand_name in FLUSH_HANDS:
            return "flush"
        if hand_name in STRAIGHT_HANDS:
            return "straight"
        if hand_name in DUPLICATE_HANDS:
            return "duplicate"
        return "pair"

    def _target_hand(
        self,
        state: BalatroState,
        *,
        preferred_hand: str,
        posterior: Mapping[str, float],
        deck_flags: Mapping[str, Any],
        deck_metrics: Mapping[str, float],
        draw_metrics: Mapping[str, float],
        stage: str,
        blueprint: Mapping[str, Any],
        boss_profile: Mapping[str, Any],
    ) -> str:
        locked_hand = str(boss_profile.get("locked_hand", "") or "")
        if locked_hand:
            return locked_hand
        flush_p = float(posterior.get("flush", 0.0))
        straight_p = float(posterior.get("straight", 0.0))
        small_hand_p = float(posterior.get("small_hand", 0.0))
        held_p = float(posterior.get("held_in_hand", 0.0))
        face_p = float(posterior.get("face_cards", 0.0))
        duplicate_p = self._duplicate_pressure(
            state,
            deck_metrics=deck_metrics,
            draw_metrics=draw_metrics,
            posterior=posterior,
            deck_flags=deck_flags,
        )
        family_bias = dict(blueprint.get("family_bias", {}))

        pair_score = small_hand_p * 2.8
        flush_score = flush_p * 2.7
        straight_score = straight_p * 2.6
        duplicate_score = duplicate_p + (small_hand_p * 0.8)

        pair_score += family_bias.get("pair", 0.0)
        flush_score += family_bias.get("flush", 0.0)
        straight_score += family_bias.get("straight", 0.0)
        duplicate_score += family_bias.get("duplicate", 0.0)

        suit_support = max(
            float(deck_metrics.get("max_suit_share", 0.0)),
            float(draw_metrics.get("draw_max_suit_share", 0.0)),
        )
        flush_score += max(0.0, (suit_support - 0.30) * 2.8)
        straight_score += max(0.0, (float(state.economy.hand_size) - 8.0) * 0.12)
        straight_score += max(0.0, float(state.economy.discards_left) - 2.0) * 0.12
        if preferred_hand in DUPLICATE_HANDS:
            duplicate_score += 0.8
        if preferred_hand in SMALL_HANDS:
            pair_score += 0.4
        if preferred_hand in FLUSH_HANDS:
            flush_score += 0.5
        if preferred_hand in STRAIGHT_HANDS:
            straight_score += 0.5

        if stage == "stabilization":
            pair_score += 0.9
            if not deck_flags.get("flush_focused"):
                flush_score -= 0.15
            if not deck_flags.get("large_hand"):
                straight_score -= 0.10
            duplicate_score -= 0.20
        elif stage == "building":
            duplicate_score += 0.20
        else:
            duplicate_score += 0.40
            flush_score += 0.15
            straight_score += 0.15

        if deck_flags.get("flush_focused"):
            return "Flush"
        if deck_flags.get("face_suppressed"):
            if duplicate_score >= max(pair_score + 0.18, 1.30):
                return self._duplicate_target_hand(state, deck_metrics=deck_metrics, draw_metrics=draw_metrics)
            if straight_score >= max(flush_score, pair_score - 0.05):
                return "Straight"
            return "Pair"
        if deck_flags.get("large_hand") and straight_p >= max(flush_p, small_hand_p - 0.05):
            return "Straight"
        if deck_flags.get("extra_discards") and max(flush_p, straight_p) >= 0.18:
            return "Flush" if flush_p >= straight_p else "Straight"
        if held_p >= 0.28 and any(joker.name in {"Baron", "Mime", "Steel Joker"} for joker in state.jokers):
            return "Pair"
        if boss_profile.get("require_five_card_play"):
            flush_score += 0.10
            straight_score += 0.10
        if duplicate_score >= max(pair_score + 0.20, flush_score + 0.12, straight_score + 0.12, 1.45):
            return self._duplicate_target_hand(state, deck_metrics=deck_metrics, draw_metrics=draw_metrics)
        if flush_score >= max(1.20, pair_score + 0.18, straight_score + 0.05):
            return "Flush"
        if straight_score >= max(1.10, pair_score + 0.12, flush_score + 0.04):
            return "Straight"
        if face_p >= 0.24:
            return "Pair"
        if pair_score >= max(flush_score, straight_score):
            if preferred_hand in DUPLICATE_HANDS and duplicate_score >= pair_score - 0.08:
                return self._duplicate_target_hand(state, deck_metrics=deck_metrics, draw_metrics=draw_metrics)
            return preferred_hand if preferred_hand in SMALL_HANDS else "Pair"
        if duplicate_score >= max(flush_score, straight_score):
            return self._duplicate_target_hand(state, deck_metrics=deck_metrics, draw_metrics=draw_metrics)
        if preferred_hand in SMALL_HANDS:
            return preferred_hand
        if preferred_hand in FLUSH_HANDS:
            return "Flush"
        if preferred_hand in STRAIGHT_HANDS:
            return "Straight"
        return "Pair"

    def _accepted_hands(self, target_hand: str) -> set[str]:
        if target_hand in SMALL_HANDS:
            return set(SMALL_HANDS)
        if target_hand in FLUSH_HANDS:
            return set(FLUSH_HANDS).union({"Flush", "Pair", "Two Pair"})
        if target_hand in STRAIGHT_HANDS:
            return set(STRAIGHT_HANDS).union({"Straight", "Pair", "Two Pair"})
        if target_hand in DUPLICATE_HANDS:
            return {"Pair", "Two Pair", "Three of a Kind", "Full House", "Four of a Kind", "Five of a Kind"}
        return {target_hand}

    def _role_scores(
        self,
        state: BalatroState,
        *,
        target_hand: str,
        posterior: Mapping[str, float],
        deck_flags: Mapping[str, Any],
        deck_metrics: Mapping[str, float],
        draw_metrics: Mapping[str, float],
    ) -> Dict[str, float]:
        scores = {role: 0.0 for role in ROLE_NAMES}

        for joker in state.jokers:
            for role, weight in JOKER_ROLE_HINTS.get(joker.name, {}).items():
                scores[role] += weight
            if joker.is_rental:
                scores["economy"] -= 0.25

        target_info = state.hand_levels.get(target_hand)
        if target_info is not None:
            scores["chips"] += min(0.8, max(0.0, float(target_info.level - 1)) * 0.14)
            scores["mult"] += min(0.8, max(0.0, float(target_info.level - 1)) * 0.14)

        money = float(state.economy.money)
        if not (deck_flags.get("ignore_interest") or state.meta.no_interest):
            scores["economy"] += min(1.0, money / 25.0)
        else:
            scores["economy"] += min(0.5, money / 20.0)

        if deck_flags.get("extra_discards"):
            scores["consistency"] += 0.35
        if deck_flags.get("extra_hands"):
            scores["consistency"] += 0.45
        if deck_flags.get("large_hand"):
            scores["consistency"] += 0.40

        if target_hand in SMALL_HANDS:
            scores["consistency"] += 0.45
            scores["value"] += float(draw_metrics.get("draw_exact_duplication", 0.0)) * 1.2
        if target_hand in DUPLICATE_HANDS:
            scores["consistency"] += 0.30
            scores["value"] += float(draw_metrics.get("draw_exact_duplication", 0.0)) * 1.8
            scores["chips"] += float(deck_metrics.get("rank_duplication", 0.0)) * 0.8
        if target_hand in FLUSH_HANDS:
            suit_share = max(
                float(deck_metrics.get("max_suit_share", 0.0)),
                float(draw_metrics.get("draw_max_suit_share", 0.0)),
            )
            scores["consistency"] += max(0.0, (suit_share - 0.26) * 2.0)
        if target_hand in STRAIGHT_HANDS:
            straight_support = 0.4 + (float(state.economy.hand_size) - 8.0) * 0.08
            scores["consistency"] += max(0.0, straight_support)

        scores["value"] += float(deck_metrics.get("blue_seal_ratio", 0.0)) * 5.0
        scores["value"] += float(draw_metrics.get("draw_enhanced_ratio", 0.0)) * 1.2
        scores["xmult"] += float(deck_metrics.get("steel_ratio", 0.0)) * 3.0
        scores["value"] += float(posterior.get("economy", 0.0)) * 0.25

        return {role: round(max(0.0, value), 6) for role, value in scores.items()}

    def _role_targets(
        self,
        state: BalatroState,
        *,
        stage: str,
        target_hand: str,
        deck_flags: Mapping[str, Any],
    ) -> Dict[str, float]:
        if stage == "stabilization":
            targets = {"chips": 0.9, "mult": 1.0, "xmult": 0.0, "economy": 0.6, "value": 0.2, "consistency": 0.4}
        elif stage == "building":
            targets = {"chips": 1.0, "mult": 1.1, "xmult": 0.6, "economy": 0.8, "value": 0.5, "consistency": 0.5}
        elif stage == "conversion":
            targets = {"chips": 0.9, "mult": 1.0, "xmult": 1.3, "economy": 0.4, "value": 0.2, "consistency": 0.55}
        else:
            targets = {"chips": 0.8, "mult": 0.9, "xmult": 1.8, "economy": 0.1, "value": 0.1, "consistency": 0.6}

        if target_hand in FLUSH_HANDS or target_hand in STRAIGHT_HANDS:
            targets["consistency"] += 0.25
        if target_hand in DUPLICATE_HANDS:
            targets["consistency"] += 0.18
            targets["value"] += 0.12
        if deck_flags.get("need_early_tempo") and stage == "stabilization":
            targets["chips"] += 0.2
            targets["mult"] += 0.2
        if deck_flags.get("high_scaling_pressure"):
            targets["xmult"] += 0.25
        if deck_flags.get("ignore_interest") or state.meta.no_interest:
            targets["economy"] = max(0.0, targets["economy"] - 0.4)
            targets["value"] += 0.15
        if deck_flags.get("large_hand"):
            targets["consistency"] += 0.1
        return targets

    def _pack_preferences(
        self,
        *,
        target_hand: str,
        stage: str,
        deck_flags: Mapping[str, Any],
        blueprint: Mapping[str, Any],
    ) -> Dict[str, float]:
        base_by_stage = {
            "stabilization": {"Buffoon": 1.00, "Arcana": 0.90, "Celestial": 0.55, "Standard": 0.50, "Spectral": 0.40},
            "building": {"Buffoon": 0.85, "Arcana": 0.75, "Celestial": 0.80, "Standard": 0.60, "Spectral": 0.60},
            "conversion": {"Buffoon": 0.60, "Arcana": 0.45, "Celestial": 0.90, "Standard": 0.70, "Spectral": 0.70},
            "endgame": {"Buffoon": 0.45, "Arcana": 0.30, "Celestial": 0.80, "Standard": 0.75, "Spectral": 0.70},
        }
        prefs = dict(base_by_stage.get(stage, base_by_stage["building"]))
        if target_hand in SMALL_HANDS:
            prefs["Celestial"] += 0.35
            prefs["Buffoon"] += 0.15
            prefs["Arcana"] += 0.15
        elif target_hand in FLUSH_HANDS:
            prefs["Celestial"] += 0.55
            prefs["Standard"] += 0.35
            prefs["Arcana"] += 0.10
        elif target_hand in STRAIGHT_HANDS:
            prefs["Celestial"] += 0.50
            prefs["Standard"] += 0.30
        elif target_hand in DUPLICATE_HANDS:
            prefs["Celestial"] += 0.45
            prefs["Standard"] += 0.35
            prefs["Spectral"] += 0.15
        if deck_flags.get("planet_focused"):
            prefs["Celestial"] += 0.35
        if deck_flags.get("spectral_focused"):
            prefs["Spectral"] += 0.35
        if deck_flags.get("flush_focused"):
            prefs["Standard"] += 0.15
        if deck_flags.get("need_early_tempo"):
            prefs["Buffoon"] += 0.20
        for kind, delta in blueprint.get("pack_bias", {}).items():
            prefs[kind] = prefs.get(kind, 0.0) + float(delta)
        return {kind: round(max(0.0, value), 6) for kind, value in prefs.items()}

    def _economy_floor(
        self,
        state: BalatroState,
        *,
        stage: str,
        deck_flags: Mapping[str, Any],
        blueprint: Mapping[str, Any],
    ) -> int:
        if deck_flags.get("ignore_interest") or state.meta.no_interest:
            base = 0 if stage == "stabilization" else 2
        else:
            base = {
                "stabilization": 2 if (state.meta.ante or 1) <= 1 else 4,
                "building": 8,
                "conversion": 6,
                "endgame": 4,
            }.get(stage, 6)
        base += int(blueprint.get("economy_floor_delta", 0))
        if deck_flags.get("need_early_tempo") and stage == "stabilization":
            base -= 1
        return max(0, min(15, base))

    def _reroll_aggression(
        self,
        *,
        stage: str,
        hard_needs: list[str],
        highest_deficit: float,
        deck_flags: Mapping[str, Any],
        blueprint: Mapping[str, Any],
    ) -> float:
        aggression = {
            "stabilization": 0.55,
            "building": 0.50,
            "conversion": 0.65,
            "endgame": 0.60,
        }.get(stage, 0.50)
        aggression += float(blueprint.get("reroll_delta", 0.0))
        aggression += min(0.20, len(hard_needs) * 0.05)
        aggression += min(0.20, max(0.0, highest_deficit - 0.80) * 0.12)
        if deck_flags.get("ignore_interest"):
            aggression += 0.15
        return round(max(0.0, min(1.0, aggression)), 6)
