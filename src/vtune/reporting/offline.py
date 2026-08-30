"""Regenerate static exports from an immutable run without execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from vtune.domain.attempt_report import AttemptReport
from vtune.domain.results import Failure, WorkerStatus
from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore
from vtune.reporting.context import ReportContext
from vtune.reporting.reporter import Reporter
from vtune.reproduction.reader import load_manifest


@dataclass(frozen=True, slots=True)
class RegeneratedReport:
    directory: Path
    result: Path
    csv: Path
    html: Path


def regenerate_report(run: Path, output: Path | None = None) -> RegeneratedReport:
    source = Path(run).resolve()
    document = _read_object(source / "result.json", "run result")
    _require(document.get("schema_version") == 1, "run result has an invalid schema")
    _require(document.get("run_id") == source.name, "run result ID does not match its directory")
    destination = Path(output).resolve() if output else _default_destination(source)
    _require(destination != source, "report output cannot replace the source run")
    _require(not destination.exists(), f"report output already exists: {destination}")

    trials = tuple(_load_trial(source, item) for item in _objects(document, "trials"))
    ranking = tuple(_score(item) for item in _objects(document, "ranking"))
    baseline_raw = document.get("baseline")
    baseline = _score(baseline_raw) if isinstance(baseline_raw, Mapping) else None
    benchmark_rankings = {
        str(name): ((_score(value),) if isinstance(value, Mapping) else ())
        for name, value in _mapping(document, "best_by_benchmark").items()
    }
    _validate_scores(trials, ranking, baseline, benchmark_rankings)
    context = ReportContext(
        str(document["run_id"]), str(document.get("status", "unknown")),
        _optional_text(document.get("started_at")),
        _optional_text(document.get("completed_at")),
        _optional_text(document.get("source_run_id")), _sources(document),
        benchmark_rankings, str(document.get("execution_mode", "sequential")),
    )
    destination.mkdir(parents=True)
    result_path = destination / "result.json"
    result_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    csv_path, html_path = Reporter(destination, source).write(
        str(document.get("maximize", "unknown")), trials, ranking, baseline, context,
    )
    return RegeneratedReport(destination, result_path, csv_path, html_path)


def _default_destination(run: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return run / "regenerated" / stamp


def _load_trial(run: Path, summary: Mapping[str, object]) -> TrialReport:
    trial_id = _text(summary, "trial_id")
    document = _read_object(run / "trials" / trial_id / "result.json", "trial result")
    _require(document.get("schema_version") == 1, f"trial {trial_id} has an invalid schema")
    _require(document.get("trial_id") == trial_id, f"trial result ID mismatch: {trial_id}")
    _require(document.get("status") == summary.get("status"),
             f"trial status mismatch: {trial_id}")
    load_manifest(run, trial_id)
    status = _status(document.get("status"), trial_id)
    failure = _failure(document.get("failure"))
    benchmarks = document.get("benchmarks", [])
    artifacts = document.get("artifacts", {})
    _require(isinstance(benchmarks, list), f"trial {trial_id} has invalid benchmarks")
    _require(isinstance(artifacts, Mapping), f"trial {trial_id} has invalid artifacts")
    attempts_raw = document.get("attempts", [])
    _require(isinstance(attempts_raw, list)
             and all(isinstance(item, Mapping) for item in attempts_raw),
             f"trial {trial_id} has invalid attempts")
    attempts = tuple(_attempt(item) for item in attempts_raw)
    return TrialReport(1, trial_id, status, tuple(benchmarks), {
        str(k): str(v) for k, v in artifacts.items()
    }, attempts, failure)


def _score(value: Mapping[str, object]) -> TrialScore:
    score = value.get("score")
    _require(isinstance(score, int | float) and not isinstance(score, bool),
             "stored ranking contains an invalid score")
    return TrialScore(_text(value, "trial_id"), float(score),
                      dict(_mapping(value, "server_args")),
                      dict(_mapping(value, "server_env")),
                      _optional_count(value.get("successful_requests")),
                      _optional_count(value.get("errored_requests")),
                      _optional_count(value.get("incomplete_requests")),
                      _optional_count(value.get("excluded_workloads")))


def _optional_count(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _validate_scores(
    trials: tuple[TrialReport, ...], ranking: tuple[TrialScore, ...],
    baseline: TrialScore | None,
    by_benchmark: Mapping[str, tuple[TrialScore, ...]],
) -> None:
    completed = {trial.trial_id for trial in trials
                 if trial.status is WorkerStatus.COMPLETED}
    scores = (*ranking, *((values[0]) for values in by_benchmark.values() if values))
    if baseline:
        scores = (*scores, baseline)
    _require(all(score.trial_id in completed for score in scores),
             "stored ranking references an incomplete or missing trial")


def _attempt(value: Mapping[str, object]) -> AttemptReport:
    index = value.get("index")
    _require(isinstance(index, int), "trial attempt has an invalid index")
    artifacts = _mapping(value, "artifacts")
    return AttemptReport(index, _status(value.get("status"), f"attempt {index}"),
                         {str(k): str(v) for k, v in artifacts.items()},
                         _failure(value.get("failure")))


def _failure(value: object) -> Failure | None:
    if value is None:
        return None
    _require(isinstance(value, Mapping), "stored failure is invalid")
    return Failure(_text(value, "code"), _text(value, "message"),
                   bool(value.get("retryable", False)))


def _status(value: object, owner: str) -> WorkerStatus:
    try:
        return WorkerStatus(value)
    except ValueError as error:
        raise ValueError(f"{owner} has invalid status: {value}") from error


def _read_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {label} '{path}': {error}") from error
    _require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def _objects(document: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    value = document.get(name)
    _require(isinstance(value, list) and all(isinstance(item, Mapping) for item in value),
             f"run result has invalid {name}")
    return value


def _mapping(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = document.get(name, {})
    _require(isinstance(value, Mapping), f"stored {name} must be an object")
    return value


def _sources(document: Mapping[str, object]) -> dict[str, Mapping[str, str]]:
    return {str(item["trial_id"]): {str(k): str(v) for k, v in item["source"].items()}
            for item in _objects(document, "trials")
            if isinstance(item.get("source"), Mapping)}


def _text(document: Mapping[str, object], name: str) -> str:
    value = document.get(name)
    _require(isinstance(value, str) and bool(value), f"stored {name} must be text")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)
