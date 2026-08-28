"""Final run-level ranking persistence and terminal reporting."""

from __future__ import annotations

import json
from pathlib import Path

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore


class RunResultsManager:
    def __init__(self, output_path: Path) -> None:
        self._output_path = Path(output_path)

    def save(
        self, run_id: str, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...],
        benchmark_rankings: dict[str, tuple[TrialScore, ...]],
        baseline: TrialScore | None = None,
    ) -> Path:
        document = {
            "schema_version": 1, "run_id": run_id, "maximize": metric,
            "trial_counts": _status_counts(trials),
            "trials": [_trial_document(item) for item in trials],
            "ranking": [_document(item) for item in ranking],
            "best": _document(ranking[0]) if ranking else None,
            "baseline": _document(baseline) if baseline else None,
            "improvement_percent": _improvement(ranking, baseline),
            "best_by_benchmark": {name: _document(values[0]) if values else None
                                  for name, values in benchmark_rankings.items()},
        }
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
                          f"Server args: {dict(best.server_args)}",
                          f"Server env: {dict(best.server_env)}"))
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
            "server_args": dict(score.server_args), "server_env": dict(score.server_env)}


def _trial_document(report: TrialReport) -> dict[str, object]:
    failure = None
    if report.failure:
        failure = {"code": report.failure.code, "message": report.failure.message,
                   "retryable": report.failure.retryable}
    return {"trial_id": report.trial_id, "status": report.status.value,
            "failure": failure, "benchmark_count": len(report.benchmarks)}


def _status_counts(trials: tuple[TrialReport, ...]) -> dict[str, int]:
    return {status: sum(report.status.value == status for report in trials)
            for status in ("completed", "failed", "interrupted")}


def _improvement(
    ranking: tuple[TrialScore, ...], baseline: TrialScore | None
) -> float | None:
    if not ranking or baseline is None or baseline.value == 0:
        return None
    return (ranking[0].value - baseline.value) / baseline.value * 100
