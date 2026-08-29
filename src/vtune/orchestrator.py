"""Local MVP experiment loop coordinating one vLLM server at a time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vtune.benchmarks.guidellm import configured_repeats, configured_runs
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.models import VTuneConfig
from vtune.config.runtime import (
    baseline_enabled, max_attempts, maximize_metric, positive, server_port,
)
from vtune.domain.results import WorkerStatus
from vtune.domain.trial_report import TrialReport
from vtune.managers.results import ResultsManager
from vtune.managers.run_results import RunResultsManager
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.managers.trial import TrialManager
from vtune.search import TrialParameters, create_search, validate_search
from vtune.reporting import Reporter
from vtune.reproduction.manifest import ManifestWriter
from vtune.reproduction.metadata import collect_metadata
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
        self._metric = maximize_metric(config)
        validate_search(config)
        self._scoring = ScoringManager(self._metric)
        self._manifest = ManifestWriter({})

    def validate(self) -> None:
        configured_runs(self._config)
        configured_repeats(self._config)
        validate_search(self._config)
        server_port(self._config)
        baseline_enabled(self._config)

    async def run(self) -> RunOutcome:
        self.validate()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        directory = Path(self._config.experiment.output_dir) / self._config.experiment.name / run_id
        directory.mkdir(parents=True, exist_ok=True)
        self._manifest = ManifestWriter(collect_metadata())
        reports: list[TrialReport] = []
        scores: list[TrialScore] = []
        benchmark_scores: dict[str, list[TrialScore]] = {
            str(run["name"]): [] for run in configured_runs(self._config)
        }
        baseline_score: TrialScore | None = None
        if baseline_enabled(self._config):
            print("[baseline] starting", flush=True)
            report, baseline_score, _ = await self._run_trial(
                directory, TrialParameters("baseline", {}, {})
            )
            reports.append(report)
            status = f"score={baseline_score.value:.4f}" if baseline_score else report.status.value
            print(f"[baseline] {status}", flush=True)
        search = create_search(self._config, directory)
        position = 0
        while (parameters := search.suggest()) is not None:
            position += 1
            print(f"[{position}/{search.total}] {parameters.trial_id}: starting", flush=True)
            report, score, scores_by_benchmark = await self._run_trial(directory, parameters)
            reports.append(report)
            if score is not None:
                scores.append(score)
                search.complete(parameters, score.value)
                print(f"[{position}/{search.total}] completed score={score.value:.4f}")
            else:
                search.fail(parameters, report.status is WorkerStatus.INTERRUPTED)
                print(f"[{position}/{search.total}] {report.status.value}")
            for name, value in scores_by_benchmark.items():
                args = {**self._config.server.args, **parameters.server_args}
                env = {**self._config.server.env, **parameters.server_env}
                benchmark_scores[name].append(TrialScore(parameters.trial_id, value, args, env))
        ranking = self._scoring.rank(scores)
        by_benchmark = {name: self._scoring.rank(values)
                        for name, values in benchmark_scores.items()}
        results = RunResultsManager(directory / "result.json")
        results.save(
            run_id, self._metric, tuple(reports), ranking, by_benchmark, baseline_score
        )
        Reporter(directory).write(self._metric, tuple(reports), ranking, baseline_score)
        summary = results.summary(
            self._metric, tuple(reports), ranking, by_benchmark, baseline_score
        )
        return RunOutcome(run_id, directory, tuple(reports), ranking, summary)

    async def _run_trial(
        self, directory: Path, parameters: TrialParameters,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        trial_dir = directory / "trials" / parameters.trial_id
        context = TrialContext(parameters.trial_id)
        outcome = await TrialManager(
            self._workers(parameters, trial_dir), max_attempts(self._config)
        ).execute(context)
        self._manifest.write(
            trial_dir / "manifest.json", self._config, parameters,
            context, outcome.status.value,
        )
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
        grace = positive(execution, "shutdown_grace", 15)
        workers: tuple[Worker, ...] = (
            ConfigurationBuilderWorker(self._config, parameters.server_args, parameters.server_env),
            VLLMRunnerWorker(ProcessRunner(), directory / "vllm.log", grace),
            ReadinessWorker(host=str(execution.get("host", "127.0.0.1")),
                            port=server_port(self._config),
                            path=str(execution.get("health_path", "/health")),
                            startup_timeout=positive(self._config.timeouts, "startup", 900)),
        )
        repeats = configured_repeats(self._config)
        return workers + tuple(
            GuideLLMBenchmarkWorker(
                self._config, run, ProcessRunner(), directory,
                timeout=timeout_for_run(run, self._config.timeouts.get("benchmark", "auto")),
                shutdown_grace=grace, repeat_index=repeat,
            ) for run in configured_runs(self._config) for repeat in range(1, repeats + 1)
        )
