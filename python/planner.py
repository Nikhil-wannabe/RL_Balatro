from collections import Counter
from typing import Any, Dict, List, Tuple

from action_types import ActionResponse
from brain import ActionFeatures, Brain, TacticalMode
from config import config
from decision_trace import DecisionTracer
from hand_solver import HandSolver
from js_solver import JSRoundSolver
from logging_utils import get_logger
from monte_carlo import MonteCarloStats, MonteCarloSimulator
from rank_utils import get_rank_value
from scorer import Scorer
from shop_planner import ShopPlanner
from state import BalatroState, Card
from strategy_model import StrategyModel

logger = get_logger("Planner")

FACE_RANKS = {"Jack", "Queen", "King"}


def _discard_card_cost(card: Card) -> float:
    score = float(get_rank_value(card.rank))
    if card.enhancement != "None":
        score += 5.0
    if card.edition != "None":
        score += 4.0
    if card.seal != "None":
        score += 3.0
    if card.rank in {"Jack", "Queen", "King", "Ace"}:
        score += 2.0
    return score


def _combo_sort_key(cards: List[Card]) -> Tuple[str, ...]:
    return tuple(sorted(card.id for card in cards))


class Planner:
    def __init__(self):
        self.scorer = Scorer()
        self.brain = Brain()
        self.mc_sim = MonteCarloSimulator(self.scorer, num_rollouts=config.MC_ROLLOUTS, seed=config.MC_SEED)
        self.js_solver = JSRoundSolver()
        self.shop_planner = ShopPlanner()
        self.tracer = DecisionTracer()
        self.strategy_model = StrategyModel()

    def _record(self, state: BalatroState, action: ActionResponse, *, solver: str, diagnostics=None, strategy=None):
        self.tracer.record(state, action, solver=solver, diagnostics=diagnostics, strategy=strategy)

    def _hand_context(self, state: BalatroState) -> Dict[str, Any]:
        suit_counts = Counter(card.suit for card in state.hand)
        rank_counts = Counter(card.rank for card in state.hand)
        dominant_suit = max(suit_counts.items(), key=lambda pair: (pair[1], pair[0]))[0] if suit_counts else None
        neighbor_counts: Dict[str, int] = {}

        for card in state.hand:
            rank_value = get_rank_value(card.rank)
            neighbor_counts[card.id] = sum(
                1
                for other in state.hand
                if other.id != card.id and 0 < abs(get_rank_value(other.rank) - rank_value) <= 2
            )

        return {
            "suit_counts": suit_counts,
            "rank_counts": rank_counts,
            "dominant_suit": dominant_suit,
            "neighbor_counts": neighbor_counts,
        }

    def _card_keep_value(self, card: Card, strategy: Dict[str, Any], hand_context: Dict[str, Any]) -> float:
        posterior = strategy.get("posterior", {})
        suit_counts = hand_context["suit_counts"]
        rank_counts = hand_context["rank_counts"]
        dominant_suit = hand_context["dominant_suit"]
        neighbor_counts = hand_context["neighbor_counts"]

        keep_value = _discard_card_cost(card)
        keep_value += posterior.get("flush", 0.0) * suit_counts.get(card.suit, 0) * 2.5
        if dominant_suit and card.suit == dominant_suit:
            keep_value += posterior.get("flush", 0.0) * 3.0

        keep_value += posterior.get("straight", 0.0) * neighbor_counts.get(card.id, 0) * 2.0

        if rank_counts.get(card.rank, 0) >= 2:
            keep_value += posterior.get("small_hand", 0.0) * rank_counts[card.rank] * 2.6

        if card.rank in FACE_RANKS:
            keep_value += posterior.get("face_cards", 0.0) * 3.0
        if card.rank == "Ace":
            keep_value += posterior.get("small_hand", 0.0) * 1.4

        if card.enhancement == "Steel":
            keep_value += posterior.get("held_in_hand", 0.0) * 5.0
        if card.seal == "Blue":
            keep_value += posterior.get("held_in_hand", 0.0) * 4.0
        if card.enhancement == "Gold" or card.seal == "Gold":
            keep_value += posterior.get("economy", 0.0) * 2.0

        return keep_value

    def _discard_candidate_priority(
        self,
        discard_combo: List[Card],
        strategy: Dict[str, Any],
        hand_context: Dict[str, Any],
    ) -> float:
        posterior = strategy.get("posterior", {})
        keep_sum = sum(self._card_keep_value(card, strategy, hand_context) for card in discard_combo)
        discard_suits = Counter(card.suit for card in discard_combo)
        discard_rank_values = sorted(get_rank_value(card.rank) for card in discard_combo)

        flush_break_penalty = posterior.get("flush", 0.0) * max(discard_suits.values(), default=0) * 2.5
        straight_break_penalty = 0.0
        for left, right in zip(discard_rank_values, discard_rank_values[1:]):
            if 0 < right - left <= 2:
                straight_break_penalty += posterior.get("straight", 0.0) * 1.8

        size_penalty = len(discard_combo) * (
            0.7
            + posterior.get("small_hand", 0.0) * 1.5
            + posterior.get("held_in_hand", 0.0) * 1.3
            - posterior.get("flush", 0.0) * 0.5
            - posterior.get("straight", 0.0) * 0.5
        )
        return keep_sum + flush_break_penalty + straight_break_penalty + size_penalty

    def _discard_search_plan(self, state: BalatroState, strategy: Dict[str, Any], best_play_score: float) -> Dict[str, Any]:
        remaining_target = state.blind.target_score - state.blind.current_score
        pressure = remaining_target / max(1.0, best_play_score)
        posterior = strategy.get("posterior", {})
        shape_pressure = max(posterior.get("flush", 0.0), posterior.get("straight", 0.0))

        candidate_limit = 6 + state.economy.discards_left * 2 + min(4, state.economy.hands_left)
        if pressure > 2.0:
            candidate_limit += 3
        if shape_pressure >= 0.2:
            candidate_limit += 2

        initial_rollouts = max(config.MC_MIN_ROLLOUTS, min(config.MC_ROLLOUTS, 4 + state.economy.discards_left))
        refine_rollouts = max(0, config.MC_ROLLOUTS - initial_rollouts)

        return {
            "candidate_limit": min(config.MC_MAX_CANDIDATES, candidate_limit),
            "initial_rollouts": initial_rollouts,
            "refine_rollouts": refine_rollouts,
            "refine_top_k": config.MC_REFINE_TOP_K,
            "pressure": round(pressure, 3),
            "shape_pressure": round(shape_pressure, 3),
            "sampling_method": "successive_refinement_with_common_random_numbers",
        }

    def _refresh_discard_entry(
        self,
        state: BalatroState,
        entry: Dict[str, Any],
        *,
        best_play_score: float,
        target: float,
        mode: str,
    ) -> None:
        stats: MonteCarloStats = self.mc_sim.summarize_scores(
            entry["scores"],
            target=target,
            current_best_score=best_play_score,
            seed_base=entry["seed_base"],
            rollout_count=len(entry["scores"]),
        )
        expected_score = best_play_score + stats.expected_improvement
        discard_priority = entry["priority"]
        cards_used = len(entry["cards"])
        rank_sum = sum(get_rank_value(card.rank) for card in entry["cards"])

        features = ActionFeatures(
            action_type="DISCARD",
            cards=[card.id for card in entry["cards"]],
            clear_probability=stats.clear_probability,
            expected_score=expected_score,
            score_variance=stats.variance,
            score_margin_vs_blind=expected_score - target,
            hands_remaining=state.economy.hands_left,
            discards_remaining=state.economy.discards_left - 1,
            money_after_action=state.economy.money,
            cards_used=cards_used,
            discard_quality=-discard_priority,
            future_hand_strength_estimate=stats.risk_adjusted_improvement,
            overkill=max(0.0, expected_score - target) if expected_score >= target else 0.0,
        )

        entry["stats"] = stats
        entry["features"] = features
        entry["utility"] = self.brain.calculate_utility(features, mode)
        entry["rank_sum"] = rank_sum

    def _evaluate_discard_actions(
        self,
        state: BalatroState,
        *,
        best_play_score: float,
        target: float,
        mode: str,
        strategy: Dict[str, Any],
    ) -> Tuple[List[Tuple[float, int, int, ActionFeatures]], List[Dict[str, Any]], Dict[str, Any]]:
        hand_context = self._hand_context(state)
        search_plan = self._discard_search_plan(state, strategy, best_play_score)

        subsets = []
        for discard_combo in HandSolver.enumerate_plays(state.hand, min_size=1, max_size=min(5, len(state.hand))):
            priority = self._discard_candidate_priority(discard_combo, strategy, hand_context)
            subsets.append((priority, len(discard_combo), _combo_sort_key(discard_combo), list(discard_combo)))

        subsets.sort(key=lambda item: (item[0], item[1], item[2]))
        candidates = subsets[: min(search_plan["candidate_limit"], len(subsets))]

        provisional: List[Dict[str, Any]] = []
        for priority, _, _, discard_candidate in candidates:
            discard_ids = {card.id for card in discard_candidate}
            scores, seed_base = self.mc_sim.simulate_discard_scores(
                state,
                discard_ids,
                rollout_count=search_plan["initial_rollouts"],
            )
            entry: Dict[str, Any] = {
                "cards": discard_candidate,
                "discard_ids": discard_ids,
                "priority": priority,
                "scores": scores,
                "seed_base": seed_base,
                "refined": False,
            }
            self._refresh_discard_entry(
                state,
                entry,
                best_play_score=best_play_score,
                target=target,
                mode=mode,
            )
            provisional.append(entry)

        provisional.sort(
            key=lambda entry: (
                entry["utility"],
                entry["stats"].clear_probability,
                entry["stats"].risk_adjusted_improvement,
                -entry["features"].cards_used,
                -entry["rank_sum"],
            ),
            reverse=True,
        )

        if provisional and search_plan["refine_rollouts"] > 0:
            leader = provisional[0]
            refine_pool: List[Dict[str, Any]] = []
            for entry in provisional:
                if len(refine_pool) >= search_plan["refine_top_k"]:
                    break
                cp_gap = leader["stats"].clear_probability - entry["stats"].clear_probability
                mean_gap = leader["stats"].mean_score - entry["stats"].mean_score
                uncertainty_band = leader["stats"].confidence_margin + entry["stats"].confidence_margin
                if cp_gap <= 0.12 or mean_gap <= max(15.0, uncertainty_band):
                    refine_pool.append(entry)

            if not refine_pool:
                refine_pool = provisional[: min(search_plan["refine_top_k"], len(provisional))]

            for entry in refine_pool:
                extra_scores, _ = self.mc_sim.simulate_discard_scores(
                    state,
                    entry["discard_ids"],
                    rollout_count=search_plan["refine_rollouts"],
                    rollout_offset=len(entry["scores"]),
                )
                entry["scores"].extend(extra_scores)
                entry["refined"] = True
                self._refresh_discard_entry(
                    state,
                    entry,
                    best_play_score=best_play_score,
                    target=target,
                    mode=mode,
                )

            provisional.sort(
                key=lambda entry: (
                    entry["utility"],
                    entry["stats"].clear_probability,
                    entry["stats"].risk_adjusted_improvement,
                    -entry["features"].cards_used,
                    -entry["rank_sum"],
                ),
                reverse=True,
            )

        actions = [
            (
                entry["utility"],
                entry["features"].cards_used,
                entry["rank_sum"],
                entry["features"],
            )
            for entry in provisional
        ]
        diagnostics = []
        for entry in provisional[:8]:
            stats = entry["stats"]
            diagnostics.append(
                {
                    "cards": entry["features"].cards,
                    "expected_score": round(entry["features"].expected_score, 3),
                    "expected_improvement": round(stats.expected_improvement, 3),
                    "risk_adjusted_improvement": round(stats.risk_adjusted_improvement, 3),
                    "clear_probability": round(stats.clear_probability, 3),
                    "variance": round(stats.variance, 3),
                    "lower_quantile": round(stats.lower_quantile, 3),
                    "confidence_margin": round(stats.confidence_margin, 3),
                    "standard_error": round(stats.standard_error, 3),
                    "rollouts": stats.sample_count,
                    "seed_base": str(stats.seed_base),
                    "strategy_priority": round(entry["priority"], 3),
                    "refined": entry["refined"],
                    "utility": round(entry["utility"], 3),
                }
            )
        return actions, diagnostics, search_plan

    def plan_action(self, state: BalatroState) -> ActionResponse:
        phase = (state.meta.phase or "SELECTING_HAND").upper()
        logger.info("Planning for phase %s.", phase)

        if phase == "SELECTING_HAND":
            return self.plan_selecting_hand(state)
        if phase == "BLIND_SELECT":
            action = self.plan_blind_select(state)
            strategy = self.strategy_model.infer(state)
            self._record(state, action, solver="phase_router", diagnostics={"phase": phase}, strategy=strategy)
            return action
        if phase == "ROUND_EVAL":
            action = ActionResponse(action="CASH_OUT")
            strategy = self.strategy_model.infer(state)
            self._record(state, action, solver="phase_router", diagnostics={"phase": phase}, strategy=strategy)
            return action
        if phase == "SHOP":
            action = self.shop_planner.plan_action(state)
            shop_trace = self.shop_planner.last_trace if hasattr(self.shop_planner, "last_trace") else {}
            self._record(
                state,
                action,
                solver="shop_strategy_model",
                diagnostics={key: value for key, value in shop_trace.items() if key != "strategy"},
                strategy=shop_trace.get("strategy"),
            )
            return action

        logger.warning("Unsupported phase %s; returning NO_OP.", phase)
        action = ActionResponse(action="NO_OP", message=f"Unsupported phase {phase}")
        strategy = self.strategy_model.infer(state)
        self._record(
            state,
            action,
            solver="phase_router",
            diagnostics={"phase": phase, "reason": "unsupported_phase"},
            strategy=strategy,
        )
        return action

    def plan_blind_select(self, state: BalatroState) -> ActionResponse:
        blind_on_deck = (state.meta.blind_on_deck or "").lower()
        if blind_on_deck == "boss" and state.economy.money < 5 and state.meta.ante <= 2:
            return ActionResponse(action="SKIP")
        return ActionResponse(action="SELECT_BLIND")

    def plan_selecting_hand(self, state: BalatroState) -> ActionResponse:
        logger.info(
            "--- PLANNING START | Ante %s, Round %s | Target: %s ---",
            state.meta.ante,
            state.meta.round,
            state.blind.target_score,
        )
        strategy = self.strategy_model.infer(state)

        if state.economy.hands_left <= 0:
            logger.warning("No hands left, returning NO_OP.")
            action = ActionResponse(action="NO_OP", message="No hands left")
            self._record(
                state,
                action,
                solver="python_fallback",
                diagnostics={"phase": "SELECTING_HAND", "reason": "no_hands_left"},
                strategy=strategy,
            )
            return action

        js_action = self.js_solver.solve(state)
        if js_action is not None and js_action.action in {"PLAY_HAND", "DISCARD"}:
            logger.info("Using JS round solver result: %s %s", js_action.action, js_action.cards)
            diagnostics = {
                "phase": "SELECTING_HAND",
                "backend": "js_round_solver",
                "js_diagnostics": self.js_solver.last_diagnostics,
            }
            self._record(state, js_action, solver="js_round_solver", diagnostics=diagnostics, strategy=strategy)
            return js_action

        target = state.blind.target_score - state.blind.current_score

        best_play_score = -1.0
        plays_evaluated = []
        for play_combo in HandSolver.enumerate_plays(state.hand):
            played_ids = {card.id for card in play_combo}
            held = [card for card in state.hand if card.id not in played_ids]
            score = float(self.scorer.evaluate_play(play_combo, held, state.jokers))
            plays_evaluated.append((play_combo, score))
            if score > best_play_score:
                best_play_score = score

        prob_clear = self.brain.estimate_clear_probability(state, best_play_score)
        mode = self.brain.determine_mode(state, best_play_score, prob_clear)
        logger.info(
            "[Mode Decision] Tactical Mode: %s | Estimated Clear Prob: %.2f | Best Immediate Score: %.1f",
            mode,
            prob_clear,
            best_play_score,
        )

        actions: List[Tuple[float, int, int, ActionFeatures]] = []
        discard_diagnostics: List[Dict[str, Any]] = []
        discard_search_info = None

        for play_combo, score in plays_evaluated:
            rank_sum = sum(get_rank_value(card.rank) for card in play_combo)
            cards_used = len(play_combo)
            is_lethal = score >= target
            features = ActionFeatures(
                action_type="PLAY_HAND",
                cards=[card.id for card in play_combo],
                clear_probability=1.0 if is_lethal else prob_clear,
                expected_score=score,
                score_variance=0.0,
                score_margin_vs_blind=score - target,
                hands_remaining=state.economy.hands_left - 1,
                discards_remaining=state.economy.discards_left,
                money_after_action=state.economy.money,
                cards_used=cards_used,
                discard_quality=0.0,
                future_hand_strength_estimate=0.0,
                overkill=max(0.0, score - target) if is_lethal else 0.0,
            )
            utility = self.brain.calculate_utility(features, mode)
            actions.append((utility, cards_used, rank_sum, features))

        if state.economy.discards_left > 0 and mode in {
            TacticalMode.DESPERATION,
            TacticalMode.SAFE_CLEAR,
            TacticalMode.SCALING_PRESERVE,
        }:
            logger.info("Evaluating discard lines via staged Monte Carlo search...")
            discard_actions, discard_diagnostics, discard_search_info = self._evaluate_discard_actions(
                state,
                best_play_score=best_play_score,
                target=target,
                mode=mode,
                strategy=strategy,
            )
            actions.extend(discard_actions)

        if not actions:
            logger.error("No valid plays found.")
            action = ActionResponse(action="ERROR", message="No valid plays found")
            self._record(
                state,
                action,
                solver="python_fallback",
                diagnostics={"phase": "SELECTING_HAND", "reason": "no_actions"},
                strategy=strategy,
            )
            return action

        actions.sort(key=lambda item: (item[0], -item[1], -item[2]), reverse=True)

        logger.info("[Top 3 Actions]")
        for i, (utility, _, _, features) in enumerate(actions[:3]):
            logger.info(
                "  #%s: %s (cards: %s) | Util: %.2f | EV: %.1f",
                i + 1,
                features.action_type,
                len(features.cards),
                utility,
                features.expected_score,
            )

        best_action = actions[0][3]
        logger.info("--- DECISION SUMMARY ---")
        logger.info("Action: %s", best_action.action_type)
        logger.info("Cards: %s", best_action.cards)
        logger.info("Utility: %.2f", actions[0][0])
        logger.info("------------------------")

        response = ActionResponse(action=best_action.action_type, cards=best_action.cards)
        diagnostics = {
            "phase": "SELECTING_HAND",
            "backend": "python_fallback",
            "js_failure": self.js_solver.last_failure,
            "mode": mode,
            "estimated_clear_probability": round(prob_clear, 4),
            "best_immediate_score": best_play_score,
            "top_actions": [
                {
                    "action_type": features.action_type,
                    "cards": features.cards,
                    "utility": round(utility, 3),
                    "expected_score": round(features.expected_score, 3),
                    "clear_probability": round(features.clear_probability, 3),
                    "cards_used": features.cards_used,
                }
                for utility, _, _, features in actions[:8]
            ],
            "discard_search": discard_search_info,
            "discard_candidates": discard_diagnostics,
        }
        self._record(state, response, solver="python_fallback", diagnostics=diagnostics, strategy=strategy)
        return response
