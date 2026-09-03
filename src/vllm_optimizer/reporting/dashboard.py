"""Compose the self-contained HTML decision dashboard."""

from __future__ import annotations

from html import escape
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.benchmark_details import benchmark_details_table
from vllm_optimizer.reporting.charts import comparison_chart, effect_charts, history_chart, scatter_chart
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.dashboard_selection import best_command as _best_command
from vllm_optimizer.reporting.dashboard_selection import best_observed as _best_observed
from vllm_optimizer.reporting.dashboard_selection import improvement as _improvement
from vllm_optimizer.reporting.importance import importance_section
from vllm_optimizer.reporting.measurement import measurement_section
from vllm_optimizer.reporting.methodology import metric_methodology
from vllm_optimizer.reporting.styles import dashboard_css
from vllm_optimizer.reporting.tables import (
    benchmark_table,
    changes_table,
    evidence_table,
    failures,
    metrics_table,
    ranking_table,
)


def render_dashboard(
    directory: Path,
    metric: str,
    trials: tuple[TrialReport, ...],
    ranking: tuple[TrialScore, ...],
    baseline: TrialScore | None,
    context: ReportContext,
) -> str:
    best_tuned = ranking[0] if ranking else None
    best = _best_observed(best_tuned, baseline)
    best_report = next((report for report in trials if best and report.trial_id == best.trial_id), None)
    completed = sum(report.status.value == "completed" for report in trials)
    failed = sum(report.status.value == "failed" for report in trials)
    interrupted = sum(report.status.value == "interrupted" for report in trials)
    improvement = _improvement(best_tuned, baseline)
    cards = "".join(
        (
            _card(
                "Best observed",
                f"{best.value:.4f}" if best else "Unavailable",
                best.trial_id if best else "No completed tuned trial",
            ),
            _card(
                "Best tuned delta",
                f"{improvement:+.2f}%" if improvement is not None else "N/A",
                "Compared with baseline",
            ),
            _card("Run status", context.status, f"{completed} completed · {failed} failed"),
            _card("Interrupted", str(interrupted), f"Run {context.run_id}"),
        )
    )
    command = _best_command(directory, best)
    importance = importance_section(ranking)
    request_total = (best.successful_requests + best.errored_requests + best.incomplete_requests) if best else 0
    quality = (
        f"{best.errored_requests + best.incomplete_requests} failed or incomplete of {request_total}"
        if best and request_total
        else "Request counts unavailable"
        if best
        else "No eligible result"
    )
    source = f"<p>Retry source: <code>{escape(context.source_run_id)}</code></p>" if context.source_run_id else ""
    contention = (
        "<p class='note'><strong>Parallel measurement mode:</strong> when several "
        "workers are active, tuned trials may contend for shared host resources. "
        "The baseline ran alone; validate finalists sequentially before production "
        "decisions.</p>"
        if context.execution_mode == "local_parallel"
        else ""
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>vLLM Optimizer · {escape(context.run_id)}</title><style>{dashboard_css()}</style></head><body>
<header><div><p class='eyebrow'>vLLM Optimizer decision report</p><h1>{escape(context.run_id)}</h1>
<p>Maximize <code>{escape(metric)}</code> · Started {escape(context.started_at or "unknown")}
· Completed {escape(context.completed_at or "unknown")} · Mode {escape(context.execution_mode)}
</p>{source}</div>
<span class='status'>{escape(context.status)}</span></header>
<main>{contention}<section class='cards'>{cards}</section>
<section><h2>Recommendation</h2>
<p><strong>{escape(best.trial_id) if best else "No eligible trial"}</strong> was selected by the highest
<code>{escape(metric)}</code> among eligible trials, with request failures used only as deterministic tie-breakers.
Request quality: {escape(quality)}.</p>{changes_table(best, baseline)}
<p class='note'>These are observed relationships, not guaranteed causal effects. Multiple settings may change together.</p>
<h3>Reproduction command</h3><pre>{escape(command)}</pre></section>
<section><h2>Selected trial metrics</h2>
    <p class='note'>Metrics are averaged across the selected trial's benchmark workloads. Values are shown only when the benchmark backend supplied them.</p>
    {metrics_table(best_report)}</section>
    <section><h2>Per-benchmark measurements</h2>
    <p class='note'>Each row is one workload from one benchmark repeat, including its successful and failed request counts.</p>
    {benchmark_details_table(best_report)}</section>
    {metric_methodology()}
{measurement_section(trials, metric, context.minimum_repeats, context.drift_threshold)}
{_llm_section(context)}
<section><h2>Evidence behind the ranking</h2>{evidence_table(ranking)}
<p class='note'>A workload is excluded when its errored and incomplete requests exceed
{context.maximum_failure_percentage:g}% of all requests. Each eligible workload contributes its selected metric; runs use their workload mean, repeats use the median run score, and the trial score is the mean of named runs. A trial with no eligible workload is not ranked.</p></section>
<section class='split'><div><h2>Baseline vs top configurations</h2>{comparison_chart(ranking, baseline)}</div>
<div><h2>Score over time</h2>{history_chart(trials, ranking)}</div></section>
<section class='split'><div><h2>Parameter importance</h2>{importance}</div>
<div><h2>Throughput vs latency</h2>{scatter_chart(trials)}</div></section>
<section><h2>Observed parameter effects</h2>
<p class='note'>Bars show mean score by tested value; <code>n</code> is the number of observations.</p>
{effect_charts(ranking)}</section>
<section><h2>Best by benchmark</h2>{benchmark_table(context)}</section>
<section><h2>Top configurations</h2>{ranking_table(ranking, baseline)}</section>
<section><h2>Failures and interruptions</h2>{failures(trials)}</section>
</main><footer>{_footer(context)}</footer></body></html>"""


def _card(label: str, value: str, detail: str) -> str:
    return (
        f"<article><span>{escape(label)}</span><strong>{escape(value)}</strong>"
        f"<small>{escape(detail)}</small></article>"
    )


def _llm_section(context: ReportContext) -> str:
    if context.llm_summary:
        text = escape(context.llm_summary).replace("\n", "<br>")
        return f"<section><h2>Optional LLM summary</h2><p>{text}</p></section>"
    if context.llm_summary_error:
        return f"<section><h2>Optional LLM summary</h2><p class='warning'>{escape(context.llm_summary_error)}</p></section>"
    return ""


def _footer(context: ReportContext) -> str:
    if context.llm_summary:
        return "Generated from local vLLM Optimizer run artifacts; it includes a summary returned by the configured endpoint."
    return "Generated from local vLLM Optimizer run artifacts. No external services were used."
