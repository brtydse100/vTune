"""Persisted outcome for one trial execution attempt."""

from collections.abc import Mapping
from dataclasses import dataclass

from vllm_optimizer.domain.results import Failure, WorkerStatus


@dataclass(frozen=True, slots=True)
class AttemptReport:
    index: int
    status: WorkerStatus
    artifacts: Mapping[str, str]
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError("attempt index must start at one")
