"""Final run-level ranking persistence and terminal reporting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.run_documents import duration as _duration
from vllm_optimizer.managers.run_documents import improvement as _improvement
from vllm_optimizer.managers.run_documents import score_document as _document
from vllm_optimizer.managers.run_documents import status_counts as _status_counts
from vllm_optimizer.managers.run_documents import strings as _strings
from vllm_optimizer.managers.run_documents import trial_document as _trial_document
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reproduction.redaction import redact_environment, redact_values


class RunResultsManager:
    def __init__(
        self,
        output_path: Path,
        execution_mode: str = "sequential",
        benchmark_policy: Mapping[str, int | float] | None = None,
    ) -> None:
        self._output_path = Path(output_path)
        self._execution_mode = execution_mode
        self._benchmark_policy = dict(benchmark_policy or {})

    @property
    def output_path(self) -> Path:
        return self._output_path

    def save(
        self,
        run_id: str,
        metric: str,
        trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...],
        benchmark_rankings: dict[str, tuple[TrialScore, ...]],
        baseline: TrialScore | None = None,
        *,
        status: str = "completed",
        started_at: str | None = None,
        completed_at: str | None = None,
        source_run_id: str | None = None,
        sources: Mapping[str, Mapping[str, str]] | None = None,
        analysis_summary: str | None = None,
        run_failure: Mapping[str, object] | None = None,
    ) -> Path:
        links = sources or {}
        document = {
            "schema_version": 1,
            "run_id": run_id,
            "maximize": metric,
            "execution_mode": self._execution_mode,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": _duration(started_at, completed_at),
            "trial_counts": _status_counts(trials),
            "trials": [_trial_document(item, links.get(item.trial_id)) for item in trials],
            "ranking": [_document(item) for item in ranking],
            "best": _document(ranking[0]) if ranking else None,
            "baseline": _document(baseline) if baseline else None,
            "improvement_percent": _improvement(ranking, baseline),
            "best_by_benchmark": {
                name: _document(values[0]) if values else None for name, values in benchmark_rankings.items()
            },
            "benchmark_order": list(benchmark_rankings),
            "benchmark_policy": self._benchmark_policy,
        }
        if source_run_id is not None:
            document["source_run_id"] = source_run_id
        if analysis_summary is not None:
            document["analysis_summary"] = analysis_summary
        if run_failure is not None:
            document["run_failure"] = dict(run_failure)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._output_path.with_suffix(self._output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self._output_path)
        return self._output_path

    def summary(
        self,
        metric: str,
        trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...],
        benchmark_rankings: dict[str, tuple[TrialScore, ...]],
        baseline: TrialScore | None = None,
    ) -> str:
        counts = _status_counts(trials)
        lines = [
            f"Trials: {len(trials)} | completed={counts['completed']} "
            f"failed={counts['failed']} interrupted={counts['interrupted']}",
            f"Maximize: {metric}",
        ]
        if ranking:
            best = ranking[0]
            lines.extend(
                (
                    f"Best overall: {best.trial_id} ({best.value:.4f})",
                    f"Request quality: {best.successful_requests} successful, "
                    f"{best.errored_requests} errored, "
                    f"{best.incomplete_requests} incomplete",
                    f"Server args: {redact_values(best.server_args)}",
                    f"Server env: {redact_environment(_strings(best.server_env))}",
                )
            )
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
