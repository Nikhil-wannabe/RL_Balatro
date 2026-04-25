import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from config import config
from hand_solver import HandSolver
from rank_utils import get_rank_value
from scorer import Scorer
from state import BalatroState, Card


@dataclass
class MonteCarloStats:
    expected_improvement: float
    clear_probability: float
    variance: float
    lower_quantile: float
    mean_score: float
    sample_count: int
    score_stddev: float
    standard_error: float
    confidence_margin: float
    risk_adjusted_improvement: float
    seed_base: int
    rollout_count: int
    rollout_offset: int

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (
            self.expected_improvement,
            self.clear_probability,
            self.variance,
            self.lower_quantile,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "expected_improvement": self.expected_improvement,
            "clear_probability": self.clear_probability,
            "variance": self.variance,
            "lower_quantile": self.lower_quantile,
            "mean_score": self.mean_score,
            "sample_count": self.sample_count,
            "score_stddev": self.score_stddev,
            "standard_error": self.standard_error,
            "confidence_margin": self.confidence_margin,
            "risk_adjusted_improvement": self.risk_adjusted_improvement,
            "seed_base": self.seed_base,
            "rollout_count": self.rollout_count,
            "rollout_offset": self.rollout_offset,
            "sampling_method": "state_seeded_common_random_numbers",
        }


class MonteCarloSimulator:
    def __init__(self, scorer: Scorer, num_rollouts: int = 50, seed: int = 42):
        self.scorer = scorer
        self.num_rollouts = num_rollouts
        self.seed = seed

    def _get_unknown_deck(self, state: BalatroState) -> List[Card]:
        """Use the exact remaining draw pile when available, otherwise approximate from a standard deck."""
        if getattr(state, "deck", None):
            return list(state.deck)

        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
        suits = ["Spades", "Hearts", "Clubs", "Diamonds"]

        full_deck = []
        i = 0
        for rank in ranks:
            for suit in suits:
                full_deck.append(
                    Card(
                        id=f"sim_{i}",
                        rank=rank,
                        suit=suit,
                        base_chips=get_rank_value(rank) if get_rank_value(rank) <= 10 else (11 if rank == "Ace" else 10),
                    )
                )
                i += 1

        known_signatures = {(card.rank, card.suit) for card in state.hand}
        return [card for card in full_deck if (card.rank, card.suit) not in known_signatures]

    def _seed_payload(self, state: BalatroState, num_to_draw: int) -> Dict[str, Any]:
        return {
            "base_seed": self.seed,
            "seed": state.meta.seed,
            "ante": state.meta.ante,
            "round": state.meta.round,
            "phase": state.meta.phase,
            "stake": state.meta.stake,
            "target_score": state.blind.target_score,
            "current_score": state.blind.current_score,
            "hands_left": state.economy.hands_left,
            "discards_left": state.economy.discards_left,
            "hand_size": state.economy.hand_size,
            "num_to_draw": num_to_draw,
            "hand": sorted(
                f"{card.id}|{card.rank}|{card.suit}|{card.enhancement}|{card.edition}|{card.seal}"
                for card in state.hand
            ),
            "deck": sorted(
                f"{card.id}|{card.rank}|{card.suit}|{card.enhancement}|{card.edition}|{card.seal}"
                for card in getattr(state, "deck", [])
            ),
            "discard_pile": sorted(
                f"{card.id}|{card.rank}|{card.suit}|{card.enhancement}|{card.edition}|{card.seal}"
                for card in getattr(state, "discard_pile", [])
            ),
            "jokers": sorted(
                f"{joker.id}|{joker.name}|{joker.edition}|{joker.is_eternal}|{joker.is_perishable}|{joker.is_rental}"
                for joker in state.jokers
            ),
        }

    def _root_seed(self, state: BalatroState, num_to_draw: int) -> int:
        payload = json.dumps(self._seed_payload(state, num_to_draw), sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big", signed=False)

    def _rollout_rng(self, seed_base: int, rollout_index: int) -> random.Random:
        mixed = (seed_base + (rollout_index + 1) * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        return random.Random(mixed)

    def simulate_discard_scores(
        self,
        state: BalatroState,
        discard_ids: Set[str],
        *,
        rollout_count: Optional[int] = None,
        rollout_offset: int = 0,
    ) -> Tuple[List[float], int]:
        unknown_deck = self._get_unknown_deck(state)
        fallback_discard_pool = list(getattr(state, "discard_pile", []))

        base_hand = [card for card in state.hand if card.id not in discard_ids]
        num_to_draw = len(discard_ids)
        if num_to_draw <= 0:
            return [], self._root_seed(state, 0)

        seed_base = self._root_seed(state, num_to_draw)
        scores: List[float] = []
        rollouts = rollout_count if rollout_count is not None else self.num_rollouts

        for rollout_index in range(rollout_count or rollouts):
            rng = self._rollout_rng(seed_base, rollout_offset + rollout_index)
            available = list(unknown_deck)
            if len(available) < num_to_draw and fallback_discard_pool:
                available.extend(fallback_discard_pool)
            if len(available) < num_to_draw:
                continue

            drawn_cards = rng.sample(available, num_to_draw)
            sim_hand = base_hand + drawn_cards

            best_sim_score = 0.0
            for play_combo in HandSolver.enumerate_plays(sim_hand):
                played_ids = {card.id for card in play_combo}
                held = [card for card in sim_hand if card.id not in played_ids]
                score = float(self.scorer.evaluate_play(play_combo, held, state.jokers))
                if score > best_sim_score:
                    best_sim_score = score

            scores.append(best_sim_score)

        return scores, seed_base

    def summarize_scores(
        self,
        scores: List[float],
        *,
        target: float,
        current_best_score: float,
        seed_base: int,
        rollout_count: int,
        rollout_offset: int = 0,
    ) -> MonteCarloStats:
        if not scores:
            return MonteCarloStats(
                expected_improvement=0.0,
                clear_probability=0.0,
                variance=0.0,
                lower_quantile=0.0,
                mean_score=0.0,
                sample_count=0,
                score_stddev=0.0,
                standard_error=0.0,
                confidence_margin=0.0,
                risk_adjusted_improvement=0.0,
                seed_base=seed_base,
                rollout_count=rollout_count,
                rollout_offset=rollout_offset,
            )

        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        score_stddev = math.sqrt(variance)
        standard_error = score_stddev / math.sqrt(len(scores))
        confidence_margin = config.MC_CONFIDENCE_MULTIPLIER * 1.96 * standard_error
        clear_probability = sum(1 for score in scores if score >= target) / len(scores)
        sorted_scores = sorted(scores)
        lower_index = min(len(sorted_scores) - 1, int(len(sorted_scores) * 0.1))
        lower_quantile = sorted_scores[lower_index]
        expected_improvement = max(0.0, mean_score - current_best_score)
        risk_adjusted_improvement = max(0.0, mean_score - confidence_margin - current_best_score)

        return MonteCarloStats(
            expected_improvement=expected_improvement,
            clear_probability=clear_probability,
            variance=variance,
            lower_quantile=lower_quantile,
            mean_score=mean_score,
            sample_count=len(scores),
            score_stddev=score_stddev,
            standard_error=standard_error,
            confidence_margin=confidence_margin,
            risk_adjusted_improvement=risk_adjusted_improvement,
            seed_base=seed_base,
            rollout_count=rollout_count,
            rollout_offset=rollout_offset,
        )

    def estimate_discard(
        self,
        state: BalatroState,
        discard_ids: Set[str],
        current_best_score: float,
        *,
        rollout_count: Optional[int] = None,
        rollout_offset: int = 0,
        existing_scores: Optional[List[float]] = None,
    ) -> MonteCarloStats:
        scores = list(existing_scores or [])
        fresh_scores, seed_base = self.simulate_discard_scores(
            state,
            discard_ids,
            rollout_count=rollout_count,
            rollout_offset=rollout_offset,
        )
        scores.extend(fresh_scores)
        target = state.blind.target_score - state.blind.current_score
        return self.summarize_scores(
            scores,
            target=target,
            current_best_score=current_best_score,
            seed_base=seed_base,
            rollout_count=rollout_count if rollout_count is not None else self.num_rollouts,
            rollout_offset=rollout_offset,
        )

    def evaluate_discard(
        self,
        state: BalatroState,
        discard_ids: Set[str],
        current_best_score: float,
        dynamic_cap: int = None,
    ) -> Tuple[float, float, float, float]:
        """Returns (expected_improvement, clear_prob, variance, lower_quantile)."""
        stats = self.estimate_discard(
            state,
            discard_ids,
            current_best_score,
            rollout_count=dynamic_cap if dynamic_cap is not None else self.num_rollouts,
        )
        return stats.as_tuple()
