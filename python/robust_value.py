from dataclasses import dataclass
from typing import Dict, Iterable, List

from belief_model import BeliefState
from risk_metrics import clamp01


@dataclass
class RobustAggregate:
    p_clear_bma: float
    p_clear_cons: float
    score_bma: float
    score_cons: float
    model_values: Dict[str, float]
    model_clear_probs: Dict[str, float]
    model_scores: Dict[str, float]


def aggregate_candidate(base_clear_probability: float, base_score: float, belief: BeliefState) -> RobustAggregate:
    if not belief.rule_models:
        base_value = base_clear_probability * 1000.0 + base_score
        return RobustAggregate(
            p_clear_bma=clamp01(base_clear_probability),
            p_clear_cons=clamp01(base_clear_probability),
            score_bma=base_score,
            score_cons=base_score,
            model_values={"nominal": base_value},
            model_clear_probs={"nominal": clamp01(base_clear_probability)},
            model_scores={"nominal": base_score},
        )

    model_values: Dict[str, float] = {}
    model_clear_probs: Dict[str, float] = {}
    model_scores: Dict[str, float] = {}
    p_clear_bma = 0.0
    score_bma = 0.0

    for model in belief.rule_models:
        clear_probability = clamp01(base_clear_probability - model.clear_penalty)
        expected_score = max(0.0, base_score * model.score_scale)
        value = clear_probability * 1000.0 + expected_score

        model_clear_probs[model.model_id] = clear_probability
        model_scores[model.model_id] = expected_score
        model_values[model.model_id] = value

        p_clear_bma += model.weight * clear_probability
        score_bma += model.weight * expected_score

    return RobustAggregate(
        p_clear_bma=clamp01(p_clear_bma),
        p_clear_cons=min(model_clear_probs.values()) if model_clear_probs else clamp01(base_clear_probability),
        score_bma=score_bma,
        score_cons=min(model_scores.values()) if model_scores else base_score,
        model_values=model_values,
        model_clear_probs=model_clear_probs,
        model_scores=model_scores,
    )


def compute_minimax_regret(aggregates: Iterable[RobustAggregate]) -> List[float]:
    aggregate_list = list(aggregates)
    if not aggregate_list:
        return []

    model_ids = sorted({model_id for aggregate in aggregate_list for model_id in aggregate.model_values})
    best_by_model = {
        model_id: max(aggregate.model_values.get(model_id, float("-inf")) for aggregate in aggregate_list)
        for model_id in model_ids
    }
    regrets: List[float] = []
    for aggregate in aggregate_list:
        regret = 0.0
        for model_id in model_ids:
            value = aggregate.model_values.get(model_id, float("-inf"))
            regret = max(regret, best_by_model[model_id] - value)
        regrets.append(max(0.0, regret))
    return regrets
