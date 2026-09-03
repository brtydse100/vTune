"""Assemble the workers required for one resolved trial."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

from vllm_optimizer.benchmarks.configuration import (
    configured_engine,
    configured_repeats,
    configured_runs,
    configured_warmup_repeats,
)
from vllm_optimizer.benchmarks.timing import timeout_for_run
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import duration, logging_level, positive, server_port
from vllm_optimizer.execution.slots import WorkerSlot
from vllm_optimizer.search.grid import TrialParameters
from vllm_optimizer.workers.base import Worker
from vllm_optimizer.workers.benchmark import GuideLLMBenchmarkWorker
from vllm_optimizer.workers.configuration import ConfigurationBuilderWorker
from vllm_optimizer.workers.drain import VLLMDrainWorker
from vllm_optimizer.workers.process import ProcessRunner
from vllm_optimizer.workers.readiness import ReadinessWorker
from vllm_optimizer.workers.vllm import VLLMRunnerWorker
from vllm_optimizer.workers.vllm_benchmark import VLLMBenchmarkWorker


def build_trial_workers(
    config: VTuneConfig,
    parameters: TrialParameters,
    directory: Path,
    slot: WorkerSlot | None = None,
    benchmark_progress: Callable[[str, int | None, float, float], None] | None = None,
) -> tuple[Worker, ...]:
    execution = config.execution
    grace = positive(execution, "shutdown_grace", 15)
    drain_grace = positive(execution, "drain_grace", 15)
    debug = logging_level(config) == "DEBUG"
    port = slot.port if slot else server_port(config)
    runtime_args = {"port": port} if slot else {}
    runtime_env = {"CUDA_VISIBLE_DEVICES": ",".join(map(str, slot.devices))} if slot else {}
    workers: list[Worker] = [
        ConfigurationBuilderWorker(config, parameters.server_args, parameters.server_env, runtime_args, runtime_env),
        VLLMRunnerWorker(ProcessRunner(debug, "vllm"), directory / "vllm.log", grace),
        ReadinessWorker(
            host=str(execution.get("host", "127.0.0.1")),
            port=port,
            path=str(execution.get("health_path", "/health")),
            startup_timeout=duration(config.timeouts, "startup", 900),
        ),
    ]
    repeats = configured_repeats(config)
    warmups = configured_warmup_repeats(config)
    engine = configured_engine(config)
    benchmark_worker = GuideLLMBenchmarkWorker if engine == "guidellm" else VLLMBenchmarkWorker
    for run in configured_runs(config):
        for warmup in range(1, warmups + 1):
            workers.append(
                cast(
                    Worker,
                    benchmark_worker(
                        config,
                        run,
                        ProcessRunner(debug, f"{engine}:{run['name']}:warmup", capture=True),
                        directory,
                        timeout=timeout_for_run(run, config.timeouts.get("benchmark")),
                        shutdown_grace=grace,
                        warmup_index=warmup,
                        progress=benchmark_progress,
                    ),
                )
            )
            workers.append(VLLMDrainWorker(directory, str(run["name"]), drain_grace, warmup_index=warmup))
        for repeat in range(1, repeats + 1):
            repeat_index = repeat if repeats > 1 else None
            workers.append(
                cast(
                    Worker,
                    benchmark_worker(
                        config,
                        run,
                        ProcessRunner(debug, f"{engine}:{run['name']}", capture=True),
                        directory,
                        timeout=timeout_for_run(run, config.timeouts.get("benchmark")),
                        shutdown_grace=grace,
                        repeat_index=repeat_index,
                        progress=benchmark_progress,
                    ),
                )
            )
            workers.append(VLLMDrainWorker(directory, str(run["name"]), drain_grace, repeat_index=repeat_index))
    return tuple(workers)
