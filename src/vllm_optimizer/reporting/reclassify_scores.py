"""Parse persisted benchmark evidence and score reclassified trials."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult
from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.reproduction.reader import load_manifest


def results(report: TrialReport, name: str | None = None) -> tuple[BenchmarkResult, ...]:
    parsed_results = []
    for item in report.benchmarks:
        if name is not None and item.get("name") != name:
            continue
        workloads = item.get("workloads", ())
        if not isinstance(workloads, tuple):
            continue
        parsed = tuple(
            WorkloadResult(int(value.get("index", 0)), value.get("configuration", {}), value.get("metrics", {}))
            for value in workloads
            if isinstance(value, Mapping)
        )
        if parsed:
            elapsed = item.get("elapsed_seconds")
            parsed_results.append(
                BenchmarkResult(
                    str(item.get("name", "unknown")),
                    str(item.get("backend", "unknown")),
                    str(item.get("backend_version", "unknown")),
                    parsed,
                    Path(str(item.get("raw_artifact", "."))),
                    cast(int, item.get("repeat")) if isinstance(item.get("repeat"), int) else None,
                    float(elapsed) if isinstance(elapsed, int | float) else None,
                )
            )
    return tuple(parsed_results)


def trial_score(run: Path, report: TrialReport, policy: ScoringManager) -> TrialScore | None:
    value = policy.score(results(report)) if report.status is WorkerStatus.COMPLETED else None
    if value is None:
        return None
    manifest = load_manifest(run, report.trial_id)
    parameters = manifest.get("parameters", {})
    selected_args = parameters.get("selected_args", {}) if isinstance(parameters, Mapping) else {}
    selected_env = parameters.get("selected_env", {}) if isinstance(parameters, Mapping) else {}
    quality = policy.quality(results(report))
    return TrialScore(
        report.trial_id,
        value,
        selected_args,
        selected_env,
        quality.successful,
        quality.errored,
        quality.incomplete,
        quality.excluded_workloads,
    )


def benchmark_score(run: Path, report: TrialReport, policy: ScoringManager, name: str) -> TrialScore | None:
    value = policy.score_each(results(report, name)).get(name)
    if value is None or report.status is not WorkerStatus.COMPLETED:
        return None
    score = trial_score(run, report, policy)
    return (
        TrialScore(
            report.trial_id,
            value,
            score.server_args,
            score.server_env,
            score.successful_requests,
            score.errored_requests,
            score.incomplete_requests,
            score.excluded_workloads,
        )
        if score
        else None
    )
