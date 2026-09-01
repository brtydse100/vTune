"""Production GuideLLM benchmark worker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from time import monotonic

from vtune.benchmarks.guidellm import build_plan, parse_result
from vtune.config.models import VTuneConfig
from vtune.config.runtime import logging_level
from vtune.domain.results import Failure, WorkerResult
from vtune.reproduction.models import CommandRecord
from vtune.workers.base import TrialContext
from vtune.workers.attempts import attempt_directory
from vtune.workers.failure_details import classified_failure
from vtune.workers.process import ManagedProcess, ProcessRunner, ProcessSpec


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
                "install runtime tools with: pip install 'vtune[runtime]'",
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


def _completed_requests(result: object) -> bool:
    workloads = getattr(result, "workloads", ())
    for workload in workloads:
        metrics = getattr(workload, "metrics", {})
        totals = metrics.get("request_totals", {}) if isinstance(metrics, Mapping) else {}
        if not isinstance(totals, Mapping) or "successful" not in totals:
            return True
        if isinstance(totals.get("successful"), int) and totals["successful"] > 0:
            return True
    return False


def _max_requests(run: Mapping[str, object]) -> tuple[bool, int | None]:
    constraints = run.get("constraints", [])
    if not isinstance(constraints, list):
        return False, None
    for constraint in constraints:
        if isinstance(constraint, Mapping) and constraint.get("kind") == "max_requests":
            count = constraint.get("count")
            valid = (isinstance(count, int) and not isinstance(count, bool) and count > 0)
            return True, count if valid else None
    return False, None


def _request_count_failure(result: object, expected: int | None) -> Failure | None:
    if expected is None:
        return Failure(
            "benchmark_request_total_missing",
            "GuideLLM request-count benchmark is missing a positive max_requests count",
        )
    workloads = getattr(result, "workloads", ())
    if not workloads:
        return Failure(
            "benchmark_request_total_missing",
            "GuideLLM result contains no workload metrics; the benchmark cannot be scored safely",
        )
    for workload in workloads:
        metrics = getattr(workload, "metrics", {})
        totals = metrics.get("request_totals") if isinstance(metrics, Mapping) else None
        request_total = metrics.get("request_total") if isinstance(metrics, Mapping) else None
        if (not isinstance(totals, Mapping)
                or not isinstance(request_total, int)
                or isinstance(request_total, bool)):
            return Failure(
                "benchmark_request_total_missing",
                "GuideLLM result is missing the normalized request total; "
                "the benchmark cannot be scored safely",
            )
        successful = totals.get("successful")
        errored = totals.get("errored")
        incomplete = totals.get("incomplete")
        if not all(isinstance(value, int) and not isinstance(value, bool)
                   for value in (successful, errored, incomplete)):
            return Failure(
                "benchmark_request_totals_invalid",
                "GuideLLM result has invalid normalized request totals",
            )
        observed = successful + errored + incomplete
        if (request_total != expected or observed != expected or errored or incomplete
                or successful != expected):
            return Failure(
                "benchmark_requests_incomplete",
                f"GuideLLM request-count benchmark expected {expected} successful requests; "
                f"observed {successful} successful, {errored} errored, "
                f"{incomplete} incomplete, total {request_total}",
            )
    return None
