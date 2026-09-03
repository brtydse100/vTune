"""Load and validate immutable run data for offline reporting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from vllm_optimizer.domain.attempt_report import AttemptReport
from vllm_optimizer.domain.results import Failure, WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.lifecycle.integrity import artifact_warnings
from vllm_optimizer.reporting.validation import execution, mapping, require, text
from vllm_optimizer.reproduction.reader import load_manifest


def load_trial(run: Path, summary: Mapping[str, object], warnings: list[str]) -> TrialReport:
    trial_id = text(summary, "trial_id")
    document = read_object(run / "trials" / trial_id / "result.json", "trial result")
    require(document.get("schema_version") == 1, f"trial {trial_id} has an invalid schema")
    require(document.get("trial_id") == trial_id, f"trial result ID mismatch: {trial_id}")
    require(document.get("status") == summary.get("status"), f"trial status mismatch: {trial_id}")
    manifest = load_manifest(run, trial_id)
    warnings.extend(artifact_warnings(manifest, trial_id))
    status = _status(document.get("status"), trial_id)
    benchmarks = document.get("benchmarks", [])
    artifacts = document.get("artifacts", {})
    actual_execution = execution(document.get("execution"), trial_id)
    for source, value in (("run summary", summary.get("execution")), ("manifest", manifest.get("execution"))):
        if value is not None:
            require(
                actual_execution == execution(value, trial_id), f"trial execution mismatch with {source}: {trial_id}"
            )
    require(isinstance(benchmarks, list), f"trial {trial_id} has invalid benchmarks")
    require(isinstance(artifacts, Mapping), f"trial {trial_id} has invalid artifacts")
    attempts = document.get("attempts", [])
    require(
        isinstance(attempts, list) and all(isinstance(item, Mapping) for item in attempts),
        f"trial {trial_id} has invalid attempts",
    )
    return TrialReport(
        1,
        trial_id,
        status,
        tuple(cast(list[Mapping[str, object]], benchmarks)),
        {str(k): str(v) for k, v in cast(Mapping[str, object], artifacts).items()},
        tuple(_attempt(item) for item in cast(list[Mapping[str, object]], attempts)),
        _failure(document.get("failure")),
        actual_execution,
    )


def read_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {label} '{path}': {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _attempt(value: Mapping[str, object]) -> AttemptReport:
    index = value.get("index")
    require(isinstance(index, int), "trial attempt has an invalid index")
    artifacts = mapping(value, "artifacts")
    return AttemptReport(
        cast(int, index),
        _status(value.get("status"), f"attempt {index}"),
        {str(k): str(v) for k, v in artifacts.items()},
        _failure(value.get("failure")),
    )


def _failure(value: object) -> Failure | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("stored failure is invalid")
    return Failure(text(value, "code"), text(value, "message"), bool(value.get("retryable", False)))


def _status(value: object, owner: str) -> WorkerStatus:
    if not isinstance(value, str):
        raise ValueError(f"{owner} has invalid status: {value}")
    try:
        return WorkerStatus(value)
    except ValueError as error:
        raise ValueError(f"{owner} has invalid status: {value}") from error
