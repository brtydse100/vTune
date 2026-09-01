"""Production GuideLLM benchmark worker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from time import monotonic

from vllm_optimizer.benchmarks.guidellm import build_plan, parse_result
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import logging_level
from vllm_optimizer.domain.results import Failure, WorkerResult
from vllm_optimizer.reproduction.models import CommandRecord
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.attempts import attempt_directory
from vllm_optimizer.workers.completion import (
    completed_requests as _completed_requests, max_requests as _max_requests,
    request_count_failure as _request_count_failure,
)
from vllm_optimizer.workers.failure_details import classified_failure
from vllm_optimizer.workers.process import ManagedProcess, ProcessRunner, ProcessSpec


class GuideLLMBenchmarkWorker:
    def __init__(
        self, config: VTuneConfig, run: Mapping[str, object], runner: ProcessRunner,
        artifacts: Path, timeout: float = 180, shutdown_grace: float = 5,
        repeat_index: int | None = None, warmup_index: int | None = None,
    ) -> None:
        if timeout <= 0 or shutdown_grace < 0:
            raise ValueError("benchmark timeout must be positive and grace non-negative")
        self._config, self._run, self._runner = config, run, runner
        if repeat_index is not None and warmup_index is not None:
            raise ValueError("benchmark repeat and warmup cannot both be set")
        self._artifacts, self._timeout = Path(artifacts), timeout
        self._shutdown_grace = shutdown_grace
        self._run_name = str(run.get("name", "invalid"))
        self._repeat_index = repeat_index
        self._warmup_index = warmup_index

    @property
    def name(self) -> str:
        suffix = (f":warmup-{self._warmup_index}" if self._warmup_index
                  else f":repeat-{self._repeat_index}" if self._repeat_index else "")
        return f"guidellm_benchmark:{self._run_name}{suffix}"

    @property
    def _ownership_key(self) -> str:
        phase = f"warmup-{self._warmup_index}" if self._warmup_index else f"repeat-{self._repeat_index or 'single'}"
        return f"_guidellm_owned_process_{self._run_name}_{phase}"

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        endpoint = context.values.get("server_endpoint")
        if not isinstance(endpoint, str):
            return self._failed("benchmark_endpoint_missing", "Missing server endpoint")
        try:
            artifacts = attempt_directory(self._artifacts, context)
            if self._warmup_index:
                artifacts = artifacts / "warmups" / f"{self._warmup_index:03d}"
            elif self._repeat_index:
                artifacts = artifacts / "repeats" / f"{self._repeat_index:03d}"
            plan = build_plan(self._config, self._run, endpoint, artifacts)
            plan.directory.mkdir(parents=True, exist_ok=True)
            context.commands.append(CommandRecord(
                "guidellm", plan.argv, int(context.values.get("attempt_index", 1)),
                self._environment(), plan.run_name, self._repeat_index,
            ))
            started = monotonic()
            process = await self._runner.start(
                ProcessSpec(plan.argv, env=self._environment()), plan.log_path
            )
        except FileNotFoundError:
            return self._failed(
                "guidellm_not_found",
                "The 'guidellm' command was not found. On Linux or WSL, "
                "install runtime tools with: pip install 'vllm-optimizer[runtime]'",
            )
        except Exception as error:
            return self._failed("benchmark_launch_failed", str(error))
        context.values[self._ownership_key] = process
        suffix = (f"_warmup_{self._warmup_index}" if self._warmup_index
                  else f"_repeat_{self._repeat_index}" if self._repeat_index else "")
        prefix = f"benchmark_{plan.run_name}{suffix}"
        context.artifacts[f"{prefix}_log"] = str(plan.log_path)
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=self._timeout)
        except TimeoutError:
            await process.stop(self._shutdown_grace)
            return WorkerResult.failed(
                classified_failure(plan.log_path, "benchmark_timeout",
                                   f"GuideLLM benchmark '{plan.run_name}' timed out after "
                                   f"{self._timeout:g}s and was stopped; full log: "
                                   f"{plan.log_path}", True)
            )
        if returncode:
            return WorkerResult.failed(classified_failure(
                plan.log_path, "benchmark_failed", f"GuideLLM exited with code {returncode}"
            ))
        try:
            result = replace(
                parse_result(plan.json_path, plan.run_name),
                repeat_index=self._repeat_index,
                elapsed_seconds=monotonic() - started,
            )
        except ValueError as error:
            return WorkerResult.failed(classified_failure(
                plan.log_path, "benchmark_result_invalid", str(error)
            ))
        has_request_limit, expected_requests = _max_requests(self._run)
        if has_request_limit:
            failure = _request_count_failure(result, expected_requests)
            if failure is not None:
                return WorkerResult.failed(failure)
        elif not _completed_requests(result):
            return WorkerResult.failed(Failure(
                "benchmark_no_completed_requests",
                f"GuideLLM exited without completed requests for '{plan.run_name}'; "
                f"vLLM may still have pending work. Inspect benchmark log: {plan.log_path}",
            ))
        previous = context.values.get("benchmark_results", ())
        if self._warmup_index is None:
            context.values["benchmark_results"] = (*previous, result)
        context.artifacts[f"{prefix}_json"] = str(plan.json_path)
        return WorkerResult.completed()

    async def cleanup(self, context: TrialContext) -> None:
        process = context.values.pop(self._ownership_key, None)
        if isinstance(process, ManagedProcess):
            await process.stop(self._shutdown_grace)

    def _environment(self) -> dict[str, str]:
        environment = {key: str(value) for key, value in self._config.env.items()}
        environment["GUIDELLM__LOGGING__CONSOLE_LOG_LEVEL"] = logging_level(self._config)
        return environment

    @staticmethod
    def _failed(code: str, message: str) -> WorkerResult[None]:
        return WorkerResult.failed(Failure(code, message))
