"""Effective benchmark policy persisted with run results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace

from vllm_optimizer.benchmarks.configuration import (
    configured_failure_percentage,
    configured_min_repeats,
    configured_repeats,
    configured_warmup_repeats,
)
from vllm_optimizer.config.models import VTuneConfig


@dataclass(frozen=True, slots=True)
class BenchmarkPolicy:
    repeats: int = 3
    minimum_repeats: int = 3
    warmup_repeats: int = 1
    drift_threshold: float = 0.05
    maximum_failure_percentage: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)

    def with_maximum(self, maximum: float) -> BenchmarkPolicy:
        return replace(self, maximum_failure_percentage=maximum)


def effective_policy(config: VTuneConfig) -> BenchmarkPolicy:
    drift = config.analysis.get("drift_threshold", 0.05)
    if isinstance(drift, bool) or not isinstance(drift, int | float) or drift < 0:
        raise ValueError("analysis.drift_threshold must be a non-negative number")
    return BenchmarkPolicy(
        configured_repeats(config),
        configured_min_repeats(config),
        configured_warmup_repeats(config),
        float(drift),
        configured_failure_percentage(config),
    )


def stored_policy(document: Mapping[str, object], benchmark: Mapping[str, object]) -> BenchmarkPolicy:
    stored = document.get("benchmark_policy")
    values = stored if isinstance(stored, Mapping) else benchmark
    repeats = _integer(values.get("repeats"), 3)
    minimum = _integer(values.get("minimum_repeats", values.get("min_repeats")), min(3, repeats))
    warmups = _integer(values.get("warmup_repeats"), 1, allow_zero=True)
    drift = _number(values.get("drift_threshold"), 0.05)
    if values is benchmark and benchmark.get("accept_any_request_failures") is True:
        maximum = 100.0
    else:
        maximum = _number(values.get("maximum_failure_percentage", values.get("max_failure_percentage")), 0.0)
    return BenchmarkPolicy(repeats, minimum, warmups, drift, maximum)


def _integer(value: object, default: int, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= minimum else default


def _number(value: object, default: float) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
