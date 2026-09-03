"""Regenerate static exports from an immutable run without execution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from vllm_optimizer.benchmarks.policy import BenchmarkPolicy, stored_policy
from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.analysis import default_metrics
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.offline_loading import load_trial as _load_trial
from vllm_optimizer.reporting.offline_loading import read_object as _read_object
from vllm_optimizer.reporting.reporter import Reporter
from vllm_optimizer.reporting.validation import mapping as _mapping
from vllm_optimizer.reporting.validation import object_list as _objects
from vllm_optimizer.reporting.validation import optional_text as _optional_text
from vllm_optimizer.reporting.validation import require as _require
from vllm_optimizer.reporting.validation import text as _text
from vllm_optimizer.reproduction.reader import load_manifest


@dataclass(frozen=True, slots=True)
class RegeneratedReport:
    directory: Path
    result: Path
    csv: Path
    html: Path
    warnings: tuple[str, ...] = ()


def regenerate_report(run: Path, output: Path | None = None) -> RegeneratedReport:
    source = Path(run).resolve()
    document = _read_object(source / "result.json", "run result")
    _require(document.get("schema_version") == 1, "run result has an invalid schema")
    _require(document.get("run_id") == source.name, "run result ID does not match its directory")
    destination = Path(output).resolve() if output else _default_destination(source)
    _require(destination != source, "report output cannot replace the source run")
    _require(not destination.exists(), f"report output already exists: {destination}")

    trial_summaries = _objects(document, "trials")
    warnings: list[str] = []
    trials = tuple(_load_trial(source, item, warnings) for item in trial_summaries)
    for summary, trial in zip(trial_summaries, trials, strict=True):
        cast(dict[str, object], summary)["metrics"] = default_metrics(trial)
    ranking = tuple(_score(item) for item in _objects(document, "ranking"))
    baseline_raw = document.get("baseline")
    baseline = _score(baseline_raw) if isinstance(baseline_raw, Mapping) else None
    benchmark_rankings = {
        str(name): ((_score(value),) if isinstance(value, Mapping) else ())
        for name, value in _mapping(document, "best_by_benchmark").items()
    }
    _validate_scores(trials, ranking, baseline, benchmark_rankings)
    policy = _benchmark_policy(document, source, trials)
    context = ReportContext(
        str(document["run_id"]),
        str(document.get("status", "unknown")),
        _optional_text(document.get("started_at")),
        _optional_text(document.get("completed_at")),
        _optional_text(document.get("source_run_id")),
        _sources(document),
        benchmark_rankings,
        str(document.get("execution_mode", "sequential")),
        _string_tuple(document.get("benchmark_order")),
        _optional_text(document.get("analysis_summary")),
        minimum_repeats=policy.minimum_repeats,
        drift_threshold=policy.drift_threshold,
        maximum_failure_percentage=policy.maximum_failure_percentage,
    )
    destination.mkdir(parents=True)
    result_path = destination / "result.json"
    result_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    csv_path, html_path = Reporter(destination, source).write(
        str(document.get("maximize", "unknown")), trials, ranking, baseline, context
    )
    return RegeneratedReport(destination, result_path, csv_path, html_path, tuple(warnings))


def _default_destination(run: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return run / "regenerated" / stamp


def _score(value: Mapping[str, object]) -> TrialScore:
    score = value.get("score")
    _require(isinstance(score, int | float) and not isinstance(score, bool), "stored ranking contains an invalid score")
    return TrialScore(
        _text(value, "trial_id"),
        float(cast(int | float, score)),
        dict(_mapping(value, "server_args")),
        dict(_mapping(value, "server_env")),
        _optional_count(value.get("successful_requests")),
        _optional_count(value.get("errored_requests")),
        _optional_count(value.get("incomplete_requests")),
        _optional_count(value.get("excluded_workloads")),
    )


def _optional_count(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _validate_scores(
    trials: tuple[TrialReport, ...],
    ranking: tuple[TrialScore, ...],
    baseline: TrialScore | None,
    by_benchmark: Mapping[str, tuple[TrialScore, ...]],
) -> None:
    completed = {trial.trial_id for trial in trials if trial.status is WorkerStatus.COMPLETED}
    scores = (*ranking, *((values[0]) for values in by_benchmark.values() if values))
    if baseline:
        scores = (*scores, baseline)
    _require(
        all(score.trial_id in completed for score in scores), "stored ranking references an incomplete or missing trial"
    )


def _sources(document: Mapping[str, object]) -> dict[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for item in _objects(document, "trials"):
        source = item.get("source")
        if isinstance(source, Mapping):
            result[str(item.get("trial_id"))] = {str(k): str(v) for k, v in source.items()}
    return result


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple | list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _benchmark_policy(document: Mapping[str, object], run: Path, trials: tuple[TrialReport, ...]) -> BenchmarkPolicy:
    if not trials:
        return stored_policy(document, {})
    benchmark = load_manifest(run, trials[0].trial_id).get("benchmark", {})
    return stored_policy(document, benchmark if isinstance(benchmark, Mapping) else {})
