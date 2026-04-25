import itertools
from typing import List, Iterator
from state import Card

class HandSolver:
    @staticmethod
    def enumerate_plays(hand: List[Card], min_size: int = 1, max_size: int = 5) -> Iterator[List[Card]]:
        num_cards = len(hand)
        for k in range(min_size, min(num_cards, max_size) + 1):
            for combo in itertools.combinations(hand, k):
                yield list(combo)
