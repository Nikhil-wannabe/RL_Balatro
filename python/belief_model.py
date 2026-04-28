import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from boss_logic import boss_profile_from_state
from rank_utils import get_rank_value
from state import BalatroState, Card, Joker


RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace")
SUITS = ("Spades", "Hearts", "Clubs", "Diamonds")


def _card_signature(card: Card) -> Tuple[str, str, str, str, str]:
    return (card.rank, card.suit, card.enhancement, card.edition, card.seal)


def _card_bucket(card: Card) -> str:
    return f"{card.rank}|{card.suit}|{card.enhancement}|{card.edition}|{card.seal}"


def _full_standard_deck() -> List[Card]:
    cards: List[Card] = []
    index = 0
    for rank in RANKS:
        for suit in SUITS:
            base_chips = get_rank_value(rank)
            if rank in {"Jack", "Queen", "King"}:
                base_chips = 10
            elif rank == "Ace":
                base_chips = 11
            cards.append(
                Card(
                    id=f"belief_{index}",
                    rank=rank,
                    suit=suit,
                    base_chips=base_chips,
                )
            )
            index += 1
    return cards


@dataclass(frozen=True)
class DeckParticle:
    cards: Tuple[Card, ...]
    weight: float
    source: str

    @property
    def category_counts(self) -> Dict[str, int]:
        return dict(sorted(Counter(_card_bucket(card) for card in self.cards).items()))


@dataclass(frozen=True)
class RulePosterior:
    model_id: str
    weight: float
    score_scale: float
    clear_penalty: float
    optimism_class: str
    unresolved_jokers: int


@dataclass(frozen=True)
class BeliefState:
    deck_particles: Tuple[DeckParticle, ...]
    rule_models: Tuple[RulePosterior, ...]
    posterior_entropy: float
    known_deck: bool
    unresolved_jokers: int


class BeliefModel:
    def _observed_cards(self, state: BalatroState) -> List[Card]:
        cards: List[Card] = []
        cards.extend(list(getattr(state, "hand", [])))
        cards.extend(list(getattr(state, "discard_pile", [])))
        cards.extend(list(getattr(state, "deck", [])))
        return cards

    def infer_unknown_deck(self, state: BalatroState) -> List[Card]:
        if getattr(state, "deck", None):
            return list(state.deck)

        full_deck = _full_standard_deck()
        seen_counter = Counter((card.rank, card.suit) for card in self._observed_cards(state))
        inferred: List[Card] = []
        for card in full_deck:
            key = (card.rank, card.suit)
            if seen_counter[key] > 0:
                seen_counter[key] -= 1
            else:
                inferred.append(card)
        return inferred

    def _posterior_entropy(self, weights: Sequence[float]) -> float:
        entropy = 0.0
        for weight in weights:
            if weight > 0.0:
                entropy -= weight * math.log(weight)
        return entropy

    def _rule_models(self, state: BalatroState) -> Tuple[RulePosterior, ...]:
        unresolved = sum(1 for joker in state.jokers if not joker.is_debuffed)
        boss_profile = boss_profile_from_state(state)
        if unresolved <= 0:
            return (
                RulePosterior(
                    model_id="nominal",
                    weight=1.0,
                    score_scale=1.0,
                    clear_penalty=boss_profile.joker_uncertainty_penalty,
                    optimism_class="nominal",
                    unresolved_jokers=0,
                ),
            )

        lower_penalty = min(0.35, 0.035 * unresolved)
        nominal_penalty = min(0.18, 0.015 * unresolved)
        upper_bonus = min(0.08, 0.01 * unresolved)
        lower_penalty = min(0.50, lower_penalty + boss_profile.joker_uncertainty_penalty)
        nominal_penalty = min(0.30, nominal_penalty + (boss_profile.joker_uncertainty_penalty * 0.6))
        return (
            RulePosterior(
                model_id="lower",
                weight=0.25,
                score_scale=1.0,
                clear_penalty=lower_penalty,
                optimism_class="lower",
                unresolved_jokers=unresolved,
            ),
            RulePosterior(
                model_id="nominal",
                weight=0.55,
                score_scale=1.0,
                clear_penalty=nominal_penalty,
                optimism_class="nominal",
                unresolved_jokers=unresolved,
            ),
            RulePosterior(
                model_id="upper",
                weight=0.20,
                score_scale=1.0,
                clear_penalty=0.0,
                optimism_class="upper",
                unresolved_jokers=unresolved,
            ),
        )

    def from_state(self, state: BalatroState) -> BeliefState:
        if getattr(state, "deck", None):
            particles = (
                DeckParticle(cards=tuple(state.deck), weight=1.0, source="observed_draw_pile"),
            )
            known_deck = True
        else:
            inferred = self.infer_unknown_deck(state)
            particles = (
                DeckParticle(cards=tuple(inferred), weight=1.0, source="standard_deck_minus_seen"),
            )
            known_deck = False

        rule_models = self._rule_models(state)
        weights = [particle.weight for particle in particles] + [model.weight for model in rule_models]
        entropy = self._posterior_entropy(weights)
        unresolved = max((model.unresolved_jokers for model in rule_models), default=0)
        return BeliefState(
            deck_particles=particles,
            rule_models=rule_models,
            posterior_entropy=entropy,
            known_deck=known_deck,
            unresolved_jokers=unresolved,
        )

    def posterior_predictive(
        self,
        belief: BeliefState,
        draw_count: int,
        n: int,
        seed: int,
    ) -> List[DeckParticle]:
        if not belief.deck_particles or n <= 0 or draw_count <= 0:
            return []
        return list(belief.deck_particles[: min(n, len(belief.deck_particles))])

    def robust_subset(self, belief: BeliefState) -> BeliefState:
        robust_models = tuple(model for model in belief.rule_models if model.optimism_class in {"lower", "nominal"})
        if not robust_models:
            robust_models = belief.rule_models
        entropy = self._posterior_entropy([particle.weight for particle in belief.deck_particles] + [model.weight for model in robust_models])
        return BeliefState(
            deck_particles=belief.deck_particles,
            rule_models=robust_models,
            posterior_entropy=entropy,
            known_deck=belief.known_deck,
            unresolved_jokers=belief.unresolved_jokers,
        )
