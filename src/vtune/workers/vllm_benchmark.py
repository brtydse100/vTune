"""Production vLLM Bench Serve worker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from time import monotonic

from vtune.benchmarks.vllm import build_plan, parse_result
from vtune.config.models import VTuneConfig
from vtune.domain.results import Failure, WorkerResult
from vtune.reproduction.models import CommandRecord
from vtune.workers.attempts import attempt_directory
from vtune.workers.base import TrialContext
from vtune.workers.failure_details import classified_failure
from vtune.workers.process import ManagedProcess, ProcessRunner, ProcessSpec


class VLLMBenchmarkWorker:
    def __init__(
        self, config: VTuneConfig, run: Mapping[str, object], runner: ProcessRunner,
        artifacts: Path, timeout: float = 180, shutdown_grace: float = 5,
        repeat_index: int | None = None,
    ) -> None:
        if timeout <= 0 or shutdown_grace < 0:
            raise ValueError("benchmark timeout must be positive and grace non-negative")
        self._config, self._run, self._runner = config, run, runner
        self._artifacts, self._timeout = Path(artifacts), timeout
        self._shutdown_grace = shutdown_grace
        self._run_name = str(run.get("name", "invalid"))
        self._repeat_index = repeat_index

    @property
    def name(self) -> str:
        suffix = f":repeat-{self._repeat_index}" if self._repeat_index else ""
        return f"vllm_benchmark:{self._run_name}{suffix}"

    @property
    def _ownership_key(self) -> str:
        return f"_vllm_bench_owned_process_{self._run_name}_{self._repeat_index or 'single'}"

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        endpoint = context.values.get("server_endpoint")
        if not isinstance(endpoint, str):
            return self._failed("benchmark_endpoint_missing", "Missing server endpoint")
        try:
            artifacts = attempt_directory(self._artifacts, context)
            if self._repeat_index:
                artifacts = artifacts / "repeats" / f"{self._repeat_index:03d}"
            plan = build_plan(self._config, self._run, endpoint, artifacts)
            plan.directory.mkdir(parents=True, exist_ok=True)
            context.commands.append(CommandRecord(
                "vllm_bench_serve", plan.argv,
                int(context.values.get("attempt_index", 1)), self._environment(),
                plan.run_name, self._repeat_index,
            ))
            started = monotonic()
            process = await self._runner.start(
                ProcessSpec(plan.argv, env=self._environment()), plan.log_path
            )
        except FileNotFoundError:
            return self._failed(
                "vllm_not_found", "The 'vllm' command was not found. On Linux or WSL, "
                "install runtime tools with: pip install 'vtune[runtime]'",
            )
        except Exception as error:
            return self._failed("benchmark_launch_failed", str(error))
        context.values[self._ownership_key] = process
        prefix = f"benchmark_{plan.run_name}" + (f"_repeat_{self._repeat_index}" if self._repeat_index else "")
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
        previous = context.values.get("benchmark_results", ())
        context.values["benchmark_results"] = (*previous, result)
        context.artifacts[f"{prefix}_json"] = str(plan.json_path)
        return WorkerResult.completed()

    async def cleanup(self, context: TrialContext) -> None:
        process = context.values.pop(self._ownership_key, None)
        if isinstance(process, ManagedProcess):
            await process.stop(self._shutdown_grace)

    def _environment(self) -> dict[str, str]:
        return {key: str(value) for key, value in self._config.env.items()}

    @staticmethod
    def _failed(code: str, message: str) -> WorkerResult[None]:
        return WorkerResult.failed(Failure(code, message))
