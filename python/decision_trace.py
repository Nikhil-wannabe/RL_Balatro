import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from action_types import ActionResponse
from config import config
from state import BalatroState, Card, Joker


def _counter_dict(values: Iterable[str]) -> Dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _summarize_cards(cards: Iterable[Card]) -> Dict[str, Any]:
    card_list = list(cards)
    return {
        "count": len(card_list),
        "suits": _counter_dict(card.suit for card in card_list),
        "ranks": _counter_dict(card.rank for card in card_list),
        "enhancements": _counter_dict(card.enhancement for card in card_list if card.enhancement != "None"),
        "editions": _counter_dict(card.edition for card in card_list if card.edition != "None"),
        "seals": _counter_dict(card.seal for card in card_list if card.seal != "None"),
    }


def _summarize_jokers(jokers: Iterable[Joker]) -> Dict[str, Any]:
    joker_list = list(jokers)
    return {
        "count": len(joker_list),
        "names": [joker.name for joker in joker_list],
        "editions": _counter_dict(joker.edition for joker in joker_list if joker.edition != "None"),
        "stickers": {
            "eternal": sum(1 for joker in joker_list if joker.is_eternal),
            "perishable": sum(1 for joker in joker_list if joker.is_perishable),
            "rental": sum(1 for joker in joker_list if joker.is_rental),
        },
    }


class DecisionTracer:
    def __init__(self):
        self.enabled = config.TRACE_ENABLED
        trace_dir = Path(config.TRACE_DIR)
        trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = trace_dir / config.TRACE_JSONL_FILE

    def summarize_state(self, state: BalatroState) -> Dict[str, Any]:
        preferred_hand = None
        if state.hand_levels:
            preferred_hand = max(
                state.hand_levels.items(),
                key=lambda pair: (pair[1].played, pair[1].level, pair[0]),
            )[0]

        return {
            "meta": {
                "seed": state.meta.seed,
                "phase": state.meta.phase,
                "ante": state.meta.ante,
                "round": state.meta.round,
                "stake": state.meta.stake,
                "blind_on_deck": state.meta.blind_on_deck,
            },
            "blind": {
                "name": state.blind.name,
                "target_score": state.blind.target_score,
                "current_score": state.blind.current_score,
                "remaining_target": state.blind.target_score - state.blind.current_score,
                "boss_modifier": state.blind.boss_modifier,
                "is_boss": state.blind.is_boss,
            },
            "economy": {
                "money": state.economy.money,
                "hands_left": state.economy.hands_left,
                "discards_left": state.economy.discards_left,
                "hand_size": state.economy.hand_size,
                "reroll_cost": state.economy.reroll_cost,
                "interest_cap": state.economy.interest_cap,
                "interest_amount": state.economy.interest_amount,
            },
            "preferred_hand": preferred_hand,
            "hand": _summarize_cards(state.hand),
            "deck": _summarize_cards(state.deck),
            "discard_pile": _summarize_cards(state.discard_pile),
            "jokers": _summarize_jokers(state.jokers),
            "hand_levels": {
                name: {
                    "level": info.level,
                    "played": info.played,
                    "played_this_round": info.played_this_round,
                }
                for name, info in state.hand_levels.items()
            },
        }

    def record(
        self,
        state: BalatroState,
        action: ActionResponse,
        *,
        solver: str,
        diagnostics: Optional[Dict[str, Any]] = None,
        strategy: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return

        payload: Dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "solver": solver,
            "action": action.model_dump(),
        }
        payload["state_summary"] = self.summarize_state(state)

        if strategy is not None:
            payload["strategy"] = strategy
        if diagnostics is not None:
            payload["diagnostics"] = diagnostics
        if config.TRACE_INCLUDE_STATE:
            payload["state"] = state.model_dump()

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
