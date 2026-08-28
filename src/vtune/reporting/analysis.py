"""Dependency-free analysis used by the MVP static report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from statistics import fmean

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore


def parameter_importance(ranking: tuple[TrialScore, ...]) -> dict[str, float]:
    """Estimate importance from between-value score variance."""
    if len(ranking) < 2:
        return {}
    mean = fmean(item.value for item in ranking)
    total = sum((item.value - mean) ** 2 for item in ranking)
    if total == 0:
        return {}
    raw: dict[str, float] = {}
    names = set().union(*(item.server_args.keys() for item in ranking))
    for name in names:
        groups: dict[str, list[float]] = defaultdict(list)
        for item in ranking:
            groups[repr(item.server_args.get(name))].append(item.value)
        if len(groups) > 1:
            raw[name] = sum(
                len(values) * (fmean(values) - mean) ** 2 for values in groups.values()
            ) / total
    scale = sum(raw.values())
    return {name: value / scale for name, value in sorted(
        raw.items(), key=lambda item: item[1], reverse=True
    )} if scale else {}


def trial_metric(report: TrialReport, metric: str) -> float | None:
    values = []
    for benchmark in report.benchmarks:
        workloads = benchmark.get("workloads", ())
        if not isinstance(workloads, tuple):
            continue
        for workload in workloads:
            if not isinstance(workload, Mapping):
                continue
            metrics = workload.get("metrics")
            if isinstance(metrics, Mapping) and (value := _value(metrics.get(metric))) is not None:
                values.append(value)
    return fmean(values) if values else None


def _value(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, Mapping):
        return None
    successful = value.get("successful")
    if isinstance(successful, Mapping):
        value = successful.get("mean")
    else:
        value = value.get("mean")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
