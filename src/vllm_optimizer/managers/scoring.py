"""Selection of the best completed trial for one configured metric."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import fmean, median

from vllm_optimizer.domain.benchmark import BenchmarkResult


@dataclass(frozen=True, slots=True)
class TrialScore:
    trial_id: str
    value: float
    server_args: Mapping[str, object]
    server_env: Mapping[str, object]
    successful_requests: int = 0
    errored_requests: int = 0
    incomplete_requests: int = 0
    excluded_workloads: int = 0

    @property
    def error_rate(self) -> float:
        total = self.successful_requests + self.errored_requests + self.incomplete_requests
        return (self.errored_requests + self.incomplete_requests) / total if total else 0.0


@dataclass(frozen=True, slots=True)
class QualitySummary:
    successful: int = 0
    errored: int = 0
    incomplete: int = 0
    excluded_workloads: int = 0


class ScoringManager:
    def __init__(
        self,
        metric: str,
        minimum_repeats: int = 1,
        required_runs: tuple[str, ...] = (),
        max_failure_percentage: float = 0,
    ) -> None:
        if not metric.strip():
            raise ValueError("optimization.maximize must not be empty")
        if not isinstance(minimum_repeats, int) or isinstance(minimum_repeats, bool) or minimum_repeats < 1:
            raise ValueError("minimum repeats must be positive")
        self.metric = metric
        self.minimum_repeats = minimum_repeats
        self.required_runs = required_runs
        if (
            isinstance(max_failure_percentage, bool)
            or not isinstance(max_failure_percentage, int | float)
            or not 0 <= max_failure_percentage <= 100
        ):
            raise ValueError("maximum failure percentage must be between 0 and 100")
        self.max_failure_percentage = float(max_failure_percentage)

    def score(self, results: tuple[BenchmarkResult, ...]) -> float | None:
        scores = self.score_each(results)
        if self.required_runs and any(name not in scores for name in self.required_runs):
            return None
        values = tuple(scores.values())
        return fmean(values) if values else None

    def score_each(self, results: tuple[BenchmarkResult, ...]) -> dict[str, float]:
        grouped: dict[str, list[float]] = {}
        for result in results:
            values = [
                value
                for workload in result.workloads
                if _eligible(workload.metrics, self.max_failure_percentage)
                if (value := _metric_value(workload.metrics.get(self.metric))) is not None
            ]
            if values:
                grouped.setdefault(result.run_name, []).append(fmean(values))
        return {name: float(median(values)) for name, values in grouped.items() if len(values) >= self.minimum_repeats}

    @staticmethod
    def rank(scores: list[TrialScore]) -> tuple[TrialScore, ...]:
        return tuple(
            sorted(
                scores,
                key=lambda item: (
                    -item.value,
                    item.error_rate,
                    item.errored_requests + item.incomplete_requests,
                    item.trial_id,
                ),
            )
        )

    def quality(self, results: tuple[BenchmarkResult, ...]) -> QualitySummary:
        successful = errored = incomplete = excluded = 0
        for result in results:
            for workload in result.workloads:
                counts = _request_counts(workload.metrics)
                successful += counts[0]
                errored += counts[1]
                incomplete += counts[2]
                excluded += not self._eligible(workload.metrics)
        return QualitySummary(successful, errored, incomplete, excluded)

    def _eligible(self, metrics: Mapping[str, object]) -> bool:
        return _eligible(metrics, self.max_failure_percentage)


def _metric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, Mapping):
        return None
    average = value.get("average")
    if isinstance(average, int | float) and not isinstance(average, bool):
        return float(average)
    successful = value.get("successful")
    if isinstance(successful, Mapping):
        mean = successful.get("mean")
        if isinstance(mean, int | float) and not isinstance(mean, bool):
            return float(mean)
    mean = value.get("mean")
    return float(mean) if isinstance(mean, int | float) and not isinstance(mean, bool) else None


def _request_counts(metrics: Mapping[str, object]) -> tuple[int, int, int]:
    totals = metrics.get("request_totals")
    if not isinstance(totals, Mapping):
        return 0, 0, 0
    return tuple(_count(totals.get(name)) for name in ("successful", "errored", "incomplete"))  # type: ignore[return-value]


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _eligible(metrics: Mapping[str, object], max_failure_percentage: float = 0) -> bool:
    successful, errored, incomplete = _request_counts(metrics)
    total = successful + errored + incomplete
    return successful > 0 and total > 0 and 100 * (errored + incomplete) / total <= max_failure_percentage
