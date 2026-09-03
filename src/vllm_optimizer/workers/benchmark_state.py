"""Shared benchmark naming and trial-context state helpers."""

from __future__ import annotations

from pathlib import Path

from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import logging_level
from vllm_optimizer.domain.results import Failure, WorkerResult
from vllm_optimizer.reproduction.models import CommandRecord
from vllm_optimizer.workers.attempts import attempt_directory
from vllm_optimizer.workers.base import TrialContext


def worker_name(engine: str, run_name: str, repeat: int | None, warmup: int | None) -> str:
    suffix = f":warmup-{warmup}" if warmup else f":repeat-{repeat}" if repeat else ""
    return f"{engine}_benchmark:{run_name}{suffix}"


def ownership_key(engine: str, run_name: str, repeat: int | None, warmup: int | None) -> str:
    phase = f"warmup-{warmup}" if warmup else f"repeat-{repeat or 'single'}"
    prefix = "_vllm_bench" if engine == "vllm" else "_guidellm"
    return f"{prefix}_owned_process_{run_name}_{phase}"


def remember_result(context: TrialContext, result: object, observed: bool = False, warmup: int | None = None) -> None:
    if warmup is not None:
        return
    key = "observed_benchmark_results" if observed else "benchmark_results"
    previous = context.values.get(key, ())
    context.values[key] = (*(previous if isinstance(previous, tuple) else ()), result)


def artifact_directory(base: Path, context: TrialContext, repeat: int | None, warmup: int | None) -> Path:
    directory = attempt_directory(base, context)
    return (
        directory / "warmups" / f"{warmup:03d}"
        if warmup
        else directory / "repeats" / f"{repeat:03d}"
        if repeat
        else directory
    )


def artifact_prefix(run_name: str, repeat: int | None, warmup: int | None) -> str:
    suffix = f"_warmup_{warmup}" if warmup else f"_repeat_{repeat}" if repeat else ""
    return f"benchmark_{run_name}{suffix}"


def failed(code: str, message: str) -> WorkerResult[None]:
    return WorkerResult.failed(Failure(code, message))


def benchmark_environment(config: VTuneConfig, guidellm: bool = False) -> dict[str, str]:
    environment = {key: str(value) for key, value in config.env.items()}
    environment["PYTHONUNBUFFERED"] = "1"
    if guidellm:
        environment["GUIDELLM__LOGGING__CONSOLE_LOG_LEVEL"] = logging_level(config)
    return environment


def record_command(
    context: TrialContext,
    engine: str,
    argv: tuple[str, ...],
    environment: dict[str, str],
    run_name: str,
    repeat: int | None,
) -> None:
    attempt = context.values.get("attempt_index", 1)
    if not isinstance(attempt, int) or isinstance(attempt, bool):
        raise ValueError("attempt index must be an integer")
    context.commands.append(CommandRecord(engine, argv, attempt, environment, run_name, repeat))
