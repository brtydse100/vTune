"""Selection of the best completed trial for one configured metric."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import fmean, median

from vtune.domain.benchmark import BenchmarkResult


@dataclass(frozen=True, slots=True)
class TrialScore:
    trial_id: str
    value: float
    server_args: Mapping[str, object]
    server_env: Mapping[str, object]


class ScoringManager:
    def __init__(self, metric: str) -> None:
        if not metric.strip():
            raise ValueError("optimization.maximize must not be empty")
        self.metric = metric

    def score(self, results: tuple[BenchmarkResult, ...]) -> float | None:
        values = tuple(self.score_each(results).values())
        return fmean(values) if values else None

    def score_each(self, results: tuple[BenchmarkResult, ...]) -> dict[str, float]:
        grouped: dict[str, list[float]] = {}
        for result in results:
            values = [value for workload in result.workloads
                      if (value := _metric_value(workload.metrics.get(self.metric))) is not None]
            if values:
                grouped.setdefault(result.run_name, []).append(fmean(values))
        return {name: float(median(values)) for name, values in grouped.items()}

    @staticmethod
    def rank(scores: list[TrialScore]) -> tuple[TrialScore, ...]:
        return tuple(sorted(scores, key=lambda item: item.value, reverse=True))


def _metric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, Mapping):
        return None
    successful = value.get("successful")
    if isinstance(successful, Mapping):
        mean = successful.get("mean")
        if isinstance(mean, int | float) and not isinstance(mean, bool):
            return float(mean)
    mean = value.get("mean")
    return float(mean) if isinstance(mean, int | float) and not isinstance(mean, bool) else None
