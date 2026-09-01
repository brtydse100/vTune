"""Complete, side-effect-free validation for a runnable configuration."""

from __future__ import annotations

from pathlib import Path

from vtune.benchmarks.configuration import (
    configured_engine, configured_min_repeats, configured_repeats,
    configured_runs, configured_warmup_repeats,
)
from vtune.benchmarks.guidellm import build_plan as build_guidellm_plan
from vtune.benchmarks.timing import timeout_for_run
from vtune.benchmarks.vllm import build_plan as build_vllm_plan
from vtune.config.errors import ConfigValidationError
from vtune.config.models import VTuneConfig
from vtune.config.runtime import (
    baseline_enabled, duration, max_attempts, maximize_metric, positive, server_port,
)
from vtune.execution.slots import WorkerSlot, worker_slots
from vtune.reporting.llm_summary import settings as llm_settings
from vtune.search.grid import TrialParameters, expand_grid
from vtune.search.factory import validate_search
from vtune.workers.configuration import build_process_spec


_EXECUTION_KEYS = {
    "mode", "max_parallel_trials", "gpu_allocation", "ports", "host",
    "health_path", "shutdown_grace", "drain_grace", "retry",
}


def validate_config(config: VTuneConfig) -> None:
    """Validate every value that can be checked before a run starts."""
    try:
        _validate(config)
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(f"Invalid configuration: {error}") from error


def _validate(config: VTuneConfig) -> None:
    unknown = set(config.execution) - _EXECUTION_KEYS
    if unknown:
        raise ValueError(f"unknown execution setting(s): {', '.join(sorted(unknown))}")
    if set(config.timeouts) - {"startup", "benchmark"}:
        raise ValueError("timeouts supports only startup and benchmark")
    host = config.execution.get("host", "127.0.0.1")
    path = config.execution.get("health_path", "/health")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("execution.host must be a non-empty string")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("execution.health_path must be a non-empty string")

    runs = configured_runs(config)
    configured_repeats(config)
    configured_min_repeats(config)
    configured_warmup_repeats(config)
    maximize_metric(config)
    validate_search(config)
    port = server_port(config)
    baseline_enabled(config)
    llm_settings(config)
    max_attempts(config)
    duration(config.timeouts, "startup", 900)
    positive(config.execution, "shutdown_grace", 15)
    positive(config.execution, "drain_grace", 15)

    slots = worker_slots(config)
    trials = expand_grid(config)
    _validate_process(config, TrialParameters("baseline", {}, {}), slots)
    for trial in trials:
        _validate_process(config, trial, slots)

    endpoint_port = slots[0].port if slots else port
    endpoint = f"http://{host}:{endpoint_port}"
    builder = build_guidellm_plan if configured_engine(config) == "guidellm" else build_vllm_plan
    for run in runs:
        timeout_for_run(run, config.timeouts.get("benchmark"))
        builder(config, run, endpoint, Path("."))


def _validate_process(
    config: VTuneConfig, trial: TrialParameters, slots: tuple[WorkerSlot, ...],
) -> None:
    slot = next((candidate for candidate in slots
                 if candidate.supports(trial.server_args, config.server)), None)
    if slots and slot is None:
        raise ValueError("a trial tensor-parallel-size exceeds every parallel worker")
    runtime_args = {"port": slot.port} if slot else None
    runtime_env = ({"CUDA_VISIBLE_DEVICES": ",".join(map(str, slot.devices))}
                   if slot else None)
    build_process_spec(
        config, trial.server_args, trial.server_env, runtime_args, runtime_env,
    )
