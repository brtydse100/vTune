"""Coordination of the workers that execute one trial attempt."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from vtune.domain.results import Failure, WorkerResult, WorkerStatus
from vtune.workers.base import TrialContext, Worker


class TrialManager:
    """Execute workers in order and guarantee reverse-order cleanup."""

    def __init__(self, workers: Sequence[Worker]) -> None:
        self._workers = tuple(workers)

    async def execute(self, context: TrialContext) -> WorkerResult[TrialContext]:
        started: list[Worker] = []
        outcome: WorkerResult[TrialContext] = WorkerResult.completed(context)

        try:
            for worker in self._workers:
                started.append(worker)
                result = await worker.execute(context)
                if result.status is WorkerStatus.FAILED:
                    outcome = WorkerResult.failed(self._failure_from(result, worker))
                    break
                if result.status is WorkerStatus.INTERRUPTED:
                    outcome = WorkerResult.interrupted(
                        self._interruption_message(result, worker)
                    )
                    break
        except asyncio.CancelledError:
            outcome = WorkerResult.interrupted("Trial execution was interrupted")
        except Exception as error:
            worker_name = started[-1].name if started else "unknown"
            outcome = WorkerResult.failed(
                Failure(
                    code="worker_execution_error",
                    message=f"Worker '{worker_name}' raised: {error}",
                )
            )

        cleanup_errors = await self._cleanup(started, context)
        if cleanup_errors and outcome.status is WorkerStatus.COMPLETED:
            return WorkerResult.failed(
                Failure(code="cleanup_failed", message="; ".join(cleanup_errors))
            )
        return outcome

    async def _cleanup(
        self, workers: list[Worker], context: TrialContext
    ) -> list[str]:
        errors: list[str] = []
        for worker in reversed(workers):
            try:
                await worker.cleanup(context)
            except Exception as error:
                errors.append(f"Cleanup for worker '{worker.name}' failed: {error}")
        return errors

    @staticmethod
    def _failure_from(result: WorkerResult[None], worker: Worker) -> Failure:
        return result.failure or Failure(
            code="worker_failed",
            message=f"Worker '{worker.name}' failed without failure details",
        )

    @staticmethod
    def _interruption_message(result: WorkerResult[None], worker: Worker) -> str:
        if result.failure:
            return result.failure.message
        return f"Worker '{worker.name}' was interrupted"
