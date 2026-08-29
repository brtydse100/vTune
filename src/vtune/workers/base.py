"""Shared contracts for execution-stage workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from vtune.domain.results import WorkerResult
from vtune.domain.attempt_report import AttemptReport
from vtune.reproduction.models import CommandRecord, StartupRecord


@dataclass(slots=True)
class TrialContext:
    """Mutable data passed between workers for one trial attempt."""

    trial_id: str
    values: dict[str, object] = field(default_factory=dict)
    artifacts: dict[str, object] = field(default_factory=dict)
    attempts: list[AttemptReport] = field(default_factory=list)
    commands: list[CommandRecord] = field(default_factory=list)
    startups: list[StartupRecord] = field(default_factory=list)


class Worker(Protocol):
    """One focused stage in a trial execution pipeline."""

    name: str

    async def execute(self, context: TrialContext) -> WorkerResult[None]: ...

    async def cleanup(self, context: TrialContext) -> None: ...
