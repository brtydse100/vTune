"""Assemble the workers required for one resolved trial."""

from pathlib import Path

from vtune.benchmarks.guidellm import configured_repeats, configured_runs
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.models import VTuneConfig
from vtune.config.runtime import duration, logging_level, positive, server_port
from vtune.execution.slots import WorkerSlot
from vtune.search.grid import TrialParameters
from vtune.workers.base import Worker
from vtune.workers.benchmark import GuideLLMBenchmarkWorker
from vtune.workers.configuration import ConfigurationBuilderWorker
from vtune.workers.process import ProcessRunner
from vtune.workers.readiness import ReadinessWorker
from vtune.workers.vllm import VLLMRunnerWorker


def build_trial_workers(
    config: VTuneConfig, parameters: TrialParameters, directory: Path,
    slot: WorkerSlot | None = None,
) -> tuple[Worker, ...]:
    execution = config.execution
    grace = positive(execution, "shutdown_grace", 15)
    debug = logging_level(config) == "DEBUG"
    port = slot.port if slot else server_port(config)
    runtime_args = {"port": port} if slot else {}
    runtime_env = ({"CUDA_VISIBLE_DEVICES": ",".join(map(str, slot.devices))}
                   if slot else {})
    workers: tuple[Worker, ...] = (
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
    )
    repeats = configured_repeats(config)
    return workers + tuple(
        GuideLLMBenchmarkWorker(
            config, run, ProcessRunner(debug, f"guidellm:{run['name']}"), directory,
            timeout=timeout_for_run(run, config.timeouts.get("benchmark")),
            shutdown_grace=grace, repeat_index=repeat,
        )
        for run in configured_runs(config)
        for repeat in range(1, repeats + 1)
    )
