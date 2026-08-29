"""Assemble the workers required for one resolved trial."""

from pathlib import Path

from vtune.benchmarks.guidellm import configured_repeats, configured_runs
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.models import VTuneConfig
from vtune.config.runtime import positive, server_port
from vtune.search.grid import TrialParameters
from vtune.workers.base import Worker
from vtune.workers.benchmark import GuideLLMBenchmarkWorker
from vtune.workers.configuration import ConfigurationBuilderWorker
from vtune.workers.process import ProcessRunner
from vtune.workers.readiness import ReadinessWorker
from vtune.workers.vllm import VLLMRunnerWorker


def build_trial_workers(
    config: VTuneConfig, parameters: TrialParameters, directory: Path,
) -> tuple[Worker, ...]:
    execution = config.execution
    grace = positive(execution, "shutdown_grace", 15)
    workers: tuple[Worker, ...] = (
        ConfigurationBuilderWorker(config, parameters.server_args, parameters.server_env),
        VLLMRunnerWorker(ProcessRunner(), directory / "vllm.log", grace),
        ReadinessWorker(
            host=str(execution.get("host", "127.0.0.1")),
            port=server_port(config),
            path=str(execution.get("health_path", "/health")),
            startup_timeout=positive(config.timeouts, "startup", 900),
        ),
    )
    repeats = configured_repeats(config)
    return workers + tuple(
        GuideLLMBenchmarkWorker(
            config, run, ProcessRunner(), directory,
            timeout=timeout_for_run(run, config.timeouts.get("benchmark", "auto")),
            shutdown_grace=grace, repeat_index=repeat,
        )
        for run in configured_runs(config)
        for repeat in range(1, repeats + 1)
    )
