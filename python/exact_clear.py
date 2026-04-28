import itertools
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from belief_model import BeliefState
from config import config
from hand_solver import HandSolver
from monte_carlo import MonteCarloStats, build_stats_from_weighted_scores
from scorer import Scorer
from state import BalatroState, Card


def multivariate_hypergeometric_pmf(category_totals: Dict[str, int], draw_counts: Dict[str, int], sample_size: int) -> float:
    total_population = sum(category_totals.values())
    if sample_size < 0 or sample_size > total_population:
        return 0.0
    if sum(draw_counts.values()) != sample_size:
        return 0.0

    numerator = 1
    for category, total in category_totals.items():
        draw = draw_counts.get(category, 0)
        if draw < 0 or draw > total:
            return 0.0
        numerator *= math.comb(total, draw)

    denominator = math.comb(total_population, sample_size)
    if denominator <= 0:
        return 0.0
    return numerator / denominator


@dataclass
class ExactSolveResult:
    stats: MonteCarloStats
    combinations_evaluated: int
    category_counts: Dict[str, int]
    method: str


class ExactClearSolver:
    def __init__(self, scorer: Scorer, exact_draw_enum_cap: int):
        self.scorer = scorer
        self.exact_draw_enum_cap = exact_draw_enum_cap

    def can_exact_enumerate(self, deck_size: int, draw_count: int) -> bool:
        if draw_count < 0 or draw_count > deck_size:
            return False
        return math.comb(deck_size, draw_count) <= self.exact_draw_enum_cap

    def _card_bucket(self, card: Card) -> Tuple:
        return (
            card.rank,
            card.suit,
            int(card.base_chips),
            card.enhancement,
            card.edition,
            card.seal,
            bool(card.is_debuffed),
        )

    def _hand_signature(self, cards: Sequence[Card]) -> Tuple:
        return tuple(sorted(self._card_bucket(card) for card in cards))

    def _best_score_for_hand(self, sim_hand: Sequence[Card], state: BalatroState) -> float:
        best_score = 0.0
        sim_hand_list = list(sim_hand)
        for play_combo in HandSolver.enumerate_plays(sim_hand_list):
            played_ids = {card.id for card in play_combo}
            held_cards = [card for card in sim_hand_list if card.id not in played_ids]
            score = float(self.scorer.evaluate_play(play_combo, held_cards, state.jokers, state))
            if score > best_score:
                best_score = score
        return best_score

    def _group_deck_cards(self, deck_cards: Sequence[Card]) -> List[Tuple[Tuple, List[Card]]]:
        grouped: Dict[Tuple, List[Card]] = defaultdict(list)
        for card in deck_cards:
            grouped[self._card_bucket(card)].append(card)
        return sorted(grouped.items(), key=lambda item: item[0])

    def _count_category_states(self, totals: Sequence[int], draw_count: int) -> int:
        @lru_cache(maxsize=None)
        def dp(index: int, remaining: int) -> int:
            if remaining < 0:
                return 0
            if index == len(totals):
                return 1 if remaining == 0 else 0
            total = totals[index]
            ways = 0
            for take in range(0, min(total, remaining) + 1):
                ways += dp(index + 1, remaining - take)
                if ways > config.EXACT_STATE_CAP:
                    return ways
            return ways

        return dp(0, draw_count)

    def _score_sim_hands_parallel(self, sim_hands: Sequence[Sequence[Card]], state: BalatroState) -> List[float]:
        if not sim_hands:
            return []
        return [self._best_score_for_hand(sim_hand, state) for sim_hand in sim_hands]

    def _score_sim_hands(
        self,
        sim_hands: Sequence[Sequence[Card]],
        state: BalatroState,
        *,
        allow_parallel: bool,
    ) -> List[float]:
        if not sim_hands:
            return []
        if (
            not allow_parallel
            or not config.PARALLEL_CANDIDATE_EVAL
            or config.PARALLEL_WORKERS <= 1
            or len(sim_hands) < config.EXACT_PARALLEL_MIN_STATES
        ):
            return [self._best_score_for_hand(sim_hand, state) for sim_hand in sim_hands]

        with ThreadPoolExecutor(max_workers=max(1, config.PARALLEL_WORKERS), thread_name_prefix="balatro-exact") as executor:
            return list(executor.map(lambda hand: self._best_score_for_hand(hand, state), sim_hands))

    def _exact_stats_from_category_vectors(
        self,
        state: BalatroState,
        deck_cards: Sequence[Card],
        base_hand: Sequence[Card],
        draw_count: int,
        current_best_score: float,
        *,
        allow_parallel: bool,
    ) -> ExactSolveResult | None:
        grouped = self._group_deck_cards(deck_cards)
        if len(grouped) > config.EXACT_CATEGORY_CAP:
            return None

        totals = [len(cards) for _, cards in grouped]
        state_count = self._count_category_states(tuple(totals), draw_count)
        if state_count <= 0 or state_count > config.EXACT_STATE_CAP:
            return None

        denominator = math.comb(len(deck_cards), draw_count)
        if denominator <= 0:
            return None

        bucket_names = ["|".join(map(str, bucket)) for bucket, _ in grouped]
        category_totals = {name: total for name, total in zip(bucket_names, totals)}
        draw_vectors: List[Dict[str, int]] = []
        sim_hands: List[List[Card]] = []

        def recurse(index: int, remaining: int, current_draws: Dict[str, int], current_cards: List[Card]) -> None:
            if len(draw_vectors) > config.EXACT_STATE_CAP:
                return
            if index == len(grouped):
                if remaining == 0:
                    draw_vectors.append(dict(current_draws))
                    sim_hands.append(list(base_hand) + list(current_cards))
                return

            _, bucket_cards = grouped[index]
            bucket_name = bucket_names[index]
            max_take = min(len(bucket_cards), remaining)
            for take in range(0, max_take + 1):
                if take > 0:
                    current_draws[bucket_name] = take
                    current_cards.extend(bucket_cards[:take])
                recurse(index + 1, remaining - take, current_draws, current_cards)
                if take > 0:
                    del current_draws[bucket_name]
                    del current_cards[-take:]

        recurse(0, draw_count, {}, [])
        if not sim_hands:
            return None

        raw_scores = self._score_sim_hands(sim_hands, state, allow_parallel=allow_parallel)
        weights = [
            multivariate_hypergeometric_pmf(category_totals, draw_counts, draw_count)
            for draw_counts in draw_vectors
        ]
        stats = build_stats_from_weighted_scores(
            raw_scores,
            weights,
            target=state.blind.target_score - state.blind.current_score,
            current_best_score=current_best_score,
            seed_base=0,
            rollout_count=len(raw_scores),
            rollout_offset=0,
            proposal="exact_category_aggregation",
            control_variate=False,
        )
        return ExactSolveResult(
            stats=stats,
            combinations_evaluated=len(raw_scores),
            category_counts=category_totals,
            method="exact_category_aggregation",
        )

    def _exact_stats_from_raw_combinations(
        self,
        state: BalatroState,
        deck_cards: Sequence[Card],
        base_hand: Sequence[Card],
        draw_count: int,
        current_best_score: float,
        *,
        allow_parallel: bool,
    ) -> ExactSolveResult:
        combos = [tuple(combo) for combo in itertools.combinations(deck_cards, draw_count)]
        sim_hands = [list(base_hand) + list(combo) for combo in combos]
        raw_scores = self._score_sim_hands(sim_hands, state, allow_parallel=allow_parallel)
        stats = build_stats_from_weighted_scores(
            raw_scores,
            [1.0] * len(raw_scores),
            target=state.blind.target_score - state.blind.current_score,
            current_best_score=current_best_score,
            seed_base=0,
            rollout_count=len(raw_scores),
            rollout_offset=0,
            proposal="exact_enumeration",
            control_variate=False,
        )
        grouped = self._group_deck_cards(deck_cards)
        return ExactSolveResult(
            stats=stats,
            combinations_evaluated=len(raw_scores),
            category_counts={("|".join(map(str, bucket))): len(cards) for bucket, cards in grouped},
            method="exact_draw_enumeration",
        )

    def exact_discard_stats(
        self,
        state: BalatroState,
        belief: BeliefState,
        discard_ids: Set[str],
        current_best_score: float,
        *,
        allow_parallel: bool = True,
    ) -> ExactSolveResult | None:
        draw_count = len(discard_ids)
        if draw_count <= 0 or not belief.deck_particles or not belief.known_deck:
            return None

        deck_cards = list(belief.deck_particles[0].cards)
        if not self.can_exact_enumerate(len(deck_cards), draw_count):
            return None

        base_hand = [card for card in state.hand if card.id not in discard_ids]
        category_result = self._exact_stats_from_category_vectors(
            state,
            deck_cards,
            base_hand,
            draw_count,
            current_best_score,
            allow_parallel=allow_parallel,
        )
        if category_result is not None:
            return category_result

        return self._exact_stats_from_raw_combinations(
            state,
            deck_cards,
            base_hand,
            draw_count,
            current_best_score,
            allow_parallel=allow_parallel,
        )
