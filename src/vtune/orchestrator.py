"""Local MVP experiment loop coordinating one vLLM server at a time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vtune.benchmarks.guidellm import configured_runs
from vtune.config.models import VTuneConfig
from vtune.domain.trial_report import TrialReport
from vtune.managers.results import ResultsManager
from vtune.managers.run_results import RunResultsManager
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.managers.trial import TrialManager
from vtune.search.grid import TrialParameters, expand_grid
from vtune.workers.base import TrialContext, Worker
from vtune.workers.benchmark import GuideLLMBenchmarkWorker
from vtune.workers.configuration import ConfigurationBuilderWorker
from vtune.workers.process import ProcessRunner
from vtune.workers.readiness import ReadinessWorker
from vtune.workers.vllm import VLLMRunnerWorker


@dataclass(frozen=True, slots=True)
class RunOutcome:
    run_id: str
    directory: Path
    trials: tuple[TrialReport, ...]
    ranking: tuple[TrialScore, ...]
    summary: str


class Orchestrator:
    def __init__(self, config: VTuneConfig) -> None:
        self._config = config
        self._metric = _maximize_metric(config)
        self._scoring = ScoringManager(self._metric)

    def validate(self) -> None:
        configured_runs(self._config)
        expand_grid(self._config)
        _port(self._config)

    async def run(self) -> RunOutcome:
        self.validate()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        directory = Path(self._config.experiment.output_dir) / self._config.experiment.name / run_id
        reports: list[TrialReport] = []
        scores: list[TrialScore] = []
        benchmark_scores: dict[str, list[TrialScore]] = {
            str(run["name"]): [] for run in configured_runs(self._config)
        }
        trials = expand_grid(self._config)
        for position, parameters in enumerate(trials, start=1):
            print(f"[{position}/{len(trials)}] {parameters.trial_id}: starting", flush=True)
            report, score, scores_by_benchmark = await self._run_trial(directory, parameters)
            reports.append(report)
            if score is not None:
                scores.append(score)
                print(f"[{position}/{len(trials)}] completed score={score.value:.4f}")
            else:
                print(f"[{position}/{len(trials)}] {report.status.value}")
            for name, value in scores_by_benchmark.items():
                args = {**self._config.server.args, **parameters.server_args}
                env = {**self._config.server.env, **parameters.server_env}
                benchmark_scores[name].append(TrialScore(parameters.trial_id, value, args, env))
        ranking = self._scoring.rank(scores)
        by_benchmark = {name: self._scoring.rank(values)
                        for name, values in benchmark_scores.items()}
        results = RunResultsManager(directory / "result.json")
        results.save(run_id, self._metric, tuple(reports), ranking, by_benchmark)
        summary = results.summary(self._metric, tuple(reports), ranking, by_benchmark)
        return RunOutcome(run_id, directory, tuple(reports), ranking, summary)

    async def _run_trial(
        self, directory: Path, parameters: TrialParameters,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        trial_dir = directory / "trials" / parameters.trial_id
        context = TrialContext(parameters.trial_id)
        outcome = await TrialManager(self._workers(parameters, trial_dir)).execute(context)
        report = ResultsManager(trial_dir / "result.json").save(context, outcome)
        raw = context.values.get("benchmark_results", ())
        results = raw if isinstance(raw, tuple) else ()
        value = self._scoring.score(results)
        by_benchmark = self._scoring.score_each(results)
        if value is None or outcome.failure is not None:
            return report, None, {}
        args = {**self._config.server.args, **parameters.server_args}
        env = {**self._config.server.env, **parameters.server_env}
        return report, TrialScore(parameters.trial_id, value, args, env), by_benchmark

    def _workers(self, parameters: TrialParameters, directory: Path) -> tuple[Worker, ...]:
        execution = self._config.execution
        grace = _positive(execution, "shutdown_grace", 15)
        workers: tuple[Worker, ...] = (
            ConfigurationBuilderWorker(self._config, parameters.server_args, parameters.server_env),
            VLLMRunnerWorker(ProcessRunner(), directory / "vllm.log", grace),
            ReadinessWorker(host=str(execution.get("host", "127.0.0.1")),
                            port=_port(self._config),
                            path=str(execution.get("health_path", "/health")),
                            startup_timeout=_positive(self._config.timeouts, "startup", 900)),
        )
        return workers + tuple(
            GuideLLMBenchmarkWorker(
                self._config, run, ProcessRunner(), directory,
                timeout=_positive(self._config.timeouts, "benchmark", 180),
                shutdown_grace=grace,
            ) for run in configured_runs(self._config)
        )


def _maximize_metric(config: VTuneConfig) -> str:
    unknown = set(config.optimization) - {"maximize"}
    metric = config.optimization.get("maximize")
    if unknown or not isinstance(metric, str) or not metric.strip():
        raise ValueError("optimization requires only a non-empty 'maximize' metric")
    return metric


def _positive(values: object, key: str, default: float) -> float:
    value = values.get(key, default)  # type: ignore[union-attr]
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(f"'{key}' must be a positive number")
    return float(value)


def _port(config: VTuneConfig) -> int:
    value = config.server.args.get("port", 8000)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError("server.args.port must be a valid integer port")
    return value
