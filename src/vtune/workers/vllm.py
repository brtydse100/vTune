"""Worker that starts and owns a vLLM server process."""

from __future__ import annotations

from pathlib import Path
from time import monotonic

from vtune.domain.results import Failure, WorkerResult
from vtune.reproduction.models import CommandRecord
from vtune.workers.base import TrialContext
from vtune.workers.attempts import attempt_path
from vtune.workers.process import ManagedProcess, ProcessRunner, ProcessSpec


class VLLMRunnerWorker:
    """Start the configured process and stop only the process it started."""

    name = "vllm_runner"
    _ownership_key = "_vllm_runner_owned_process"

    def __init__(
        self,
        runner: ProcessRunner,
        log_path: Path,
        shutdown_grace: float = 5.0,
    ) -> None:
        if shutdown_grace < 0:
            raise ValueError("shutdown_grace must not be negative")
        self._runner = runner
        self._log_path = log_path
        self._shutdown_grace = shutdown_grace

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        spec = context.values.get("process_spec")
        if not isinstance(spec, ProcessSpec):
            return WorkerResult.failed(
                Failure(
                    code="server_launch_failed",
                    message="Trial context does not contain a valid process specification",
                )
            )

        try:
            log_path = attempt_path(self._log_path, context)
            context.commands.append(CommandRecord(
                "vllm", spec.argv, int(context.values.get("attempt_index", 1)), spec.env,
            ))
            context.values["vllm_started_at"] = monotonic()
            process = await self._runner.start(spec, log_path)
        except Exception as error:
            return WorkerResult.failed(
                Failure(
                    code="server_launch_failed",
                    message=f"Unable to start vLLM: {error}",
                )
            )

        context.values["server_process"] = process
        context.values[self._ownership_key] = process
        context.artifacts["vllm_log"] = str(log_path)
        return WorkerResult.completed()

    async def cleanup(self, context: TrialContext) -> None:
        process = context.values.get("server_process")
        owned = context.values.pop(self._ownership_key, None)
        if process is owned and isinstance(process, ManagedProcess):
            await process.stop(self._shutdown_grace)
