import math
from typing import Iterable, List, Sequence, Tuple


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def effective_sample_size(weights: Sequence[float]) -> float:
    if not weights:
        return 0.0
    total = sum(weights)
    denom = sum(weight * weight for weight in weights)
    if total <= 0.0 or denom <= 0.0:
        return 0.0
    return (total * total) / denom


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return 0.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def weighted_variance(values: Sequence[float], weights: Sequence[float], mean: float = None) -> float:
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return 0.0
    avg = weighted_mean(values, weights) if mean is None else mean
    return max(
        0.0,
        sum(weight * ((value - avg) ** 2) for value, weight in zip(values, weights)) / total_weight,
    )


def weighted_quantile(values: Sequence[float], weights: Sequence[float], alpha: float) -> float:
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda pair: pair[0])
    total_weight = sum(weight for _, weight in pairs)
    if total_weight <= 0.0:
        return min(values)

    target = clamp01(alpha) * total_weight
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= target:
            return value
    return pairs[-1][0]


def lower_quantile(values: Sequence[float], alpha: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(math.floor(clamp01(alpha) * len(sorted_values)))))
    return sorted_values[index]


def cvar_loss(values: Sequence[float], target: float, alpha: float) -> float:
    if not values:
        return max(0.0, float(target))
    losses = sorted(max(0.0, float(target) - float(value)) for value in values)
    tail_count = max(1, int(math.ceil(clamp01(alpha) * len(losses))))
    return sum(losses[-tail_count:]) / tail_count


def weighted_cvar_loss(values: Sequence[float], weights: Sequence[float], target: float, alpha: float) -> float:
    if not values:
        return max(0.0, float(target))
    losses = sorted(
        ((max(0.0, float(target) - float(value))), float(weight))
        for value, weight in zip(values, weights)
        if weight > 0.0
    )
    if not losses:
        return max(0.0, float(target))

    tail_mass = max(1e-12, clamp01(alpha) * sum(weight for _, weight in losses))
    remaining = tail_mass
    weighted_total = 0.0

    for loss, weight in reversed(losses):
        take = min(weight, remaining)
        weighted_total += loss * take
        remaining -= take
        if remaining <= 1e-12:
            break

    if tail_mass <= 0.0:
        return 0.0
    return weighted_total / tail_mass


def lower_confidence_bound(probability: float, sample_size: float, z: float = 1.96) -> float:
    n = max(0.0, float(sample_size))
    if n <= 0.0:
        return 0.0

    p = clamp01(probability)
    denominator = 1.0 + (z * z) / n
    center = p + (z * z) / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) / n) + ((z * z) / (4.0 * n * n)))
    return clamp01((center - margin) / denominator)


def normalize_ratio(value: float, scale: float, *, clip: bool = True) -> float:
    if scale <= 0.0:
        return 0.0
    ratio = float(value) / float(scale)
    if not clip:
        return ratio
    return max(-1.0, min(1.0, ratio))


def stable_desc_tuple(values: Iterable[float]) -> Tuple[float, ...]:
    return tuple(round(float(value), 8) for value in values)
