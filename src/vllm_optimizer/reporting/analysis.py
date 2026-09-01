"""Dependency-free analysis used by the MVP static report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from statistics import fmean

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore


DEFAULT_METRICS = {
    "requests_per_second": ("requests_per_second", "request_throughput"),
    "throughput_tokens_per_second": ("output_tokens_per_second", "output_throughput"),
    "total_tokens_per_second": ("total_tokens_per_second", "total_token_throughput"),
    "ttft_ms": ("time_to_first_token_ms", "time_to_first_token", "mean_ttft_ms", "median_ttft_ms", "p99_ttft_ms"),
    "tpot_ms": ("time_per_output_token_ms", "mean_tpot_ms", "median_tpot_ms", "p99_tpot_ms"),
    "itl_ms": ("inter_token_latency_ms", "mean_itl_ms", "median_itl_ms", "p99_itl_ms"),
    "end_to_end_ms": ("end_to_end_latency_ms", "end_to_end_latency", "mean_e2el_ms",
                      "median_e2el_ms", "p99_e2el_ms"),
    "total_time_seconds": ("total_time_seconds", "total_time", "duration"),
}


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


def parameter_effects(
    ranking: tuple[TrialScore, ...],
) -> dict[str, tuple[tuple[str, float, int], ...]]:
    """Group observed scores by each varied argument value."""
    names = set().union(*(item.server_args.keys() for item in ranking)) if ranking else set()
    effects = {}
    for name in sorted(names):
        groups: dict[str, list[float]] = defaultdict(list)
        for item in ranking:
            groups[repr(item.server_args.get(name))].append(item.value)
        if len(groups) > 1:
            effects[name] = tuple(
                (value, fmean(scores), len(scores))
                for value, scores in sorted(groups.items())
            )
    return effects


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


def default_metrics(report: TrialReport) -> dict[str, dict[str, float]]:
    """Return comparable common metrics without inventing missing measurements."""
    return {
        name: summary for name, aliases in DEFAULT_METRICS.items()
        if (summary := _metric_summary(report, aliases))
    }


def _metric_summary(report: TrialReport, aliases: tuple[str, ...]) -> dict[str, float]:
    summaries = []
    for benchmark in report.benchmarks:
        for workload in benchmark.get("workloads", ()):
            if not isinstance(workload, Mapping) or not isinstance(workload.get("metrics"), Mapping):
                continue
            summaries.append(workload_metric_summary(workload["metrics"], aliases))
    if not summaries:
        return {}
    return {name: fmean(values) for name in ("average", "median", "p99")
            if (values := [summary[name] for summary in summaries if name in summary])}


def workload_metric_summary(
    metrics: Mapping[str, object], aliases: tuple[str, ...],
) -> dict[str, float]:
    """Merge available statistics across canonical and legacy aliases."""
    result: dict[str, float] = {}
    for name in aliases:
        for statistic, value in _summary(name, metrics.get(name)).items():
            result.setdefault(statistic, value)
    return result


def _summary(name: str, value: object) -> dict[str, float]:
    if isinstance(value, int | float) and not isinstance(value, bool):
        number = float(value)
        if name.startswith("p99_"):
            return {"p99": number}
        if name.startswith("median_"):
            return {"median": number}
        if name.startswith("mean_"):
            return {"average": number}
        return {"average": number}
    if not isinstance(value, Mapping):
        return {}
    observed = value.get("successful")
    source = observed if isinstance(observed, Mapping) else value
    result = {statistic: number for key, statistic in (
              ("mean", "average"), ("average", "average"),
              ("median", "median"), ("p99", "p99"))
              if isinstance((number := source.get(key)), int | float)
              and not isinstance(number, bool)}
    return result


def _value(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, Mapping):
        return None
    if isinstance((average := value.get("average")), int | float) and not isinstance(average, bool):
        return float(average)
    successful = value.get("successful")
    if isinstance(successful, Mapping):
        value = successful.get("mean")
    else:
        value = value.get("mean")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
