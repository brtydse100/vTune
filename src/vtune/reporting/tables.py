"""HTML tables and summaries for the static dashboard."""

from __future__ import annotations

from collections import Counter
from html import escape
import json

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore
from vtune.reporting.context import ReportContext


def ranking_table(
    ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
) -> str:
    unique = _unique_changed(ranking, baseline)
    rows = "".join(
        f"<tr><td>{index}</td><td>{escape(item.trial_id)}</td><td>{item.value:.4f}</td>"
        f"<td>{item.error_rate:.2%}</td><td>{item.errored_requests}</td>"
        f"<td><code>{escape(json.dumps(changes, sort_keys=True))}</code></td></tr>"
        for index, (item, changes) in enumerate(unique, start=1)
    )
    return _table(("Rank", "Trial", "Score", "Error rate", "Errors",
                   "Changed settings"), rows)


def evidence_table(ranking: tuple[TrialScore, ...]) -> str:
    rows = "".join(
        f"<tr><td>{escape(item.trial_id)}</td><td>{item.value:.4f}</td>"
        f"<td>{item.successful_requests}</td><td>{item.errored_requests}</td>"
        f"<td>{item.incomplete_requests}</td><td>{item.error_rate:.2%}</td>"
        f"<td>{item.excluded_workloads}</td></tr>" for item in ranking
    )
    return _table(("Trial", "Metric", "Successful", "Errored", "Incomplete",
                   "Error rate", "Excluded workloads"), rows)


def benchmark_table(context: ReportContext) -> str:
    rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{escape(values[0].trial_id)}</td>"
        f"<td>{values[0].value:.4f}</td></tr>"
        for name, values in context.benchmark_rankings.items() if values
    )
    return _table(("Benchmark", "Best trial", "Score"), rows)


def changes_table(best: TrialScore | None, baseline: TrialScore | None) -> str:
    if best is None:
        return "<p class='warning'>No completed tuned trial produced a trustworthy winner.</p>"
    base = dict(baseline.server_args) if baseline else {}
    names = sorted(set(base) | set(best.server_args))
    rows = "".join(
        f"<tr><td><code>{escape(name)}</code></td>"
        f"<td>{escape(repr(base.get(name, '(vLLM default)')))}</td>"
        f"<td>{escape(repr(best.server_args.get(name, '(vLLM default)')))}</td></tr>"
        for name in names if base.get(name) != best.server_args.get(name)
    )
    return (_table(("Setting", "Baseline", "Best observed"), rows)
            if rows else "<p>No explicit server arguments changed from baseline.</p>")


def failures(trials: tuple[TrialReport, ...]) -> str:
    failed = [report for report in trials if report.failure]
    if not failed:
        return "<p>No failed or interrupted trials.</p>"
    counts = Counter(report.failure.code for report in failed if report.failure)
    maximum = max(counts.values())
    chart = "".join(
        f"<div class='hbar'><span>{escape(name)}</span>"
        f"<i class='bad' style='width:{count / maximum * 70:.1f}%'></i><b>{count}</b></div>"
        for name, count in counts.most_common()
    )
    rows = "".join(
        f"<tr><td>{escape(report.trial_id)}</td><td>{report.status.value}</td>"
        f"<td>{escape(report.failure.code)}</td><td>{escape(report.failure.message)}</td>"
        f"<td>{len(report.attempts)}</td></tr>" for report in failed if report.failure
    )
    return chart + _table(("Trial", "Status", "Category", "Details", "Attempts"), rows)


def _unique_changed(
    ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
) -> list[tuple[TrialScore, dict[str, object]]]:
    base_args = dict(baseline.server_args) if baseline else {}
    base_env = dict(baseline.server_env) if baseline else {}
    unique: list[tuple[TrialScore, dict[str, object]]] = []
    seen: set[str] = set()
    for item in ranking:
        changes = {name: value for name, value in item.server_args.items()
                   if base_args.get(name) != value}
        changes.update({f"env.{name}": value for name, value in item.server_env.items()
                        if base_env.get(name) != value})
        fingerprint = json.dumps(changes, sort_keys=True, default=repr)
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append((item, changes))
    return unique


def _table(headers: tuple[str, ...], rows: str) -> str:
    heading = "".join(f"<th>{escape(value)}</th>" for value in headers)
    body = rows or f"<tr><td colspan='{len(headers)}'>No data available.</td></tr>"
    return f"<div class='table'><table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>"
