"""Persisted, backend-neutral result for one trial execution."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from vtune.domain.results import Failure, WorkerStatus
from vtune.domain.attempt_report import AttemptReport


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class TrialReport:
    schema_version: int
    trial_id: str
    status: WorkerStatus
    benchmarks: tuple[Mapping[str, object], ...]
    artifacts: Mapping[str, str]
    attempts: tuple[AttemptReport, ...] = ()
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if self.schema_version < 1 or not self.trial_id.strip():
            raise ValueError("report schema version and trial ID must be valid")
        if self.status is WorkerStatus.COMPLETED and self.failure is not None:
            raise ValueError("a completed trial report cannot contain a failure")
        if self.status is not WorkerStatus.COMPLETED and self.failure is None:
            raise ValueError("an unsuccessful trial report requires a failure")
        object.__setattr__(self, "benchmarks", tuple(_freeze(self.benchmarks)))
        object.__setattr__(self, "artifacts", _freeze(self.artifacts))
        object.__setattr__(self, "attempts", tuple(self.attempts))

    def to_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": self.schema_version, "trial_id": self.trial_id,
            "status": self.status.value, "benchmarks": _plain(self.benchmarks),
            "artifacts": _plain(self.artifacts),
            "attempts": [_attempt_dict(attempt) for attempt in self.attempts],
        }
        if self.failure:
            document["failure"] = {"code": self.failure.code,
                                   "message": self.failure.message,
                                   "retryable": self.failure.retryable}
        return document


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _attempt_dict(attempt: AttemptReport) -> dict[str, object]:
    failure = None
    if attempt.failure:
        failure = {"code": attempt.failure.code, "message": attempt.failure.message,
                   "retryable": attempt.failure.retryable}
    return {"index": attempt.index, "status": attempt.status.value,
            "artifacts": dict(attempt.artifacts), "failure": failure}
