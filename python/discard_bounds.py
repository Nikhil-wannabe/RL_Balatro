from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Sequence, Tuple

from belief_model import BeliefState
from hand_solver import HandSolver
from rank_utils import get_rank_value
from scorer import Scorer
from state import BalatroState, Card


@dataclass
class BoundDiagnostics:
    generated_nodes: int
    memo_hits: int
    sound_prunes: int
    heuristic_prunes: int


class DiscardBounder:
    def __init__(self, scorer: Scorer):
        self.scorer = scorer
        self._memo_hits = 0

    def _max_card_chip_value(self, cards: Sequence[Card]) -> float:
        if not cards:
            return 0.0
        max_card_value = 0.0
        for card in cards:
            value = float(card.base_chips)
            if card.edition == "Foil":
                value += 50.0
            if card.enhancement == "Mult":
                value += 12.0
            if card.enhancement == "Glass":
                value += 20.0
            max_card_value = max(max_card_value, value)
        return max_card_value

    def optimistic_round_clear_upper_bound(
        self,
        state: BalatroState,
        kept_cards: Sequence[Card],
        draw_count: int,
        belief: BeliefState,
    ) -> float:
        particle_cards = list(belief.deck_particles[0].cards) if belief.deck_particles else []
        available = list(kept_cards) + particle_cards
        top_card_value = self._max_card_chip_value(available)
        top_steel_count = sum(1 for card in available if card.enhancement == "Steel")
        optimistic_chips = 100.0 + 5.0 * top_card_value
        optimistic_mult = 8.0 * (1.5 ** min(3, top_steel_count))
        optimistic_score = optimistic_chips * optimistic_mult
        return optimistic_score * max(1, state.economy.hands_left)

    def branch_and_bound_candidates(
        self,
        state: BalatroState,
        belief: BeliefState,
        *,
        max_discard_size: int,
        target_remaining: float,
        candidate_limit: int,
    ) -> Tuple[List[List[Card]], BoundDiagnostics]:
        hand = list(state.hand)
        max_discard_size = min(max_discard_size, len(hand))
        generated: List[Tuple[Tuple[str, ...], float, List[Card]]] = []
        self._memo_hits = 0
        sound_prunes = 0
        generated_nodes = 0

        ordered_hand = sorted(
            hand,
            key=lambda card: (
                get_rank_value(card.rank),
                card.suit,
                card.id,
            ),
        )

        @lru_cache(maxsize=512)
        def _upper_bound(kept_ids: Tuple[str, ...], draw_count: int) -> float:
            kept = [card for card in ordered_hand if card.id in kept_ids]
            return self.optimistic_round_clear_upper_bound(state, kept, draw_count, belief)

        def _search(index: int, kept: List[Card], discarded: List[Card]) -> None:
            nonlocal sound_prunes, generated_nodes
            generated_nodes += 1

            if len(discarded) > max_discard_size:
                return

            if index == len(ordered_hand):
                if discarded:
                    key = tuple(sorted(card.id for card in kept))
                    if _upper_bound.cache_info().hits > self._memo_hits:
                        self._memo_hits = _upper_bound.cache_info().hits
                    upper = _upper_bound(key, len(discarded))
                    if upper < target_remaining:
                        sound_prunes += 1
                        return
                    priority = sum(get_rank_value(card.rank) for card in discarded) + len(discarded) * 0.1
                    generated.append((tuple(sorted(card.id for card in discarded)), priority, list(discarded)))
                return

            card = ordered_hand[index]

            _search(index + 1, kept + [card], discarded)
            _search(index + 1, kept, discarded + [card])

        _search(0, [], [])

        generated.sort(key=lambda item: (item[1], len(item[2]), item[0]))
        unique_candidates: List[List[Card]] = []
        seen = set()
        for signature, _, cards in generated:
            if signature in seen:
                continue
            seen.add(signature)
            unique_candidates.append(cards)
            if len(unique_candidates) >= candidate_limit:
                break

        diagnostics = BoundDiagnostics(
            generated_nodes=generated_nodes,
            memo_hits=self._memo_hits,
            sound_prunes=sound_prunes,
            heuristic_prunes=max(0, len(generated) - len(unique_candidates)),
        )
        return unique_candidates, diagnostics
