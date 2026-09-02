"""Production vLLM Bench Serve worker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from time import monotonic

from vllm_optimizer.benchmarks.vllm import build_plan, parse_result
from vllm_optimizer.benchmarks.configuration import configured_failure_percentage
from vllm_optimizer.benchmarks.failures import save_failed_requests
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.domain.results import Failure, WorkerResult
from vllm_optimizer.reproduction.models import CommandRecord
from vllm_optimizer.workers.attempts import attempt_directory
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.completion import (
    observed_requests, reported_request_total, request_count_failure,
)
from vllm_optimizer.workers.failure_details import classified_failure
from vllm_optimizer.workers.process import ManagedProcess, ProcessRunner, ProcessSpec
from vllm_optimizer.workers.progress import BenchmarkProgress, ProgressCallback


class VLLMBenchmarkWorker:
    def __init__(
        self, config: VTuneConfig, run: Mapping[str, object], runner: ProcessRunner,
        artifacts: Path, timeout: float = 180, shutdown_grace: float = 5,
        repeat_index: int | None = None, warmup_index: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        if timeout <= 0 or shutdown_grace < 0:
            raise ValueError("benchmark timeout must be positive and grace non-negative")
        if repeat_index is not None and warmup_index is not None:
            raise ValueError("benchmark repeat and warmup cannot both be set")
        self._config, self._run, self._runner = config, run, runner
        self._artifacts, self._timeout = Path(artifacts), timeout
        self._shutdown_grace = shutdown_grace
        self._run_name = str(run.get("name", "invalid"))
        self._repeat_index = repeat_index
        self._warmup_index = warmup_index
        self._progress = progress

    @property
    def name(self) -> str:
        suffix = (f":warmup-{self._warmup_index}" if self._warmup_index
                  else f":repeat-{self._repeat_index}" if self._repeat_index else "")
        return f"vllm_benchmark:{self._run_name}{suffix}"

    @property
    def _ownership_key(self) -> str:
        phase = f"warmup-{self._warmup_index}" if self._warmup_index else f"repeat-{self._repeat_index or 'single'}"
        return f"_vllm_bench_owned_process_{self._run_name}_{phase}"

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
                "vllm_bench_serve", plan.argv,
                int(context.values.get("attempt_index", 1)), self._environment(),
                plan.run_name, self._repeat_index,
            ))
            started = monotonic()
            progress = BenchmarkProgress("vllm", self._run, self.name, self._progress)
            await progress.prepare(endpoint)
            process = await self._runner.start(
                ProcessSpec(plan.argv, env=self._environment()), plan.log_path
            )
        except FileNotFoundError:
            return self._failed(
                "vllm_not_found", "The 'vllm' command was not found. On Linux or WSL, "
                "install runtime tools with: pip install 'vllm-optimizer[runtime]'",
            )
        except Exception as error:
            return self._failed("benchmark_launch_failed", str(error))
        context.values[self._ownership_key] = process
        progress.start(process)
        suffix = (f"_warmup_{self._warmup_index}" if self._warmup_index
                  else f"_repeat_{self._repeat_index}" if self._repeat_index else "")
        prefix = f"benchmark_{plan.run_name}{suffix}"
        context.artifacts[f"{prefix}_log"] = str(plan.log_path)
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=self._timeout)
        except TimeoutError:
            await process.stop(self._shutdown_grace)
            return WorkerResult.failed(classified_failure(
                plan.log_path, "benchmark_timeout",
                f"vLLM benchmark '{plan.run_name}' timed out after {self._timeout:g}s "
                f"and was stopped; full log: {plan.log_path}", True,
            ))
        finally:
            await progress.stop()
        if returncode:
            return WorkerResult.failed(classified_failure(
                plan.log_path, "benchmark_failed", f"vLLM bench serve exited with code {returncode}"
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
        progress.complete(process, observed_requests(result))
        failed_path = plan.directory / "failed_requests.json"
        if save_failed_requests(plan.json_path, "vllm", failed_path):
            context.artifacts[f"{prefix}_failed_requests"] = str(failed_path)
        context.artifacts[f"{prefix}_json"] = str(plan.json_path)
        failure = request_count_failure(
            result, reported_request_total(result), "vLLM Bench Serve",
            configured_failure_percentage(self._config),
        )
        if failure is not None:
            if self._warmup_index is None:
                previous = context.values.get("observed_benchmark_results", ())
                context.values["observed_benchmark_results"] = (*previous, result)
            return WorkerResult.failed(failure)
        previous = context.values.get("benchmark_results", ())
        if self._warmup_index is None:
            context.values["benchmark_results"] = (*previous, result)
        return WorkerResult.completed()

    async def cleanup(self, context: TrialContext) -> None:
        process = context.values.pop(self._ownership_key, None)
        if isinstance(process, ManagedProcess):
            await process.stop(self._shutdown_grace)

    def _environment(self) -> dict[str, str]:
        return {**{key: str(value) for key, value in self._config.env.items()},
                "PYTHONUNBUFFERED": "1"}

    @staticmethod
    def _failed(code: str, message: str) -> WorkerResult[None]:
        return WorkerResult.failed(Failure(code, message))
