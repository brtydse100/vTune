import asyncio

from vllm_optimizer.domain.results import Failure, WorkerResult, WorkerStatus
from vllm_optimizer.managers.trial import TrialManager
from vllm_optimizer.workers.base import TrialContext


class _Worker:
    def __init__(self, name: str, results: list[WorkerResult[None]], cleanup_error: bool = False) -> None:
        self.name, self.results, self.cleanup_error = name, results, cleanup_error
        self.cleaned = 0

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        return self.results.pop(0)

    async def cleanup(self, context: TrialContext) -> None:
        self.cleaned += 1
        if self.cleanup_error:
            raise RuntimeError("cleanup sentinel")


def test_transient_failure_retries_and_cleans_each_attempt() -> None:
    worker = _Worker("retry", [WorkerResult.failed(Failure("temporary", "try again", True)), WorkerResult.completed()])
    events = []
    context = TrialContext("trial")

    outcome = asyncio.run(TrialManager((worker,), 2, lambda *event: events.append(event)).execute(context))

    assert outcome.status is WorkerStatus.COMPLETED
    assert [attempt.status for attempt in context.attempts] == [WorkerStatus.FAILED, WorkerStatus.COMPLETED]
    assert worker.cleaned == 2
    assert ("completed", "cleanup") in events


def test_permanent_failure_stops_and_cleanup_failure_is_reported() -> None:
    failed = _Worker("failed", [WorkerResult.failed(Failure("permanent", "stop"))])
    outcome = asyncio.run(TrialManager((failed,), 3).execute(TrialContext("trial")))
    assert outcome.failure and outcome.failure.code == "permanent"
    assert failed.cleaned == 1

    cleanup = _Worker("cleanup", [WorkerResult.completed()], cleanup_error=True)
    outcome = asyncio.run(TrialManager((cleanup,)).execute(TrialContext("trial")))
    assert outcome.failure and outcome.failure.code == "cleanup_failed"


def test_worker_exception_and_interruption_are_classified() -> None:
    class Raising(_Worker):
        async def execute(self, context: TrialContext) -> WorkerResult[None]:
            raise RuntimeError("worker sentinel")

    outcome = asyncio.run(TrialManager((Raising("boom", []),)).execute(TrialContext("trial")))
    assert outcome.failure and outcome.failure.code == "worker_execution_error"

    interrupted = _Worker("interrupt", [WorkerResult.interrupted("stop")])
    outcome = asyncio.run(TrialManager((interrupted,)).execute(TrialContext("trial")))
    assert outcome.status is WorkerStatus.INTERRUPTED
