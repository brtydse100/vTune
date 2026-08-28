"""Result types shared by execution workers and their managers."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


class WorkerStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("failure code must not be empty")
        if not self.message or not self.message.strip():
            raise ValueError("failure message must not be empty")


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class WorkerResult(Generic[T]):
    status: WorkerStatus
    value: T | None = None
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if self.status is WorkerStatus.COMPLETED:
            if self.failure is not None:
                raise ValueError("completed results must not contain a failure")
            return
        if self.value is not None or self.failure is None:
            raise ValueError("failed or interrupted results require only a failure")

    @classmethod
    def completed(cls, value: T | None = None) -> "WorkerResult[T]":
        return cls(status=WorkerStatus.COMPLETED, value=value)

    @classmethod
    def failed(cls, failure: Failure) -> "WorkerResult[T]":
        return cls(status=WorkerStatus.FAILED, failure=failure)

    @classmethod
    def interrupted(
        cls, message: str = "Worker execution was interrupted"
    ) -> "WorkerResult[T]":
        return cls(
            status=WorkerStatus.INTERRUPTED,
            failure=Failure(code="interrupted", message=message),
        )
