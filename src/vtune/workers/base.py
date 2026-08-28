"""Shared contracts for execution-stage workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from vtune.domain.results import WorkerResult


@dataclass(slots=True)
class TrialContext:
    """Mutable data passed between workers for one trial attempt."""

    trial_id: str
    values: dict[str, object] = field(default_factory=dict)
    artifacts: dict[str, object] = field(default_factory=dict)


class Worker(Protocol):
    """One focused stage in a trial execution pipeline."""

    name: str

    async def execute(self, context: TrialContext) -> WorkerResult[None]: ...

    async def cleanup(self, context: TrialContext) -> None: ...
