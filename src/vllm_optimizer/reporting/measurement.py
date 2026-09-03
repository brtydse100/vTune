"""HTML evidence for repeat variance and sequential drift."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from statistics import fmean

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.measurement import MeasurementSummary, drifted, summarize


def measurement_section(
    trials: tuple[TrialReport, ...], metric: str, minimum_repeats: int = 2, drift_threshold: float = 0.05
) -> str:
    rows: list[str] = []
    for trial in trials:
        grouped: dict[str, list[float]] = {}
        for benchmark in trial.benchmarks:
            workloads = benchmark.get("workloads", ())
            if not isinstance(workloads, tuple | list):
                continue
            measured = [
                _metric(workload.get("metrics", {}), metric) for workload in workloads if isinstance(workload, Mapping)
            ]
            scores = [value for value in measured if value is not None]
            if scores:
                grouped.setdefault(str(benchmark.get("name", "unknown")), []).append(fmean(scores))
        for name, values in grouped.items():
            summary = summarize(values, minimum_repeats)
            warning = _warning(values, summary, drift_threshold)
            rows.append(_row(trial.trial_id, name, summary, warning))
    body = "".join(rows) or "<tr><td colspan='8'>No repeat measurements available.</td></tr>"
    return f"""<section><h2>Measurement uncertainty</h2>
<p class='note'>Repeat scores use sample variance and a 95% Student's t confidence interval.
At least {minimum_repeats} measured repeats are required for the configured confidence policy.
Finalists whose sequential measurements drift by more than {drift_threshold:.0%} require a rerun.</p>
<table><thead><tr><th>Trial</th><th>Benchmark</th><th>n</th><th>Mean</th><th>Median</th>
<th>Variance</th><th>95% CI</th><th>Policy</th></tr></thead><tbody>{body}</tbody></table></section>"""


def _row(trial: str, name: str, summary: MeasurementSummary, warning: str) -> str:
    variance = "—" if summary.variance is None else f"{summary.variance:.6g}"
    interval = (
        "—" if summary.confidence_low is None else f"[{summary.confidence_low:.6g}, {summary.confidence_high:.6g}]"
    )
    policy = warning or (
        "exploratory — fewer than 3 measurements"
        if summary.count < 3
        else "ready"
        if summary.minimum_repeats_met
        else "minimum repeats not met"
    )
    return (
        f"<tr><td>{escape(trial)}</td><td>{escape(name)}</td><td>{summary.count}</td>"
        f"<td>{summary.mean:.6g}</td><td>{summary.median:.6g}</td><td>{variance}</td>"
        f"<td>{interval}</td><td>{escape(policy)}</td></tr>"
    )


def _warning(values: list[float], summary: MeasurementSummary, threshold: float) -> str:
    if len(values) < 4:
        return "drift unavailable — fewer than 4 measurements"
    midpoint = len(values) // 2
    before, after = fmean(values[:midpoint]), fmean(values[midpoint:])
    return "sequential drift — rerun finalist" if drifted(before, after, threshold) else ""


def _metric(metrics: object, name: str) -> float | None:
    if not isinstance(metrics, Mapping):
        return None
    value = metrics.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, Mapping):
        average = value.get("average", value.get("mean"))
        if isinstance(average, (int, float)) and not isinstance(average, bool):
            return float(average)
    return None
