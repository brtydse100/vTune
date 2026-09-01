"""Small, dependency-free summaries for repeated benchmark measurements."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import fmean, median
from collections.abc import Mapping
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MeasurementSummary:
    count: int
    mean: float
    median: float
    variance: float | None
    confidence_low: float | None
    confidence_high: float | None
    minimum_repeats_met: bool


def summarize(values: Iterable[float], minimum_repeats: int = 2) -> MeasurementSummary:
    samples = tuple(float(value) for value in values)
    if minimum_repeats < 1 or not samples:
        raise ValueError("measurements and minimum_repeats must be positive")
    average = fmean(samples)
    if len(samples) < 2:
        return MeasurementSummary(len(samples), average, median(samples), None, None, None,
                                  len(samples) >= minimum_repeats)
    variance = fmean((value - average) ** 2 for value in samples) * len(samples) / (len(samples) - 1)
    margin = 1.96 * sqrt(variance / len(samples))
    return MeasurementSummary(len(samples), average, median(samples), variance,
                              average - margin, average + margin,
                              len(samples) >= minimum_repeats)


def drifted(before: float, after: float, threshold: float = 0.05) -> bool:
    """Return true when sequential measurements differ by the relative threshold."""
    if threshold < 0:
        raise ValueError("drift threshold must not be negative")
    scale = max(abs(before), 1e-12)
    return abs(after - before) / scale > threshold


def sequentially_drifted(values: Iterable[float], threshold: float = 0.05) -> bool:
    samples = tuple(float(value) for value in values)
    if len(samples) < 4:
        return False
    midpoint = len(samples) // 2
    return drifted(fmean(samples[:midpoint]), fmean(samples[midpoint:]), threshold)


def benchmark_samples(
    benchmarks: Iterable[Mapping[str, object]], metric: str,
) -> dict[str, tuple[float, ...]]:
    grouped: dict[str, list[float]] = {}
    for benchmark in benchmarks:
        values = [_metric(workload.get("metrics", {}), metric)
                  for workload in benchmark.get("workloads", ())
                  if isinstance(workload, Mapping)]
        values = [value for value in values if value is not None]
        if values:
            grouped.setdefault(str(benchmark.get("name", "unknown")), []).append(fmean(values))
    return {name: tuple(values) for name, values in grouped.items()}


def _metric(metrics: object, name: str) -> float | None:
    if not isinstance(metrics, Mapping):
        return None
    value = metrics.get(name)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, Mapping):
        average = value.get("average", value.get("mean"))
        if isinstance(average, int | float) and not isinstance(average, bool):
            return float(average)
    return None
