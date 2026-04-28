from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any, Dict, List, Optional, Tuple

from action_types import ActionResponse
from belief_model import BeliefModel, BeliefState
from boss_logic import boss_profile_from_state, future_penalty_scale, money_after_play
from brain import ActionFeatures, Brain, RankedAction, TacticalMode
from config import config
from decision_trace import DecisionTracer
from discard_bounds import DiscardBounder
from exact_clear import ExactClearSolver
from hand_solver import HandSolver
from js_solver import JSRoundSolver
from logging_utils import get_logger
from monte_carlo import MonteCarloStats, MonteCarloSimulator
from pack_planner import PackPlanner
from rank_utils import get_rank_value
from robust_value import RobustAggregate, aggregate_candidate
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
    _candidate_executor: Optional[ThreadPoolExecutor] = None
    _js_executor: Optional[ThreadPoolExecutor] = None

    def __init__(self):
        self.scorer = Scorer()
        self.brain = Brain()
        self.mc_sim = MonteCarloSimulator(self.scorer, num_rollouts=config.MC_ROLLOUTS, seed=config.MC_SEED)
        self.js_solver = JSRoundSolver()
        self.shop_planner = ShopPlanner()
        self.pack_planner = PackPlanner()
        self.tracer = DecisionTracer()
        self.strategy_model = StrategyModel()
        self.belief_model = BeliefModel()
        self.discard_bounder = DiscardBounder(self.scorer)
        self.exact_solver = ExactClearSolver(self.scorer, exact_draw_enum_cap=config.EXACT_DRAW_ENUM_CAP)

    @classmethod
    def _get_candidate_executor(cls) -> ThreadPoolExecutor:
        if cls._candidate_executor is None:
            cls._candidate_executor = ThreadPoolExecutor(
                max_workers=max(1, config.PARALLEL_WORKERS),
                thread_name_prefix="balatro-candidate",
            )
        return cls._candidate_executor

    @classmethod
    def _get_js_executor(cls) -> ThreadPoolExecutor:
        if cls._js_executor is None:
            cls._js_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="balatro-js",
            )
        return cls._js_executor

    def _record(self, state: BalatroState, action: ActionResponse, *, solver: str, diagnostics=None, strategy=None):
        self.tracer.record(state, action, solver=solver, diagnostics=diagnostics, strategy=strategy)

    def _deadline_from_ms(self, budget_ms: int) -> float:
        return time.perf_counter() + max(0.1, budget_ms / 1000.0)

    def _time_remaining_s(self, deadline: Optional[float]) -> float:
        if deadline is None:
            return float("inf")
        return max(0.0, deadline - time.perf_counter())

    def _has_budget(self, deadline: Optional[float], reserve_ms: int = 0) -> bool:
        return self._time_remaining_s(deadline) > (reserve_ms / 1000.0)

    def _hand_context(self, state: BalatroState) -> Dict[str, Any]:
        suit_counts = Counter(card.suit for card in state.hand)
        rank_counts = Counter(card.rank for card in state.hand)
        draw_suit_counts = Counter(card.suit for card in getattr(state, "deck", []))
        draw_rank_counts = Counter(card.rank for card in getattr(state, "deck", []))
        dominant_suit = max(suit_counts.items(), key=lambda pair: (pair[1], pair[0]))[0] if suit_counts else None
        neighbor_counts: Dict[str, int] = {}
        draw_neighbor_counts: Dict[str, int] = {}

        for card in state.hand:
            rank_value = get_rank_value(card.rank)
            neighbor_counts[card.id] = sum(
                1
                for other in state.hand
                if other.id != card.id and 0 < abs(get_rank_value(other.rank) - rank_value) <= 2
            )
            draw_neighbor_counts[card.id] = sum(
                1
                for other in getattr(state, "deck", [])
                if 0 < abs(get_rank_value(other.rank) - rank_value) <= 2
            )

        return {
            "suit_counts": suit_counts,
            "rank_counts": rank_counts,
            "draw_suit_counts": draw_suit_counts,
            "draw_rank_counts": draw_rank_counts,
            "dominant_suit": dominant_suit,
            "neighbor_counts": neighbor_counts,
            "draw_neighbor_counts": draw_neighbor_counts,
        }

    def _card_keep_value(self, card: Card, strategy: Dict[str, Any], hand_context: Dict[str, Any]) -> float:
        posterior = strategy.get("posterior", {})
        suit_counts = hand_context["suit_counts"]
        rank_counts = hand_context["rank_counts"]
        draw_suit_counts = hand_context["draw_suit_counts"]
        draw_rank_counts = hand_context["draw_rank_counts"]
        dominant_suit = hand_context["dominant_suit"]
        neighbor_counts = hand_context["neighbor_counts"]
        draw_neighbor_counts = hand_context["draw_neighbor_counts"]

        keep_value = _discard_card_cost(card)
        keep_value += posterior.get("flush", 0.0) * suit_counts.get(card.suit, 0) * 2.5
        if dominant_suit and card.suit == dominant_suit:
            keep_value += posterior.get("flush", 0.0) * 3.0
        keep_value += posterior.get("flush", 0.0) * draw_suit_counts.get(card.suit, 0) * 0.35

        keep_value += posterior.get("straight", 0.0) * neighbor_counts.get(card.id, 0) * 2.0
        keep_value += posterior.get("straight", 0.0) * draw_neighbor_counts.get(card.id, 0) * 0.45

        if rank_counts.get(card.rank, 0) >= 2:
            keep_value += posterior.get("small_hand", 0.0) * rank_counts[card.rank] * 2.6
        keep_value += posterior.get("small_hand", 0.0) * draw_rank_counts.get(card.rank, 0) * 0.65

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

    def _evaluate_exact_discard_candidate(
        self,
        state: BalatroState,
        belief: BeliefState,
        discard_candidate: List[Card],
        priority: float,
        *,
        best_play_score: float,
        target: float,
        allow_parallel: bool,
    ) -> Dict[str, Any] | None:
        discard_ids = {card.id for card in discard_candidate}
        exact_result = self.exact_solver.exact_discard_stats(
            state,
            belief,
            discard_ids,
            best_play_score,
            allow_parallel=allow_parallel,
        )
        if exact_result is None:
            return None
        entry = self._make_discard_entry(
            state,
            belief,
            discard_candidate,
            exact_result.stats,
            target=target,
            priority=priority,
            exact=True,
            refined=True,
        )
        entry["exact_method"] = exact_result.method
        entry["exact_combinations_evaluated"] = exact_result.combinations_evaluated
        return entry

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

    def _discard_search_plan(
        self,
        state: BalatroState,
        strategy: Dict[str, Any],
        best_play_score: float,
        *,
        remaining_time_s: Optional[float],
    ) -> Dict[str, Any]:
        remaining_target = state.blind.target_score - state.blind.current_score
        pressure = remaining_target / max(1.0, best_play_score)
        posterior = strategy.get("posterior", {})
        shape_pressure = max(posterior.get("flush", 0.0), posterior.get("straight", 0.0))

        candidate_limit = 6 + state.economy.discards_left * 2 + min(4, state.economy.hands_left)
        if pressure > 2.0:
            candidate_limit += 3
        if shape_pressure >= 0.2:
            candidate_limit += 2

        initial_rollouts = config.MC_STAGE_A_ROLLOUTS
        refine_rollouts = config.MC_STAGE_B_ROLLOUTS
        rare_event_rollouts = config.MC_STAGE_C_ROLLOUTS

        if remaining_time_s is not None:
            baseline_budget_s = max(0.5, config.SELECTING_HAND_TIME_BUDGET_MS / 1000.0)
            time_scale = max(0.2, min(1.0, remaining_time_s / baseline_budget_s))
            candidate_limit = max(3, min(config.MC_MAX_CANDIDATES, int(round(candidate_limit * (0.45 + 0.55 * time_scale)))))
            initial_rollouts = max(4, int(round(initial_rollouts * time_scale)))
            refine_rollouts = max(0, int(round(refine_rollouts * time_scale)))
            rare_event_rollouts = max(0, int(round(rare_event_rollouts * time_scale)))
            if remaining_time_s < 0.75:
                rare_event_rollouts = min(rare_event_rollouts, 10)
            if remaining_time_s < 0.45:
                refine_rollouts = 0
                rare_event_rollouts = 0

        return {
            "candidate_limit": min(config.MC_MAX_CANDIDATES, candidate_limit),
            "initial_rollouts": initial_rollouts,
            "refine_rollouts": refine_rollouts,
            "rare_event_rollouts": rare_event_rollouts,
            "refine_top_k": config.MC_REFINE_TOP_K,
            "pressure": round(pressure, 3),
            "shape_pressure": round(shape_pressure, 3),
            "remaining_time_s": None if remaining_time_s is None else round(remaining_time_s, 3),
            "sampling_method": "branch_and_bound_plus_shared_pool_mc",
        }

    def _hand_matches_run_plan(self, hand_name: str, run_plan: Optional[Dict[str, Any]]) -> bool:
        if not hand_name or not run_plan:
            return False
        return hand_name in set(run_plan.get("accepted_hands", []))

    def _make_play_entry(
        self,
        state: BalatroState,
        belief: BeliefState,
        play_combo: List[Card],
        score: float,
        target: float,
        hand_name: str,
        money_after_action: Optional[float] = None,
    ) -> Dict[str, Any]:
        cards_used = len(play_combo)
        is_lethal = score >= target
        remaining_target = max(0.0, target - score)
        hands_after_action = max(0, state.economy.hands_left - 1)
        heuristic_clear = (
            1.0
            if is_lethal
            else self.brain.estimate_clear_probability(
                state,
                score,
                target_override=remaining_target,
                hands_override=hands_after_action,
            )
        )
        conservative_clear = 1.0 if is_lethal else max(0.0, heuristic_clear - 0.10)
        if money_after_action is None:
            money_after_action = float(state.economy.money)
        future_strength = max(0.0, score - (target / max(1, state.economy.hands_left)))
        future_strength -= future_penalty_scale(state, hand_name, hands_after_action=hands_after_action) * (
            target / max(1.0, float(state.economy.hands_left))
        )
        features = ActionFeatures(
            action_type="PLAY_HAND",
            cards=[card.id for card in play_combo],
            clear_probability=heuristic_clear,
            clear_probability_lcb=conservative_clear,
            expected_score=score,
            score_variance=0.0,
            score_margin_vs_blind=score - target,
            hands_remaining=state.economy.hands_left - 1,
            discards_remaining=state.economy.discards_left,
            money_after_action=money_after_action,
            cards_used=cards_used,
            discard_quality=0.0,
            future_hand_strength_estimate=future_strength,
            overkill=max(0.0, score - target) if is_lethal else 0.0,
            cvar_loss=max(0.0, target - score),
            confidence_margin=0.0,
            ess=0.0,
            decision_method="exact_play_score",
            hand_name=hand_name,
        )
        if is_lethal:
            model_clear_probs = {
                (model.model_id if belief.rule_models else "certain_clear"): 1.0
                for model in (belief.rule_models or [])
            }
            model_scores = {
                (model.model_id if belief.rule_models else "certain_clear"): score
                for model in (belief.rule_models or [])
            }
            if not model_clear_probs:
                model_clear_probs = {"certain_clear": 1.0}
                model_scores = {"certain_clear": score}
            aggregate = RobustAggregate(
                p_clear_bma=1.0,
                p_clear_cons=1.0,
                score_bma=score,
                score_cons=score,
                model_values={model_id: 1000.0 + score for model_id in model_clear_probs},
                model_clear_probs=model_clear_probs,
                model_scores=model_scores,
            )
        else:
            aggregate = aggregate_candidate(heuristic_clear, score, belief)

        return {
            "features": features,
            "aggregate": aggregate,
            "stats": None,
            "priority": 0.0,
            "rank_sum": sum(get_rank_value(card.rank) for card in play_combo),
            "exact": True,
            "refined": False,
        }

    def _score_play_combo(
        self,
        state: BalatroState,
        belief: BeliefState,
        play_combo: List[Card],
        target: float,
    ) -> Tuple[Dict[str, Any], float]:
        played_ids = {card.id for card in play_combo}
        held = [card for card in state.hand if card.id not in played_ids]
        hand_name, _ = self.scorer.classify_hand(play_combo, state.jokers)
        score = float(self.scorer.evaluate_play(play_combo, held, state.jokers, state))
        money_delta = self.scorer.estimate_money_delta(play_combo, held, state.jokers, state)
        money_after_action = money_after_play(
            state,
            hand_name=hand_name,
            cards_used=len(play_combo),
            money_delta=money_delta,
        )
        return self._make_play_entry(
            state,
            belief,
            play_combo,
            score,
            target,
            hand_name,
            money_after_action=money_after_action,
        ), score

    def _evaluate_play_entries(
        self,
        state: BalatroState,
        belief: BeliefState,
        target: float,
    ) -> Tuple[List[Dict[str, Any]], float]:
        play_combos = list(HandSolver.enumerate_plays(state.hand))
        if not play_combos:
            return [], -1.0

        if (
            config.PARALLEL_CANDIDATE_EVAL
            and config.PARALLEL_WORKERS > 1
            and len(play_combos) >= config.PARALLEL_PLAY_MIN_TASKS
        ):
            executor = self._get_candidate_executor()
            futures = [
                executor.submit(self._score_play_combo, state, belief, play_combo, target)
                for play_combo in play_combos
            ]
            results = [future.result() for future in futures]
        else:
            results = [self._score_play_combo(state, belief, play_combo, target) for play_combo in play_combos]

        entries = [entry for entry, _ in results]
        best_play_score = max(score for _, score in results)
        return entries, best_play_score

    def _evaluate_mc_discard_candidate(
        self,
        state: BalatroState,
        belief: BeliefState,
        discard_candidate: List[Card],
        priority: float,
        pool,
        *,
        best_play_score: float,
        target: float,
    ) -> Dict[str, Any]:
        discard_ids = {card.id for card in discard_candidate}
        stats = self.mc_sim.evaluate_discard_with_pool(
            state,
            discard_ids,
            best_play_score,
            pool,
            use_control_variate=True,
        )
        entry = self._make_discard_entry(
            state,
            belief,
            discard_candidate,
            stats,
            target=target,
            priority=priority,
            exact=False,
            refined=False,
        )
        entry["pool_size"] = len(pool)
        return entry

    def _make_discard_entry(
        self,
        state: BalatroState,
        belief: BeliefState,
        discard_candidate: List[Card],
        stats: MonteCarloStats,
        *,
        target: float,
        priority: float,
        exact: bool,
        refined: bool,
    ) -> Dict[str, Any]:
        expected_score = stats.mean_score
        heuristic_clear = self.brain.estimate_clear_probability(state, expected_score)
        conservative_clear = max(stats.clear_probability_lcb, max(0.0, heuristic_clear - 0.15))
        features = ActionFeatures(
            action_type="DISCARD",
            cards=[card.id for card in discard_candidate],
            clear_probability=max(stats.clear_probability, heuristic_clear),
            clear_probability_lcb=min(1.0, conservative_clear if not exact else max(stats.clear_probability, conservative_clear)),
            expected_score=expected_score,
            score_variance=stats.variance,
            score_margin_vs_blind=expected_score - target,
            hands_remaining=state.economy.hands_left,
            discards_remaining=state.economy.discards_left - 1,
            money_after_action=state.economy.money,
            cards_used=len(discard_candidate),
            discard_quality=-priority,
            future_hand_strength_estimate=stats.risk_adjusted_improvement,
            overkill=max(0.0, expected_score - target) if expected_score >= target else 0.0,
            cvar_loss=stats.cvar_loss,
            confidence_margin=stats.confidence_margin,
            ess=stats.ess,
            decision_method=stats.proposal,
            hand_name="",
        )

        return {
            "features": features,
            "aggregate": aggregate_candidate(features.clear_probability, features.expected_score, belief),
            "stats": stats,
            "priority": priority,
            "rank_sum": sum(get_rank_value(card.rank) for card in discard_candidate),
            "exact": exact,
            "refined": refined,
        }

    def _apply_round_viability_biases(
        self,
        state: BalatroState,
        entries: List[Dict[str, Any]],
        *,
        best_play_score: float,
        target: float,
        run_plan: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not entries:
            return

        early_game = (state.meta.ante or 1) <= config.EARLY_GAME_ANTE_CUTOFF
        required_per_hand_now = target / max(1, state.economy.hands_left)
        stage = (run_plan or {}).get("stage")
        target_hand = (run_plan or {}).get("target_hand", "")
        backup_hands = set((run_plan or {}).get("backup_hands", []))
        small_hand_plan = target_hand in {"High Card", "Pair", "Two Pair"}
        flush_plan = target_hand in {"Flush", "Straight Flush", "Flush House", "Flush Five"}
        straight_plan = target_hand in {"Straight", "Straight Flush"}
        duplicate_plan = target_hand in {"Three of a Kind", "Full House", "Four of a Kind", "Five of a Kind"}

        for entry in entries:
            features: ActionFeatures = entry["features"]
            if features.action_type == "PLAY_HAND":
                exact_target_match = bool(target_hand) and features.hand_name == target_hand
                backup_match = features.hand_name in backup_hands
                if features.score_margin_vs_blind >= 0:
                    if exact_target_match:
                        features.future_hand_strength_estimate += required_per_hand_now * 0.12
                    elif backup_match:
                        features.future_hand_strength_estimate += required_per_hand_now * 0.06
                    elif self._hand_matches_run_plan(features.hand_name, run_plan):
                        features.future_hand_strength_estimate += required_per_hand_now * 0.10
                    continue

                remaining_target = max(0.0, target - features.expected_score)
                hands_after_action = max(0, features.hands_remaining)
                if hands_after_action <= 0:
                    continue

                required_after_action = remaining_target / max(1, hands_after_action)
                tempo_gap = required_after_action - max(features.expected_score, best_play_score * 0.85)
                if tempo_gap > 0.0:
                    penalty = min(0.55, tempo_gap / max(required_per_hand_now * 3.0, 1.0))
                    features.clear_probability = max(0.0, features.clear_probability - penalty)
                    features.clear_probability_lcb = max(0.0, features.clear_probability_lcb - penalty)
                    features.future_hand_strength_estimate -= tempo_gap * 0.20

                if (
                    early_game
                    and state.economy.discards_left > 0
                    and features.cards_used <= 2
                    and features.expected_score < required_per_hand_now * 0.70
                ):
                    features.clear_probability *= 0.85
                    features.clear_probability_lcb *= 0.75
                    features.future_hand_strength_estimate -= required_per_hand_now * 0.25

                if (
                    run_plan
                    and small_hand_plan
                    and stage in {"building", "conversion"}
                    and state.economy.discards_left > 0
                    and features.cards_used >= 4
                    and not self._hand_matches_run_plan(features.hand_name, run_plan)
                ):
                    features.clear_probability *= 0.90
                    features.clear_probability_lcb *= 0.86
                    features.future_hand_strength_estimate -= required_per_hand_now * 0.18

                if (
                    run_plan
                    and (flush_plan or straight_plan)
                    and stage in {"stabilization", "building"}
                    and features.cards_used <= 2
                    and not self._hand_matches_run_plan(features.hand_name, run_plan)
                    and features.expected_score < required_per_hand_now * 0.95
                ):
                    features.clear_probability *= 0.92
                    features.clear_probability_lcb *= 0.88
                    features.future_hand_strength_estimate -= required_per_hand_now * 0.12

                if duplicate_plan and state.economy.discards_left > 0 and not self._hand_matches_run_plan(features.hand_name, run_plan):
                    if features.cards_used <= 2 and features.expected_score < required_per_hand_now * 0.95:
                        features.clear_probability *= 0.90
                        features.clear_probability_lcb *= 0.84
                        features.future_hand_strength_estimate -= required_per_hand_now * 0.16

                if exact_target_match:
                    features.future_hand_strength_estimate += required_per_hand_now * 0.12
                elif backup_match:
                    features.future_hand_strength_estimate += required_per_hand_now * 0.05
                elif self._hand_matches_run_plan(features.hand_name, run_plan):
                    features.future_hand_strength_estimate += required_per_hand_now * 0.08
            else:
                tempo_surplus = features.expected_score - required_per_hand_now
                if tempo_surplus > 0.0:
                    bonus = min(0.20, tempo_surplus / max(target * 1.25, 1.0))
                    features.clear_probability = min(1.0, features.clear_probability + bonus)
                    features.clear_probability_lcb = min(1.0, features.clear_probability_lcb + (bonus * 0.8))
                    features.future_hand_strength_estimate += tempo_surplus * 0.25

                if early_game and best_play_score < required_per_hand_now:
                    features.discard_quality += max(0.0, features.expected_score - best_play_score) * 0.35
                if run_plan and small_hand_plan and stage in {"building", "conversion"} and best_play_score < required_per_hand_now * 1.05:
                    features.discard_quality += max(0.0, features.expected_score - best_play_score) * 0.22
                if run_plan and (flush_plan or straight_plan) and state.economy.discards_left > 0:
                    features.discard_quality += 0.08 * required_per_hand_now
                if run_plan and duplicate_plan and state.economy.discards_left > 0:
                    features.discard_quality += max(0.0, features.expected_score - best_play_score) * 0.18

    def _finalize_entries(
        self,
        state: BalatroState,
        entries: List[Dict[str, Any]],
        best_immediate_score: float,
    ) -> Tuple[List[RankedAction], str]:
        if not entries:
            return [], TacticalMode.DESPERATION

        target_scale = max(1.0, float(state.blind.target_score - state.blind.current_score))
        boss_pressure = boss_profile_from_state(state).immediate_clear_pressure
        model_ids = sorted(
            {
                model_id
                for entry in entries
                for model_id in entry["aggregate"].model_clear_probs.keys()
            }
        )
        if not model_ids:
            model_ids = ["nominal"]

        def surrogate_value(entry: Dict[str, Any], model_id: str) -> float:
            features: ActionFeatures = entry["features"]
            aggregate: RobustAggregate = entry["aggregate"]
            clear_probability = aggregate.model_clear_probs.get(model_id, features.clear_probability)
            score = aggregate.model_scores.get(model_id, features.expected_score)
            capped_score = min(score, target_scale) / target_scale
            resource = (features.hands_remaining + 0.5 * features.discards_remaining) / 10.0
            immediate_bonus = 0.15 if features.action_type == "PLAY_HAND" and features.score_margin_vs_blind >= 0 else 0.0
            overkill_penalty = min(1.0, max(0.0, features.overkill / target_scale)) * 0.05
            return (
                (clear_probability * (1000.0 + boss_pressure * 160.0))
                + capped_score
                + resource
                + immediate_bonus
                - overkill_penalty
            )

        best_by_model = {
            model_id: max(surrogate_value(entry, model_id) for entry in entries)
            for model_id in model_ids
        }
        regrets = [
            max(best_by_model[model_id] - surrogate_value(entry, model_id) for model_id in model_ids)
            for entry in entries
        ]

        best_bma_clear = 0.0
        best_cons_clear = 0.0
        for entry, regret in zip(entries, regrets):
            features: ActionFeatures = entry["features"]
            aggregate: RobustAggregate = entry["aggregate"]
            features.minimax_regret = regret
            if features.clear_probability_lcb > 0.0:
                features.clear_probability_lcb = min(features.clear_probability_lcb, aggregate.p_clear_cons)
            else:
                features.clear_probability_lcb = aggregate.p_clear_cons
            if features.action_type == "DISCARD":
                features.clear_probability = aggregate.p_clear_bma
            best_bma_clear = max(best_bma_clear, features.clear_probability)
            best_cons_clear = max(best_cons_clear, features.clear_probability_lcb)

        mode = self.brain.determine_mode(
            state,
            best_immediate_score,
            best_bma_clear,
            conservative_clear_prob=best_cons_clear,
        )
        ranked_actions = [self.brain.rank_action(state, entry["features"], mode) for entry in entries]
        ranked_actions = self.brain.sort_ranked_actions(ranked_actions)
        return ranked_actions, mode

    def _matching_ranked_action(
        self,
        ranked_actions: List[RankedAction],
        action: ActionResponse,
    ) -> Optional[RankedAction]:
        if action.action not in {"PLAY_HAND", "DISCARD"} or not action.cards:
            return None
        signature = tuple(sorted(action.cards))
        return next(
            (
                ranked
                for ranked in ranked_actions
                if ranked.features.action_type == action.action
                and tuple(sorted(ranked.features.cards)) == signature
            ),
            None,
        )

    def _prefer_js_action(
        self,
        state: BalatroState,
        ranked_actions: List[RankedAction],
        js_action: Optional[ActionResponse],
    ) -> Optional[RankedAction]:
        if js_action is None:
            return None

        matching = self._matching_ranked_action(ranked_actions, js_action)
        if matching is None:
            return None

        diagnostics = self.js_solver.last_diagnostics or {}
        reason = diagnostics.get("reason")
        chosen = diagnostics.get("chosen", {})
        js_clear = float(chosen.get("clear_prob", 0.0) or 0.0)
        leader = ranked_actions[0]
        early_game = (state.meta.ante or 1) <= max(config.EARLY_GAME_ANTE_CUTOFF + 1, 3)

        if reason == "lethal_play_found":
            return matching
        if matching.features.action_type == "PLAY_HAND" and matching.features.score_margin_vs_blind >= 0:
            return matching
        if early_game and reason == "risk_adjusted_rollout_search":
            return matching
        if js_clear >= max(0.0, leader.features.clear_probability_lcb - 0.03):
            return matching
        return None

    def _evaluate_discard_actions(
        self,
        state: BalatroState,
        belief: BeliefState,
        *,
        best_play_score: float,
        target: float,
        strategy: Dict[str, Any],
        deadline: Optional[float],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        hand_context = self._hand_context(state)
        search_plan = self._discard_search_plan(
            state,
            strategy,
            best_play_score,
            remaining_time_s=self._time_remaining_s(deadline),
        )

        bnb_candidates, bound_diag = self.discard_bounder.branch_and_bound_candidates(
            state,
            belief,
            max_discard_size=min(5, len(state.hand)),
            target_remaining=target,
            candidate_limit=search_plan["candidate_limit"],
        )

        prioritized = []
        for discard_candidate in bnb_candidates:
            priority = self._discard_candidate_priority(discard_candidate, strategy, hand_context)
            prioritized.append((priority, len(discard_candidate), _combo_sort_key(discard_candidate), discard_candidate))
        prioritized.sort(key=lambda item: (item[0], item[1], item[2]))

        entries: List[Dict[str, Any]] = []
        pending_by_size: Dict[int, List[Tuple[float, List[Card]]]] = defaultdict(list)
        exact_solved = 0
        exact_pending: List[Tuple[float, List[Card]]] = []
        exact_candidate_limit = min(
            config.EXACT_MAX_CANDIDATES,
            max(1, int(max(0.0, self._time_remaining_s(deadline)) / 0.9)),
        )

        for priority, _, _, discard_candidate in prioritized:
            if not self._has_budget(deadline, reserve_ms=75):
                search_plan["stopped_early_reason"] = "time_budget_exhausted"
                break
            exact_allowed = len(discard_candidate) <= 2 or (
                len(discard_candidate) == 3
                and len(prioritized) <= 4
                and self._has_budget(deadline, reserve_ms=400)
            )
            if exact_allowed:
                if len(exact_pending) < exact_candidate_limit:
                    exact_pending.append((priority, discard_candidate))
                else:
                    pending_by_size[len(discard_candidate)].append((priority, discard_candidate))
            else:
                pending_by_size[len(discard_candidate)].append((priority, discard_candidate))

        exact_results: List[Dict[str, Any] | None] = []
        if exact_pending:
            if (
                config.PARALLEL_CANDIDATE_EVAL
                and config.PARALLEL_WORKERS > 1
                and len(exact_pending) >= config.PARALLEL_DISCARD_MIN_TASKS
            ):
                executor = self._get_candidate_executor()
                futures = [
                    executor.submit(
                        self._evaluate_exact_discard_candidate,
                        state,
                        belief,
                        discard_candidate,
                        priority,
                        best_play_score=best_play_score,
                        target=target,
                        allow_parallel=False,
                    )
                    for priority, discard_candidate in exact_pending
                ]
                exact_results = [future.result() for future in futures]
            else:
                exact_results = [
                    self._evaluate_exact_discard_candidate(
                        state,
                        belief,
                        discard_candidate,
                        priority,
                        best_play_score=best_play_score,
                        target=target,
                        allow_parallel=True,
                    )
                    for priority, discard_candidate in exact_pending
                ]

        for (priority, discard_candidate), exact_entry in zip(exact_pending, exact_results):
            if exact_entry is not None:
                exact_solved += 1
                entries.append(exact_entry)
            else:
                pending_by_size[len(discard_candidate)].append((priority, discard_candidate))

        mc_entries: List[Dict[str, Any]] = []
        for draw_count, candidates in sorted(pending_by_size.items()):
            if not self._has_budget(deadline, reserve_ms=60):
                search_plan.setdefault("stopped_early_reason", "time_budget_exhausted")
                break

            nominal_pool = self.mc_sim.build_shared_pool(
                state,
                draw_count,
                rollout_count=search_plan["initial_rollouts"],
                proposal="nominal",
            )

            group_entries: List[Dict[str, Any]] = []
            if (
                config.PARALLEL_CANDIDATE_EVAL
                and config.PARALLEL_WORKERS > 1
                and len(candidates) >= config.PARALLEL_DISCARD_MIN_TASKS
            ):
                executor = self._get_candidate_executor()
                futures = [
                    executor.submit(
                        self._evaluate_mc_discard_candidate,
                        state,
                        belief,
                        discard_candidate,
                        priority,
                        nominal_pool,
                        best_play_score=best_play_score,
                        target=target,
                    )
                    for priority, discard_candidate in candidates
                ]
                group_entries = [future.result() for future in futures]
            else:
                for priority, discard_candidate in candidates:
                    group_entries.append(
                        self._evaluate_mc_discard_candidate(
                            state,
                            belief,
                            discard_candidate,
                            priority,
                            nominal_pool,
                            best_play_score=best_play_score,
                            target=target,
                        )
                    )

            group_entries.sort(
                key=lambda entry: (
                    entry["features"].clear_probability_lcb,
                    entry["features"].clear_probability,
                    entry["stats"].risk_adjusted_improvement if entry["stats"] else 0.0,
                    -entry["features"].cards_used,
                    -entry["rank_sum"],
                ),
                reverse=True,
            )

            refine_pool = group_entries[: min(search_plan["refine_top_k"], len(group_entries))]
            for entry in refine_pool:
                if not self._has_budget(deadline, reserve_ms=40):
                    search_plan["refine_stopped_early_reason"] = "time_budget_exhausted"
                    break

                discard_ids = set(entry["features"].cards)
                combined_pool = list(nominal_pool)
                if search_plan["refine_rollouts"] > 0:
                    combined_pool.extend(
                        self.mc_sim.build_shared_pool(
                            state,
                            draw_count,
                            rollout_count=search_plan["refine_rollouts"],
                            rollout_offset=len(combined_pool),
                            proposal="nominal",
                        )
                    )
                if (
                    search_plan["rare_event_rollouts"] > 0
                    and entry["features"].clear_probability_lcb < config.MC_RARE_EVENT_THRESHOLD
                ):
                    combined_pool.extend(
                        self.mc_sim.build_shared_pool(
                            state,
                            draw_count,
                            rollout_count=search_plan["rare_event_rollouts"],
                            rollout_offset=len(combined_pool),
                            proposal="tilted",
                        )
                    )

                stats = self.mc_sim.evaluate_discard_with_pool(
                    state,
                    discard_ids,
                    best_play_score,
                    combined_pool,
                    use_control_variate=True,
                )
                refreshed = self._make_discard_entry(
                    state,
                    belief,
                    [card for card in state.hand if card.id in discard_ids],
                    stats,
                    target=target,
                    priority=entry["priority"],
                    exact=False,
                    refined=True,
                )
                entry.update(refreshed)
                entry["pool_size"] = len(combined_pool)

            mc_entries.extend(group_entries)

        entries.extend(mc_entries)

        diagnostics = []
        for entry in sorted(
            entries,
            key=lambda item: (
                item["features"].clear_probability_lcb,
                item["features"].clear_probability,
                item["features"].expected_score,
                -item["features"].cards_used,
            ),
            reverse=True,
        )[:8]:
            stats = entry["stats"]
            diagnostics.append(
                {
                    "cards": entry["features"].cards,
                    "expected_score": round(entry["features"].expected_score, 3),
                    "clear_probability": round(entry["features"].clear_probability, 3),
                    "clear_probability_lcb": round(entry["features"].clear_probability_lcb, 3),
                    "cvar_loss": round(entry["features"].cvar_loss, 3),
                    "confidence_margin": round(entry["features"].confidence_margin, 3),
                    "ess": round(entry["features"].ess, 3),
                    "decision_method": entry["features"].decision_method,
                    "exact": entry["exact"],
                    "refined": entry["refined"],
                    "strategy_priority": round(entry["priority"], 3),
                    "stats": stats.as_dict() if stats is not None else None,
                }
            )

        search_plan["generated_candidates"] = len(prioritized)
        search_plan["evaluated_candidates"] = len(entries)
        search_plan["exact_solved"] = exact_solved
        search_plan["exact_candidate_limit"] = exact_candidate_limit
        search_plan["bound_diagnostics"] = {
            "generated_nodes": bound_diag.generated_nodes,
            "memo_hits": bound_diag.memo_hits,
            "sound_prunes": bound_diag.sound_prunes,
            "heuristic_prunes": bound_diag.heuristic_prunes,
        }
        return entries, diagnostics, search_plan

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
        if phase == "PACK_CHOICE":
            action = self.pack_planner.plan_action(state)
            pack_trace = self.pack_planner.last_trace if hasattr(self.pack_planner, "last_trace") else {}
            self._record(
                state,
                action,
                solver="pack_strategy_model",
                diagnostics={key: value for key, value in pack_trace.items() if key != "strategy"},
                strategy=pack_trace.get("strategy"),
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
        deadline = self._deadline_from_ms(config.SELECTING_HAND_TIME_BUDGET_MS)
        logger.info(
            "--- PLANNING START | Ante %s, Round %s | Target: %s ---",
            state.meta.ante,
            state.meta.round,
            state.blind.target_score,
        )
        strategy = self.strategy_model.infer(state)
        belief = self.belief_model.from_state(state)

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

        js_action = None
        js_future = None
        should_try_js = (
            config.JS_ROUND_SOLVER
            and (state.meta.ante or 1) >= config.JS_ROUND_SOLVER_MIN_ANTE
            and self._has_budget(deadline, reserve_ms=config.JS_ROUND_SOLVER_MIN_TIMEOUT_MS + config.PLANNER_HEADROOM_MS)
        )
        js_timeout_ms = min(
            config.JS_ROUND_SOLVER_TIMEOUT_MS,
            max(0, int(self._time_remaining_s(deadline) * 1000) - config.PLANNER_HEADROOM_MS),
        )
        if not config.JS_ROUND_SOLVER:
            self.js_solver.last_failure = "disabled_by_config"
        elif not should_try_js:
            self.js_solver.last_failure = "skipped_early_or_low_budget"
        elif js_timeout_ms >= config.JS_ROUND_SOLVER_MIN_TIMEOUT_MS and config.PARALLEL_JS_AND_PYTHON:
            js_future = self._get_js_executor().submit(self.js_solver.solve, state, js_timeout_ms)
        elif js_timeout_ms >= config.JS_ROUND_SOLVER_MIN_TIMEOUT_MS:
            js_action = self.js_solver.solve(state, timeout_ms=js_timeout_ms)
        else:
            self.js_solver.last_failure = "skipped_insufficient_budget"

        target = state.blind.target_score - state.blind.current_score
        entries, best_play_score = self._evaluate_play_entries(state, belief, target)

        discard_diagnostics: List[Dict[str, Any]] = []
        discard_search_info: Dict[str, Any] | None = None
        if state.economy.discards_left > 0 and self._has_budget(deadline, reserve_ms=100):
            logger.info("Evaluating discard lines via exact+deterministic Monte Carlo search...")
            discard_entries, discard_diagnostics, discard_search_info = self._evaluate_discard_actions(
                state,
                belief,
                best_play_score=best_play_score,
                target=target,
                strategy=strategy,
                deadline=deadline,
            )
            entries.extend(discard_entries)
        elif state.economy.discards_left > 0:
            discard_search_info = {
                "sampling_method": "branch_and_bound_plus_shared_pool_mc",
                "skipped": "time_budget_exhausted",
                "remaining_time_s": round(self._time_remaining_s(deadline), 3),
            }

        if not entries:
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

        self._apply_round_viability_biases(
            state,
            entries,
            best_play_score=best_play_score,
            target=target,
            run_plan=strategy.get("run_plan"),
        )
        ranked_actions, mode = self._finalize_entries(state, entries, best_play_score)
        if not ranked_actions:
            action = ActionResponse(action="ERROR", message="No ranked actions")
            self._record(
                state,
                action,
                solver="python_fallback",
                diagnostics={"phase": "SELECTING_HAND", "reason": "ranking_failed"},
                strategy=strategy,
            )
            return action

        logger.info(
            "[Mode Decision] Tactical Mode: %s | Best Immediate Score: %.1f | Conservative Clear: %.2f",
            mode,
            best_play_score,
            ranked_actions[0].features.clear_probability_lcb,
        )

        logger.info("[Top 3 Actions]")
        for index, ranked in enumerate(ranked_actions[:3], start=1):
            logger.info(
                "  #%s: %s (cards: %s) | Rank: %s | EV: %.1f | Pclear_LCB: %.3f",
                index,
                ranked.features.action_type,
                len(ranked.features.cards),
                ranked.rank_tuple[:5],
                ranked.features.expected_score,
                ranked.features.clear_probability_lcb,
            )

        best_ranked = ranked_actions[0]
        if js_future is not None:
            wait_time_s = self._time_remaining_s(deadline)
            if wait_time_s > 0.0:
                try:
                    js_action = js_future.result(timeout=wait_time_s)
                except Exception:
                    if self.js_solver.last_failure is None:
                        self.js_solver.last_failure = "parallel_python_preferred"
        preferred_js = self._prefer_js_action(state, ranked_actions, js_action)
        if preferred_js is not None:
            best_ranked = preferred_js

        best_action = best_ranked.features
        logger.info("--- DECISION SUMMARY ---")
        logger.info("Action: %s", best_action.action_type)
        logger.info("Cards: %s", best_action.cards)
        logger.info("Rank Tuple: %s", best_ranked.rank_tuple)
        logger.info("------------------------")

        response = ActionResponse(action=best_action.action_type, cards=best_action.cards)
        diagnostics = {
            "phase": "SELECTING_HAND",
            "backend": "python_brain_layer",
            "js_failure": self.js_solver.last_failure,
            "js_hint": js_action.model_dump() if js_action is not None else None,
            "js_selected": preferred_js is not None,
            "time_budget_ms": config.SELECTING_HAND_TIME_BUDGET_MS,
            "time_remaining_s": round(self._time_remaining_s(deadline), 3),
            "js_timeout_ms": js_timeout_ms,
            "parallel_js_and_python": js_future is not None,
            "parallel_workers": config.PARALLEL_WORKERS,
            "mode": mode,
            "run_plan": strategy.get("run_plan"),
            "belief": {
                "known_deck": belief.known_deck,
                "posterior_entropy": round(belief.posterior_entropy, 6),
                "unresolved_jokers": belief.unresolved_jokers,
                "rule_models": [
                    {
                        "model_id": model.model_id,
                        "weight": model.weight,
                        "clear_penalty": model.clear_penalty,
                        "score_scale": model.score_scale,
                    }
                    for model in belief.rule_models
                ],
            },
            "best_immediate_score": best_play_score,
            "top_actions": [
                {
                    "action_type": ranked.features.action_type,
                    "cards": ranked.features.cards,
                    "expected_score": round(ranked.features.expected_score, 3),
                    "clear_probability": round(ranked.features.clear_probability, 3),
                    "clear_probability_lcb": round(ranked.features.clear_probability_lcb, 3),
                    "cvar_loss": round(ranked.features.cvar_loss, 3),
                    "minimax_regret": round(ranked.features.minimax_regret, 3),
                    "decision_method": ranked.features.decision_method,
                    "rank_tuple": ranked.rank_tuple,
                    "utility": round(ranked.utility, 3),
                }
                for ranked in ranked_actions[:8]
            ],
            "discard_search": discard_search_info,
            "discard_candidates": discard_diagnostics,
        }
        self._record(state, response, solver="python_brain_layer", diagnostics=diagnostics, strategy=strategy)
        return response
