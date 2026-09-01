"""Per-benchmark evidence table for the selected trial."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.reporting.analysis import DEFAULT_METRICS, workload_metric_summary


_COLUMNS = (
    ("Output tok/s", DEFAULT_METRICS["throughput_tokens_per_second"], "average"),
    ("TTFT median (ms)", DEFAULT_METRICS["ttft_ms"], "median"),
    ("TTFT P99 (ms)", DEFAULT_METRICS["ttft_ms"], "p99"),
    ("E2E median (ms)", DEFAULT_METRICS["end_to_end_ms"], "median"),
    ("E2E P99 (ms)", DEFAULT_METRICS["end_to_end_ms"], "p99"),
)


def benchmark_details_table(report: TrialReport | None) -> str:
    if report is None:
        return "<p class='muted'>No selected trial has benchmark details.</p>"
    rows = []
    for benchmark in report.benchmarks:
        workloads = benchmark.get("workloads", ())
        if not isinstance(workloads, tuple):
            continue
        for workload in workloads:
            if not isinstance(workload, Mapping):
                continue
            metrics = workload.get("metrics")
            if not isinstance(metrics, Mapping):
                continue
            cells = "".join(
                f"<td>{_number(workload_metric_summary(metrics, aliases).get(stat))}</td>"
                for _, aliases, stat in _COLUMNS
            )
            rows.append(
                f"<tr><td>{escape(str(benchmark.get('name', 'unknown')))}</td>"
                f"<td>{escape(str(benchmark.get('backend', 'unknown')))}</td>"
                f"<td>{escape(str(benchmark.get('repeat') or '—'))}</td>"
                f"<td>{escape(str(workload.get('index', '—')))}</td>"
                f"<td>{_seconds(benchmark.get('elapsed_seconds'))}</td>{cells}</tr>"
            )
    headers = ("Benchmark", "Backend", "Repeat", "Workload", "Elapsed", *(
        label for label, _, _ in _COLUMNS
    ))
    heading = "".join(f"<th>{escape(value)}</th>" for value in headers)
    body = "".join(rows) or f"<tr><td colspan='{len(headers)}'>No data available.</td></tr>"
    return f"<div class='table'><table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>"


def _number(value: object) -> str:
    return f"{value:.4f}" if isinstance(value, float) else "—"


def _seconds(value: object) -> str:
    return f"{value:.2f}s" if isinstance(value, int | float) and not isinstance(value, bool) else "—"
