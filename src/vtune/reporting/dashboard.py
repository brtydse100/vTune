"""Compose the self-contained HTML decision dashboard."""

from __future__ import annotations

from html import escape
from pathlib import Path

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore
from vtune.reporting.analysis import parameter_importance
from vtune.reporting.charts import (
    comparison_chart, effect_charts, history_chart, scatter_chart,
)
from vtune.reporting.context import ReportContext
from vtune.reporting.tables import (
    benchmark_table, changes_table, evidence_table, failures, ranking_table,
)
from vtune.reproduction.export import export_vllm_command


def render_dashboard(
    directory: Path, metric: str, trials: tuple[TrialReport, ...],
    ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
    context: ReportContext,
) -> str:
    best_tuned = ranking[0] if ranking else None
    best = _best_observed(best_tuned, baseline)
    completed = sum(report.status.value == "completed" for report in trials)
    failed = sum(report.status.value == "failed" for report in trials)
    interrupted = sum(report.status.value == "interrupted" for report in trials)
    improvement = _improvement(best_tuned, baseline)
    cards = "".join((
        _card("Best observed", f"{best.value:.4f}" if best else "Unavailable",
              best.trial_id if best else "No completed tuned trial"),
        _card("Best tuned delta", f"{improvement:+.2f}%" if improvement is not None else "N/A",
              "Compared with baseline"),
        _card("Run status", context.status, f"{completed} completed · {failed} failed"),
        _card("Interrupted", str(interrupted), f"Run {context.run_id}"),
    ))
    command = _best_command(directory, best)
    importance = _importance(ranking)
    request_total = (best.successful_requests + best.errored_requests
                     + best.incomplete_requests) if best else 0
    quality = (f"{best.errored_requests + best.incomplete_requests} failed or incomplete "
               f"of {request_total}" if best and request_total
               else "Request counts unavailable" if best else "No eligible result")
    source = (f"<p>Retry source: <code>{escape(context.source_run_id)}</code></p>"
              if context.source_run_id else "")
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>vTune · {escape(context.run_id)}</title><style>{_css()}</style></head><body>
<header><div><p class='eyebrow'>vTune decision report</p><h1>{escape(context.run_id)}</h1>
<p>Maximize <code>{escape(metric)}</code> · Started {escape(context.started_at or 'unknown')}
· Completed {escape(context.completed_at or 'unknown')}</p>{source}</div>
<span class='status'>{escape(context.status)}</span></header>
<main><section class='cards'>{cards}</section>
<section><h2>Recommendation</h2>
<p><strong>{escape(best.trial_id) if best else 'No eligible trial'}</strong> was selected by lowest request
error percentage, then lowest error count, then highest <code>{escape(metric)}</code>.
Request quality: {escape(quality)}.</p>{changes_table(best, baseline)}
<p class='note'>These are observed relationships, not guaranteed causal effects. Multiple settings may change together.</p>
<h3>Reproduction command</h3><pre>{escape(command)}</pre></section>
<section><h2>Evidence behind the ranking</h2>{evidence_table(ranking)}
<p class='note'>A workload is excluded from score calculation when more than half of its requests
are errored or incomplete. A trial with no eligible workload is not ranked.</p></section>
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
</main><footer>Generated from local vTune run artifacts. No external services required.</footer></body></html>"""


def _card(label: str, value: str, detail: str) -> str:
    return (f"<article><span>{escape(label)}</span><strong>{escape(value)}</strong>"
            f"<small>{escape(detail)}</small></article>")


def _importance(ranking: tuple[TrialScore, ...]) -> str:
    if len(ranking) < 5:
        return ("<p class='muted'>Not shown: fewer than 5 eligible tuned trials. "
                "A percentage here would look precise without enough evidence.</p>")
    values = parameter_importance(ranking)
    confidence = "Exploratory association across evaluated trials; it is not causal."
    bars = "".join(
        f"<div class='hbar'><span>{escape(name)}</span><i style='width:{value * 70:.1f}%'></i>"
        f"<b>{value:.1%}</b></div>" for name, value in values.items()
    ) or "<p class='muted'>Not enough varied trials to estimate importance.</p>"
    return f"<p class='note'>{confidence}</p>{bars}"


def _best_command(directory: Path, best: TrialScore | None) -> str:
    if best is None:
        return "Unavailable: no completed tuned trial."
    try:
        return export_vllm_command(directory, best.trial_id)
    except ValueError as error:
        return f"Unavailable: {error}"


def _improvement(best: TrialScore | None, baseline: TrialScore | None) -> float | None:
    if best is None or baseline is None or baseline.value == 0:
        return None
    return (best.value - baseline.value) / baseline.value * 100


def _best_observed(
    best_tuned: TrialScore | None, baseline: TrialScore | None,
) -> TrialScore | None:
    candidates = [item for item in (best_tuned, baseline) if item is not None]
    return min(candidates, key=lambda item: (
        item.error_rate, item.errored_requests + item.incomplete_requests, -item.value,
    )) if candidates else None


def _css() -> str:
    return """*{box-sizing:border-box}body{margin:0;background:#f8fafc;color:#172033;font:15px system-ui}
header,main,footer{max-width:1200px;margin:auto}header{padding:36px 24px 20px;display:flex;justify-content:space-between}
h1{margin:.1rem 0;font-size:2rem}h2{margin-top:0}.eyebrow{color:#2563eb;font-weight:700;text-transform:uppercase}
.status{background:#dbeafe;color:#1d4ed8;padding:8px 14px;border-radius:999px;height:max-content}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;background:none;padding:0}
.cards article,section{background:white;border:1px solid #e2e8f0;border-radius:14px;padding:20px}.cards strong{display:block;font-size:1.65rem;margin:7px 0}.cards span,.cards small,.muted,.note{color:#64748b}
main{padding:0 24px;display:grid;gap:18px}.split{display:grid;grid-template-columns:1fr 1fr;gap:24px}pre{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:14px;border-radius:9px;overflow:auto}
.table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}code{font-size:12px}.hbar{display:flex;align-items:center;gap:8px;margin:9px 0}.hbar span{width:25%;overflow:hidden;text-overflow:ellipsis}.hbar i{display:block;height:13px;background:#2563eb;border-radius:5px}.hbar i.bad{background:#dc2626}.hbar b{white-space:nowrap}.warning{padding:12px;background:#fef2f2;color:#991b1b;border-radius:8px}svg{width:100%;max-height:310px}circle{fill:#2563eb}footer{padding:28px;color:#64748b}@media(max-width:800px){.cards,.split{grid-template-columns:1fr 1fr}}@media(max-width:520px){.cards,.split{grid-template-columns:1fr}}"""
