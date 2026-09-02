"""Final run-level ranking persistence and terminal reporting."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Mapping

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reproduction.redaction import redact_environment, redact_values
from vllm_optimizer.reporting.analysis import default_metrics


class RunResultsManager:
    def __init__(self, output_path: Path, execution_mode: str = "sequential") -> None:
        self._output_path = Path(output_path)
        self._execution_mode = execution_mode

    def save(
        self, run_id: str, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...],
        benchmark_rankings: dict[str, tuple[TrialScore, ...]],
        baseline: TrialScore | None = None,
        *, status: str = "completed", started_at: str | None = None,
        completed_at: str | None = None, source_run_id: str | None = None,
        sources: Mapping[str, Mapping[str, str]] | None = None,
        analysis_summary: str | None = None,
    ) -> Path:
        links = sources or {}
        document = {
            "schema_version": 1, "run_id": run_id, "maximize": metric,
            "execution_mode": self._execution_mode,
            "status": status, "started_at": started_at, "completed_at": completed_at,
            "duration_seconds": _duration(started_at, completed_at),
            "trial_counts": _status_counts(trials),
            "trials": [_trial_document(item, links.get(item.trial_id)) for item in trials],
            "ranking": [_document(item) for item in ranking],
            "best": _document(ranking[0]) if ranking else None,
            "baseline": _document(baseline) if baseline else None,
            "improvement_percent": _improvement(ranking, baseline),
            "best_by_benchmark": {name: _document(values[0]) if values else None
                                  for name, values in benchmark_rankings.items()},
            "benchmark_order": list(benchmark_rankings),
        }
        if source_run_id is not None:
            document["source_run_id"] = source_run_id
        if analysis_summary is not None:
            document["analysis_summary"] = analysis_summary
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._output_path.with_suffix(self._output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self._output_path)
        return self._output_path

    def summary(
        self, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...],
        benchmark_rankings: dict[str, tuple[TrialScore, ...]],
        baseline: TrialScore | None = None,
    ) -> str:
        counts = _status_counts(trials)
        lines = [f"Trials: {len(trials)} | completed={counts['completed']} "
                 f"failed={counts['failed']} interrupted={counts['interrupted']}",
                 f"Maximize: {metric}"]
        if ranking:
            best = ranking[0]
            lines.extend((f"Best overall: {best.trial_id} ({best.value:.4f})",
                          f"Request quality: {best.successful_requests} successful, "
                          f"{best.errored_requests} errored, "
                          f"{best.incomplete_requests} incomplete",
                          f"Server args: {redact_values(best.server_args)}",
                          f"Server env: {redact_environment(_strings(best.server_env))}"))
        else:
            lines.append("Best overall: unavailable")
        if baseline:
            lines.append(f"Baseline: {baseline.value:.4f}")
            improvement = _improvement(ranking, baseline)
            if improvement is not None:
                lines.append(f"Improvement over baseline: {improvement:+.2f}%")
        for report in trials:
            if report.failure:
                lines.append(f"{report.trial_id}: {report.failure.code}: {report.failure.message}")
        for name, values in benchmark_rankings.items():
            conclusion = f"{values[0].trial_id} ({values[0].value:.4f})" if values else "unavailable"
            lines.append(f"Best for {name}: {conclusion}")
        lines.append(f"Run result: {self._output_path}")
        return "\n".join(lines)


def _document(score: TrialScore) -> dict[str, object]:
    return {"trial_id": score.trial_id, "score": score.value,
            "successful_requests": score.successful_requests,
            "errored_requests": score.errored_requests,
            "incomplete_requests": score.incomplete_requests,
            "excluded_workloads": score.excluded_workloads,
            "error_rate": score.error_rate,
            "server_args": redact_values(score.server_args),
            "server_env": redact_environment(_strings(score.server_env))}


def _strings(values: Mapping[str, object]) -> dict[str, str]:
    return {str(name): str(value) for name, value in values.items()}


def _trial_document(
    report: TrialReport, source: Mapping[str, str] | None = None,
) -> dict[str, object]:
    failure = None
    if report.failure:
        failure = {"code": report.failure.code, "message": report.failure.message,
                   "retryable": report.failure.retryable}
    document = {"trial_id": report.trial_id, "status": report.status.value,
                "failure": failure, "benchmark_count": len(report.benchmarks),
                "metrics": default_metrics(report),
                "benchmarks": report.to_dict()["benchmarks"]}
    if report.execution:
        document["execution"] = dict(report.execution)
    if source is not None:
        document["source"] = dict(source)
    return document


def _status_counts(trials: tuple[TrialReport, ...]) -> dict[str, int]:
    return {status: sum(report.status.value == status for report in trials)
            for status in ("completed", "failed", "interrupted")}


def _improvement(
    ranking: tuple[TrialScore, ...], baseline: TrialScore | None
) -> float | None:
    if not ranking or baseline is None or baseline.value == 0:
        return None
    return (ranking[0].value - baseline.value) / baseline.value * 100


def _duration(started_at: str | None, completed_at: str | None) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        return max(0.0, (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds())
    except ValueError:
        return None
