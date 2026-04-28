import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from config import config
from hand_solver import HandSolver
from rank_utils import get_rank_value
from risk_metrics import (
    cvar_loss,
    effective_sample_size,
    lower_confidence_bound,
    lower_quantile,
    weighted_cvar_loss,
    weighted_mean,
    weighted_quantile,
    weighted_variance,
)
from scorer import Scorer
from state import BalatroState, Card


@dataclass
class MonteCarloStats:
    expected_improvement: float
    clear_probability: float
    clear_probability_lcb: float
    variance: float
    lower_quantile: float
    cvar_loss: float
    mean_score: float
    sample_count: int
    score_stddev: float
    standard_error: float
    confidence_margin: float
    risk_adjusted_improvement: float
    seed_base: int
    rollout_count: int
    rollout_offset: int
    ess: float
    proposal: str
    control_variate: bool

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
            "clear_probability_lcb": self.clear_probability_lcb,
            "variance": self.variance,
            "lower_quantile": self.lower_quantile,
            "cvar_loss": self.cvar_loss,
            "mean_score": self.mean_score,
            "sample_count": self.sample_count,
            "score_stddev": self.score_stddev,
            "standard_error": self.standard_error,
            "confidence_margin": self.confidence_margin,
            "risk_adjusted_improvement": self.risk_adjusted_improvement,
            "seed_base": self.seed_base,
            "rollout_count": self.rollout_count,
            "rollout_offset": self.rollout_offset,
            "ess": self.ess,
            "proposal": self.proposal,
            "control_variate": self.control_variate,
            "sampling_method": "deterministic_shared_sample_pool",
        }


@dataclass(frozen=True)
class SharedSample:
    draw_cards: Tuple[Card, ...]
    nominal_prob: float
    proposal_prob: float
    weight: float
    rollout_index: int
    seed_base: int
    proposal: str


def build_stats_from_weighted_scores(
    scores: Sequence[float],
    weights: Sequence[float],
    *,
    target: float,
    current_best_score: float,
    seed_base: int,
    rollout_count: int,
    rollout_offset: int,
    proposal: str,
    control_variate: bool,
) -> MonteCarloStats:
    if not scores:
        return MonteCarloStats(
            expected_improvement=0.0,
            clear_probability=0.0,
            clear_probability_lcb=0.0,
            variance=0.0,
            lower_quantile=0.0,
            cvar_loss=max(0.0, target),
            mean_score=0.0,
            sample_count=0,
            score_stddev=0.0,
            standard_error=0.0,
            confidence_margin=0.0,
            risk_adjusted_improvement=0.0,
            seed_base=seed_base,
            rollout_count=rollout_count,
            rollout_offset=rollout_offset,
            ess=0.0,
            proposal=proposal,
            control_variate=control_variate,
        )

    weight_list = list(weights) if weights else [1.0] * len(scores)
    if len(weight_list) != len(scores):
        weight_list = [1.0] * len(scores)

    mean_score = weighted_mean(scores, weight_list)
    variance = weighted_variance(scores, weight_list, mean=mean_score)
    score_stddev = math.sqrt(max(0.0, variance))
    ess = effective_sample_size(weight_list)
    effective_n = max(1.0, ess if ess > 0.0 else float(len(scores)))
    standard_error = score_stddev / math.sqrt(effective_n)
    confidence_margin = config.MC_CONFIDENCE_MULTIPLIER * 1.96 * standard_error
    clear_indicators = [1.0 if score >= target else 0.0 for score in scores]
    clear_probability = weighted_mean(clear_indicators, weight_list)
    clear_probability_lcb = lower_confidence_bound(clear_probability, effective_n)
    alpha = getattr(config, "RISK_ALPHA", 0.10)
    lower_q = weighted_quantile(scores, weight_list, alpha)
    tail_loss = weighted_cvar_loss(scores, weight_list, target, alpha)
    expected_improvement = max(0.0, mean_score - current_best_score)
    risk_adjusted_improvement = max(0.0, mean_score - confidence_margin - current_best_score)

    return MonteCarloStats(
        expected_improvement=expected_improvement,
        clear_probability=clear_probability,
        clear_probability_lcb=clear_probability_lcb,
        variance=variance,
        lower_quantile=lower_q,
        cvar_loss=tail_loss,
        mean_score=mean_score,
        sample_count=len(scores),
        score_stddev=score_stddev,
        standard_error=standard_error,
        confidence_margin=confidence_margin,
        risk_adjusted_improvement=risk_adjusted_improvement,
        seed_base=seed_base,
        rollout_count=rollout_count,
        rollout_offset=rollout_offset,
        ess=ess,
        proposal=proposal,
        control_variate=control_variate,
    )


class MonteCarloSimulator:
    def __init__(self, scorer: Scorer, num_rollouts: int = 50, seed: int = 42):
        self.scorer = scorer
        self.num_rollouts = num_rollouts
        self.seed = seed

    def _get_unknown_deck(self, state: BalatroState) -> List[Card]:
        if getattr(state, "deck", None):
            return list(state.deck)

        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
        suits = ["Spades", "Hearts", "Clubs", "Diamonds"]

        full_deck = []
        i = 0
        for rank in ranks:
            for suit in suits:
                base_chips = get_rank_value(rank)
                if rank in {"Jack", "Queen", "King"}:
                    base_chips = 10
                elif rank == "Ace":
                    base_chips = 11
                full_deck.append(
                    Card(
                        id=f"sim_{i}",
                        rank=rank,
                        suit=suit,
                        base_chips=base_chips,
                    )
                )
                i += 1

        known_signatures = {(card.rank, card.suit) for card in state.hand}
        known_signatures.update((card.rank, card.suit) for card in getattr(state, "discard_pile", []))
        return [card for card in full_deck if (card.rank, card.suit) not in known_signatures]

    def _seed_payload(self, state: BalatroState, num_to_draw: int, proposal: str) -> Dict[str, Any]:
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
            "proposal": proposal,
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
        }

    def _root_seed(self, state: BalatroState, num_to_draw: int, proposal: str = "nominal") -> int:
        payload = json.dumps(self._seed_payload(state, num_to_draw, proposal), sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big", signed=False)

    def _rollout_rng(self, seed_base: int, rollout_index: int) -> random.Random:
        mixed = (seed_base + (rollout_index + 1) * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        return random.Random(mixed)

    def _root_proposal_weight(self, card: Card, state: BalatroState) -> float:
        suit_counts = {}
        rank_values = []
        rank_counts = {}
        for hand_card in state.hand:
            suit_counts[hand_card.suit] = suit_counts.get(hand_card.suit, 0) + 1
            rank_counts[hand_card.rank] = rank_counts.get(hand_card.rank, 0) + 1
            rank_values.append(get_rank_value(hand_card.rank))

        weight = 1.0
        weight += suit_counts.get(card.suit, 0) * 0.75
        weight += rank_counts.get(card.rank, 0) * 1.25
        card_value = get_rank_value(card.rank)
        if any(0 < abs(card_value - rank_value) <= 2 for rank_value in rank_values):
            weight += 0.75
        if card.rank in {"Jack", "Queen", "King", "Ace"}:
            weight += 0.25
        if card.enhancement != "None":
            weight += 0.5
        if card.edition != "None":
            weight += 0.4
        if card.seal != "None":
            weight += 0.3
        return max(0.1, weight)

    def _sample_uniform_ordered(self, available_cards: Sequence[Card], rng: random.Random, draw_count: int) -> Tuple[List[Card], float]:
        available = list(available_cards)
        drawn_cards: List[Card] = []
        probability = 1.0
        for _ in range(draw_count):
            if not available:
                break
            probability *= 1.0 / len(available)
            index = rng.randrange(len(available))
            drawn_cards.append(available.pop(index))
        return drawn_cards, probability

    def _sample_weighted_ordered(self, state: BalatroState, available_cards: Sequence[Card], rng: random.Random, draw_count: int) -> Tuple[List[Card], float, float]:
        available = list(available_cards)
        mixture_epsilon = max(0.0, min(1.0, getattr(config, "MC_IS_MIXTURE_EPSILON", 0.35)))
        drawn_cards: List[Card] = []
        nominal_probability = 1.0
        proposal_probability = 1.0

        for _ in range(draw_count):
            if not available:
                break

            raw_weights = [self._root_proposal_weight(card, state) for card in available]
            total_weight = sum(raw_weights)
            probabilities = []
            for raw_weight in raw_weights:
                biased = raw_weight / total_weight if total_weight > 0.0 else 1.0 / len(available)
                probability = ((1.0 - mixture_epsilon) / len(available)) + (mixture_epsilon * biased)
                probabilities.append(probability)

            threshold = rng.random()
            cumulative = 0.0
            choice_index = len(available) - 1
            for index, probability in enumerate(probabilities):
                cumulative += probability
                if threshold <= cumulative:
                    choice_index = index
                    break

            nominal_probability *= 1.0 / len(available)
            proposal_probability *= probabilities[choice_index]
            drawn_cards.append(available.pop(choice_index))

        return drawn_cards, nominal_probability, proposal_probability

    def build_shared_pool(
        self,
        state: BalatroState,
        draw_count: int,
        *,
        rollout_count: Optional[int] = None,
        rollout_offset: int = 0,
        proposal: str = "nominal",
        deck_override: Optional[Sequence[Card]] = None,
    ) -> List[SharedSample]:
        if draw_count <= 0:
            return []

        available = list(deck_override) if deck_override is not None else self._get_unknown_deck(state)
        fallback_discard_pool = list(getattr(state, "discard_pile", []))
        if len(available) < draw_count and fallback_discard_pool:
            available.extend(fallback_discard_pool)
        if len(available) < draw_count:
            return []

        rollouts = rollout_count if rollout_count is not None else self.num_rollouts
        seed_base = self._root_seed(state, draw_count, proposal=proposal)
        pool: List[SharedSample] = []
        for rollout_index in range(rollouts):
            rng = self._rollout_rng(seed_base, rollout_offset + rollout_index)
            if proposal == "nominal":
                drawn_cards, probability = self._sample_uniform_ordered(available, rng, draw_count)
                nominal_probability = probability
                proposal_probability = probability
            else:
                drawn_cards, nominal_probability, proposal_probability = self._sample_weighted_ordered(
                    state,
                    available,
                    rng,
                    draw_count,
                )

            if len(drawn_cards) != draw_count or proposal_probability <= 0.0:
                continue
            pool.append(
                SharedSample(
                    draw_cards=tuple(drawn_cards),
                    nominal_prob=nominal_probability,
                    proposal_prob=proposal_probability,
                    weight=nominal_probability / proposal_probability,
                    rollout_index=rollout_offset + rollout_index,
                    seed_base=seed_base,
                    proposal=proposal,
                )
            )
        return pool

    def _best_score_for_hand(self, state: BalatroState, hand: Sequence[Card]) -> float:
        best_score = 0.0
        hand_list = list(hand)
        for play_combo in HandSolver.enumerate_plays(hand_list):
            played_ids = {card.id for card in play_combo}
            held = [card for card in hand_list if card.id not in played_ids]
            score = float(self.scorer.evaluate_play(play_combo, held, state.jokers, state))
            if score > best_score:
                best_score = score
        return best_score

    def _is_helpful_draw(self, card: Card, base_hand: Sequence[Card]) -> bool:
        if not base_hand:
            return card.rank in {"Ace", "King", "Queen", "Jack"}

        suit_counts: Dict[str, int] = {}
        rank_counts: Dict[str, int] = {}
        rank_values = [get_rank_value(base_card.rank) for base_card in base_hand]
        for base_card in base_hand:
            suit_counts[base_card.suit] = suit_counts.get(base_card.suit, 0) + 1
            rank_counts[base_card.rank] = rank_counts.get(base_card.rank, 0) + 1

        dominant_suit_count = max(suit_counts.values(), default=0)
        if dominant_suit_count >= 2 and suit_counts.get(card.suit, 0) >= dominant_suit_count - 1:
            return True
        if rank_counts.get(card.rank, 0) > 0:
            return True
        card_value = get_rank_value(card.rank)
        if any(0 < abs(card_value - rank_value) <= 2 for rank_value in rank_values):
            return True
        return card.rank in {"Ace", "King", "Queen", "Jack"}

    def _apply_control_variate(
        self,
        scores: Sequence[float],
        weights: Sequence[float],
        proxies: Sequence[float],
        expected_proxy: float,
    ) -> List[float]:
        if not scores or not proxies or len(scores) != len(proxies):
            return list(scores)

        mean_score = weighted_mean(scores, weights)
        mean_proxy = weighted_mean(proxies, weights)
        variance_proxy = weighted_variance(proxies, weights, mean=mean_proxy)
        if variance_proxy <= 1e-9:
            return list(scores)

        total_weight = sum(weights)
        covariance = 0.0
        for score, proxy, weight in zip(scores, proxies, weights):
            covariance += weight * (score - mean_score) * (proxy - mean_proxy)
        covariance /= total_weight if total_weight > 0.0 else 1.0
        beta = covariance / variance_proxy
        return [score - beta * (proxy - expected_proxy) for score, proxy in zip(scores, proxies)]

    def evaluate_discard_with_pool(
        self,
        state: BalatroState,
        discard_ids: Set[str],
        current_best_score: float,
        pool: Sequence[SharedSample],
        *,
        use_control_variate: bool = False,
    ) -> MonteCarloStats:
        draw_count = len(discard_ids)
        base_hand = [card for card in state.hand if card.id not in discard_ids]
        if draw_count <= 0:
            return build_stats_from_weighted_scores(
                [],
                [],
                target=state.blind.target_score - state.blind.current_score,
                current_best_score=current_best_score,
                seed_base=0,
                rollout_count=0,
                rollout_offset=0,
                proposal="nominal",
                control_variate=False,
            )

        raw_scores: List[float] = []
        weights: List[float] = []
        proxies: List[float] = []
        draw_deck = self._get_unknown_deck(state)
        helpful_cards = sum(1 for card in draw_deck if self._is_helpful_draw(card, base_hand))
        expected_proxy = draw_count * helpful_cards / max(1, len(draw_deck))

        for sample in pool:
            sim_hand = base_hand + list(sample.draw_cards)
            raw_scores.append(self._best_score_for_hand(state, sim_hand))
            weights.append(sample.weight)
            if use_control_variate:
                proxies.append(float(sum(1 for card in sample.draw_cards if self._is_helpful_draw(card, base_hand))))

        adjusted_scores = raw_scores
        control_variate_used = False
        if use_control_variate and proxies:
            adjusted_scores = self._apply_control_variate(raw_scores, weights, proxies, expected_proxy)
            control_variate_used = True

        seed_base = pool[0].seed_base if pool else self._root_seed(state, draw_count)
        rollout_offset = pool[0].rollout_index if pool else 0
        proposal = pool[0].proposal if pool else "nominal"
        target = state.blind.target_score - state.blind.current_score
        return build_stats_from_weighted_scores(
            adjusted_scores,
            weights,
            target=target,
            current_best_score=current_best_score,
            seed_base=seed_base,
            rollout_count=len(adjusted_scores),
            rollout_offset=rollout_offset,
            proposal=proposal,
            control_variate=control_variate_used,
        )

    def simulate_discard_scores(
        self,
        state: BalatroState,
        discard_ids: Set[str],
        *,
        rollout_count: Optional[int] = None,
        rollout_offset: int = 0,
    ) -> Tuple[List[float], int]:
        draw_count = len(discard_ids)
        pool = self.build_shared_pool(
            state,
            draw_count,
            rollout_count=rollout_count,
            rollout_offset=rollout_offset,
            proposal="nominal",
        )
        base_hand = [card for card in state.hand if card.id not in discard_ids]
        scores = [self._best_score_for_hand(state, base_hand + list(sample.draw_cards)) for sample in pool]
        seed_base = pool[0].seed_base if pool else self._root_seed(state, draw_count)
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
        return build_stats_from_weighted_scores(
            scores,
            [1.0] * len(scores),
            target=target,
            current_best_score=current_best_score,
            seed_base=seed_base,
            rollout_count=rollout_count,
            rollout_offset=rollout_offset,
            proposal="nominal",
            control_variate=False,
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
        stats = self.estimate_discard(
            state,
            discard_ids,
            current_best_score,
            rollout_count=dynamic_cap if dynamic_cap is not None else self.num_rollouts,
        )
        return stats.as_tuple()
