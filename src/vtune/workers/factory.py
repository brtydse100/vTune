"""Assemble the workers required for one resolved trial."""

from pathlib import Path

from vtune.benchmarks.configuration import (
    configured_engine, configured_repeats, configured_runs, configured_warmup_repeats,
)
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.models import VTuneConfig
from vtune.config.runtime import duration, logging_level, positive, server_port
from vtune.execution.slots import WorkerSlot
from vtune.search.grid import TrialParameters
from vtune.workers.base import Worker
from vtune.workers.benchmark import GuideLLMBenchmarkWorker
from vtune.workers.configuration import ConfigurationBuilderWorker
from vtune.workers.drain import VLLMDrainWorker
from vtune.workers.process import ProcessRunner
from vtune.workers.readiness import ReadinessWorker
from vtune.workers.vllm import VLLMRunnerWorker
from vtune.workers.vllm_benchmark import VLLMBenchmarkWorker


def build_trial_workers(
    config: VTuneConfig, parameters: TrialParameters, directory: Path,
    slot: WorkerSlot | None = None,
) -> tuple[Worker, ...]:
    execution = config.execution
    grace = positive(execution, "shutdown_grace", 15)
    drain_grace = positive(execution, "drain_grace", 15)
    debug = logging_level(config) == "DEBUG"
    port = slot.port if slot else server_port(config)
    runtime_args = {"port": port} if slot else {}
    runtime_env = ({"CUDA_VISIBLE_DEVICES": ",".join(map(str, slot.devices))}
                   if slot else {})
    workers: list[Worker] = [
        ConfigurationBuilderWorker(
            config, parameters.server_args, parameters.server_env,
            runtime_args, runtime_env,
        ),
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
    benchmark_worker = (GuideLLMBenchmarkWorker
                        if engine == "guidellm" else VLLMBenchmarkWorker)
    for run in configured_runs(config):
        for warmup in range(1, warmups + 1):
            workers.append(benchmark_worker(
                config, run, ProcessRunner(debug, f"{engine}:{run['name']}:warmup"), directory,
                timeout=timeout_for_run(run, config.timeouts.get("benchmark")),
                shutdown_grace=grace, warmup_index=warmup,
            ))
            workers.append(VLLMDrainWorker(
                directory, str(run["name"]), drain_grace,
                warmup_index=warmup,
            ))
        for repeat in range(1, repeats + 1):
            repeat_index = repeat if repeats > 1 else None
            workers.append(benchmark_worker(
                config, run, ProcessRunner(debug, f"{engine}:{run['name']}"), directory,
                timeout=timeout_for_run(run, config.timeouts.get("benchmark")),
                shutdown_grace=grace, repeat_index=repeat_index,
            ))
            workers.append(VLLMDrainWorker(
                directory, str(run["name"]), drain_grace,
                repeat_index=repeat_index,
            ))
    return tuple(workers)
