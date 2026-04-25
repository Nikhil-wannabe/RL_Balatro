from typing import List, Tuple
from state import Card, Joker
from rank_utils import get_rank_value

class Scorer:
    BASE_SCORES = {
        "Straight Flush": (100, 8),
        "Four of a Kind": (60, 7),
        "Full House": (40, 4),
        "Flush": (35, 4),
        "Straight": (30, 4),
        "Three of a Kind": (30, 3),
        "Two Pair": (20, 2),
        "Pair": (10, 2),
        "High Card": (5, 1)
    }

    def evaluate_play(self, played_cards: List[Card], held_cards: List[Card], jokers: List[Joker]) -> int:
        if not played_cards: return 0
        
        # 1. Poker Hand Classification
        hand_type, scoring_cards = self.classify_hand(played_cards)
        base_chips, base_mult = self.BASE_SCORES.get(hand_type, (5, 1))
        
        chips = base_chips
        mult = base_mult

        # 2. Played Cards Loop (Only scoring cards contribute base chips and trigger)
        # Preserve played-card order for scoring
        ordered_scoring = [c for c in played_cards if c in scoring_cards]

        for card in ordered_scoring:
            if card.is_debuffed: continue
            chips += card.base_chips
            
            # Enhancement Hooks
            if card.enhancement == "Mult": mult += 4
            elif card.enhancement == "Glass": mult *= 2
            # TODO: Handle Retriggers here (e.g., Red Seal)
            
            # Edition Hooks
            if card.edition == "Foil": chips += 50
            elif card.edition == "Holo": mult += 10
            elif card.edition == "Polychrome": mult *= 1.5

        # 3. Held Cards Loop
        for card in held_cards:
            if card.is_debuffed: continue
            if card.enhancement == "Steel": mult *= 1.5
            # TODO: Handle Retriggers for held cards (e.g. Mime)

        # 4. Jokers Loop
        for joker in jokers:
            if joker.is_debuffed: continue
            # TODO: Exact Joker effects based on internal_state and name
            if joker.edition == "Foil": chips += 50
            elif joker.edition == "Holo": mult += 10
            elif joker.edition == "Polychrome": mult *= 1.5
            # TODO: Retriggers for jokers (e.g., Blueprint, Brainstorm)

        return int(chips * mult)

    def classify_hand(self, cards: List[Card]) -> Tuple[str, List[Card]]:
        if not cards: return "High Card", []
        
        # Sort by rank value descending for straight detection
        sorted_cards = sorted(cards, key=lambda c: get_rank_value(c.rank), reverse=True)
        ranks = [c.rank for c in sorted_cards]
        suits = [c.suit for c in sorted_cards]
        
        rank_counts = {}
        for c in sorted_cards: rank_counts[c.rank] = rank_counts.get(c.rank, 0) + 1
        
        counts = sorted(list(rank_counts.values()), reverse=True)
        
        # Flush logic: Needs at least 5 cards of the same suit
        suit_counts = {}
        for s in suits: suit_counts[s] = suit_counts.get(s, 0) + 1
        is_flush = any(count >= 5 for count in suit_counts.values())
        flush_suit = next((s for s, count in suit_counts.items() if count >= 5), None)
        flush_cards = [c for c in sorted_cards if c.suit == flush_suit][:5] if is_flush else []

        # Straight logic
        is_straight = False
        straight_cards = []
        
        # Unique ranks sorted descending
        unique_vals = sorted(list(set([get_rank_value(r) for r in ranks])), reverse=True)
        if len(unique_vals) >= 5:
            for i in range(len(unique_vals) - 4):
                if unique_vals[i] - unique_vals[i+4] == 4:
                    is_straight = True
                    target_vals = unique_vals[i:i+5]
                    break
            # Ace-low straight check: Ace(14), 5, 4, 3, 2
            if not is_straight and 14 in unique_vals and all(v in unique_vals for v in [5, 4, 3, 2]):
                is_straight = True
                target_vals = [5, 4, 3, 2, 14]
                
            if is_straight:
                for v in target_vals:
                    # Append the first card that matches this rank
                    for c in sorted_cards:
                        if get_rank_value(c.rank) == v and c not in straight_cards:
                            straight_cards.append(c)
                            break

        if is_flush and is_straight:
            # Need to check if the straight is entirely within the flush suit
            sf_cards = [c for c in straight_cards if c.suit == flush_suit]
            if len(sf_cards) == 5:
                return "Straight Flush", sf_cards

        if counts[0] == 4: 
            quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
            scoring = [c for c in sorted_cards if c.rank == quad_rank]
            return "Four of a Kind", scoring
            
        if len(counts) >= 2 and counts[0] == 3 and counts[1] >= 2: 
            trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
            pair_rank = [r for r, c in rank_counts.items() if c >= 2 and r != trip_rank][0]
            scoring = [c for c in sorted_cards if c.rank in (trip_rank, pair_rank)][:5]
            return "Full House", scoring
            
        if is_flush: return "Flush", flush_cards
        if is_straight: return "Straight", straight_cards
        
        if counts[0] == 3: 
            trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
            scoring = [c for c in sorted_cards if c.rank == trip_rank]
            return "Three of a Kind", scoring
            
        if counts[:2] == [2, 2]: 
            pair_ranks = [r for r, c in rank_counts.items() if c == 2][:2]
            scoring = [c for c in sorted_cards if c.rank in pair_ranks]
            return "Two Pair", scoring
            
        if counts[0] == 2: 
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            scoring = [c for c in sorted_cards if c.rank == pair_rank]
            return "Pair", scoring

        # High Card
        return "High Card", [sorted_cards[0]]
