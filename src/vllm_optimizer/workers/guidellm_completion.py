"""Validate GuideLLM request completion evidence."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vllm_optimizer.benchmarks.configuration import configured_failure_percentage
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.domain.benchmark import BenchmarkResult
from vllm_optimizer.domain.results import Failure
from vllm_optimizer.workers.completion import completed_requests, max_requests, request_count_failure


def completion_failure(
    config: VTuneConfig, run: Mapping[str, object], result: BenchmarkResult, run_name: str, log_path: Path
) -> Failure | None:
    has_limit, expected = max_requests(run)
    if has_limit:
        return request_count_failure(result, expected, max_failure_percentage=configured_failure_percentage(config))
    if completed_requests(result):
        return None
    return Failure(
        "benchmark_no_completed_requests",
        f"GuideLLM exited without completed requests for '{run_name}'; "
        f"vLLM may still have pending work. Inspect benchmark log: {log_path}",
    )
