from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from vtune.benchmarks.guidellm import configured_repeats, configured_runs
from vtune.config.models import VTuneConfig
from vtune.config.runtime import (
    baseline_enabled, logging_level, max_attempts, maximize_metric, server_port,
)
from vtune.domain.results import WorkerStatus
from vtune.domain.trial_report import TrialReport
from vtune.managers.results import ResultsManager
from vtune.managers.run_results import RunResultsManager
from vtune.managers.run_session import RunAccumulator, run_status
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.managers.trial import TrialManager
from vtune.search import TrialParameters, create_search, validate_search
from vtune.search.fixed_session import FixedSearchSession
from vtune.terminal import TerminalLogger
from vtune.reporting import Reporter
from vtune.reporting.context import ReportContext
from vtune.reproduction.manifest import ManifestWriter
from vtune.reproduction.metadata import collect_metadata
from vtune.workers.base import TrialContext
from vtune.workers.factory import build_trial_workers

@dataclass(frozen=True, slots=True)
class RunOutcome:
    run_id: str
    directory: Path
    trials: tuple[TrialReport, ...]
    ranking: tuple[TrialScore, ...]
    summary: str
    status: str


class Orchestrator:
    def __init__(
        self, config: VTuneConfig,
        trials: tuple[TrialParameters, ...] | None = None,
        source_run_id: str | None = None,
        sources: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self._config = config
        self._metric = maximize_metric(config)
        if trials is None:
            validate_search(config)
        self._scoring = ScoringManager(self._metric)
        self._manifest = ManifestWriter({})
        self._retry_trials = trials
        self._source_run_id = source_run_id
        self._sources = dict(sources or {})
        self._terminal = TerminalLogger(logging_level(config))

    def validate(self) -> None:
        configured_runs(self._config)
        configured_repeats(self._config)
        if self._retry_trials is None:
            validate_search(self._config)
        server_port(self._config)
        baseline_enabled(self._config)

    async def run(self) -> RunOutcome:
        self.validate()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        started_at = datetime.now(timezone.utc).isoformat()
        directory = Path(self._config.experiment.output_dir) / self._config.experiment.name / run_id
        directory.mkdir(parents=True, exist_ok=True)
        results = RunResultsManager(directory / "result.json")
        names = tuple(str(run["name"]) for run in configured_runs(self._config))
        session = RunAccumulator(names, self._scoring)
        session.persist(results, run_id, self._metric, "running", started_at, None,
                        self._source_run_id, self._sources)
        self._terminal.info(f"Run: {run_id}\nDirectory: {directory.resolve()}")
        self._manifest = ManifestWriter(collect_metadata())
        interrupted = False
        if self._retry_trials is None and baseline_enabled(self._config):
            self._terminal.info("[baseline] starting")
            parameters = TrialParameters("baseline", {}, {})
            report, score, by_benchmark = await self._run_trial(
                directory, parameters
            )
            session.record(parameters, report, score, by_benchmark, baseline=True)
            session.persist(results, run_id, self._metric, "running", started_at, None,
                            self._source_run_id, self._sources)
            status = f"score={score.value:.4f}" if score else report.status.value
            self._terminal.info(f"[baseline] {status}")
            interrupted = report.status is WorkerStatus.INTERRUPTED
        search = (FixedSearchSession(self._retry_trials) if self._retry_trials is not None
                  else create_search(self._config, directory))
        position = 0
        while not interrupted and (parameters := search.suggest()) is not None:
            position += 1
            self._terminal.info(f"[{position}/{search.total}] {parameters.trial_id}: starting")
            report, score, scores_by_benchmark = await self._run_trial(directory, parameters)
            session.record(parameters, report, score, scores_by_benchmark)
            if score is not None:
                search.complete(parameters, score.value)
                self._terminal.info(f"[{position}/{search.total}] completed score={score.value:.4f}")
            else:
                search.fail(parameters, report.status is WorkerStatus.INTERRUPTED)
                self._terminal.warning(f"[{position}/{search.total}] {report.status.value}")
            session.persist(results, run_id, self._metric, "running", started_at, None,
                            self._source_run_id, self._sources)
            if report.status is WorkerStatus.INTERRUPTED:
                break
        status = run_status(tuple(session.reports))
        completed_at = datetime.now(timezone.utc).isoformat()
        session.persist(results, run_id, self._metric, status, started_at, completed_at,
                        self._source_run_id, self._sources)
        reports, ranking = tuple(session.reports), session.ranking
        by_benchmark = session.benchmark_rankings
        report_context = ReportContext(run_id, status, started_at, completed_at,
            self._source_run_id, self._sources, by_benchmark)
        Reporter(directory).write(
            self._metric, reports, ranking, session.baseline, report_context,
        )
        details = results.summary(self._metric, reports, ranking, by_benchmark,
                                  session.baseline)
        summary = f"Run status: {status}\n{details}"
        return RunOutcome(run_id, directory, reports, ranking, summary, status)

    async def _run_trial(
        self, directory: Path, parameters: TrialParameters,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        trial_dir = directory / "trials" / parameters.trial_id
        context = TrialContext(parameters.trial_id)
        outcome = await TrialManager(
            build_trial_workers(self._config, parameters, trial_dir),
            max_attempts(self._config),
        ).execute(context)
        manifest_path = trial_dir / "manifest.json"
        result_path = trial_dir / "result.json"
        context.artifacts["manifest"] = str(manifest_path)
        report = ResultsManager(result_path).save(context, outcome)
        context.artifacts["trial_result"] = str(result_path)
        self._manifest.write(manifest_path, self._config, parameters,
            context, outcome.status.value, self._sources.get(parameters.trial_id),
        )
        raw = context.values.get("benchmark_results", ())
        results = raw if isinstance(raw, tuple) else ()
        value = self._scoring.score(results)
        by_benchmark = self._scoring.score_each(results)
        if value is None or outcome.failure is not None:
            return report, None, {}
        args = {**self._config.server.args, **parameters.server_args}
        env = {**self._config.server.env, **parameters.server_env}
        return report, TrialScore(parameters.trial_id, value, args, env), by_benchmark
