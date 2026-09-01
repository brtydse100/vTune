"""Coordination and retry attempts for one resolved trial."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from vllm_optimizer.domain.attempt_report import AttemptReport
from vllm_optimizer.domain.results import Failure, WorkerResult, WorkerStatus
from vllm_optimizer.workers.base import TrialContext, Worker


class TrialManager:
    """Execute workers, guarantee cleanup, and retry transient failures."""

    def __init__(
        self, workers: Sequence[Worker], max_attempts: int = 1,
        progress: Callable[[str, str], None] | None = None,
    ) -> None:
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self._workers = tuple(workers)
        self._max_attempts = max_attempts
        self._progress = progress or (lambda event, name: None)

    async def execute(self, context: TrialContext) -> WorkerResult[TrialContext]:
        outcome: WorkerResult[TrialContext] = WorkerResult.completed(context)
        base_values = dict(context.values)
        for index in range(1, self._max_attempts + 1):
            self._prepare_attempt(context, index, base_values)
            outcome = await self._execute_once(context)
            context.attempts.append(
                AttemptReport(index, outcome.status,
                              {key: str(value) for key, value in context.artifacts.items()},
                              outcome.failure)
            )
            if not self._should_retry(outcome, index):
                break
        context.values.pop("attempt_index", None)
        return outcome

    async def _execute_once(self, context: TrialContext) -> WorkerResult[TrialContext]:
        started: list[Worker] = []
        outcome: WorkerResult[TrialContext] = WorkerResult.completed(context)
        try:
            for worker in self._workers:
                started.append(worker)
                self._progress("starting", worker.name)
                result = await worker.execute(context)
                if result.status is WorkerStatus.FAILED:
                    self._progress("failed", worker.name)
                    outcome = WorkerResult.failed(self._failure_from(result, worker))
                    break
                if result.status is WorkerStatus.INTERRUPTED:
                    outcome = WorkerResult.interrupted(
                        self._interruption_message(result, worker)
                    )
                    break
                self._progress("completed", worker.name)
        except asyncio.CancelledError:
            outcome = WorkerResult.interrupted("Trial execution was interrupted")
        except Exception as error:
            name = started[-1].name if started else "unknown"
            outcome = WorkerResult.failed(
                Failure("worker_execution_error", f"Worker '{name}' raised: {error}")
            )
        cleanup_errors = await self._cleanup(started, context)
        if cleanup_errors and outcome.status is WorkerStatus.COMPLETED:
            return WorkerResult.failed(Failure("cleanup_failed", "; ".join(cleanup_errors)))
        return outcome

    async def _cleanup(self, workers: list[Worker], context: TrialContext) -> list[str]:
        errors = []
        self._progress("starting", "cleanup")
        for worker in reversed(workers):
            try:
                await worker.cleanup(context)
            except Exception as error:
                errors.append(f"Cleanup for worker '{worker.name}' failed: {error}")
        self._progress("failed" if errors else "completed", "cleanup")
        return errors

    @staticmethod
    def _prepare_attempt(
        context: TrialContext, index: int, base_values: dict[str, object]
    ) -> None:
        context.values = {**base_values, "attempt_index": index}
        context.artifacts = {}

    def _should_retry(self, outcome: WorkerResult[TrialContext], index: int) -> bool:
        return bool(
            index < self._max_attempts
            and outcome.status is WorkerStatus.FAILED
            and outcome.failure
            and outcome.failure.retryable
        )

    @staticmethod
    def _failure_from(result: WorkerResult[None], worker: Worker) -> Failure:
        return result.failure or Failure(
            "worker_failed", f"Worker '{worker.name}' failed without failure details"
        )

    @staticmethod
    def _interruption_message(result: WorkerResult[None], worker: Worker) -> str:
        return result.failure.message if result.failure else f"Worker '{worker.name}' was interrupted"
