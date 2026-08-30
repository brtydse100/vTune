from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from vtune.benchmarks.configuration import configured_repeats, configured_runs
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.models import VTuneConfig
from vtune.config.runtime import (
    baseline_enabled, duration, logging_level, maximize_metric, server_port,
)
from vtune.domain.results import WorkerStatus
from vtune.domain.trial_report import TrialReport
from vtune.execution import (
    TrialExecutor, WorkerSlot, execution_mode, parallel_trials, sequential_trials, worker_slots,
)
from vtune.managers.run_results import RunResultsManager
from vtune.managers.run_session import RunAccumulator, run_status
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.search import (
    TrialParameters, create_search, expand_grid, search_warning, validate_search,
)
from vtune.search.fixed_session import FixedSearchSession
from vtune.terminal import TerminalLogger
from vtune.reporting import Reporter
from vtune.reporting.context import ReportContext
from vtune.reproduction.manifest import ManifestWriter
from vtune.reproduction.metadata import collect_metadata

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
        self._trial_executor: TrialExecutor | None = None
        self._retry_trials = trials
        self._source_run_id = source_run_id
        self._sources = dict(sources or {})
        self._terminal = TerminalLogger(logging_level(config))

    def validate(self) -> None:
        runs = configured_runs(self._config)
        configured_repeats(self._config)
        if self._retry_trials is None:
            validate_search(self._config)
        server_port(self._config)
        baseline_enabled(self._config)
        slots = worker_slots(self._config)
        if slots and not all(
            any(slot.supports(trial.server_args, self._config.server) for slot in slots)
            for trial in expand_grid(self._config)
        ):
            raise ValueError("a trial tensor-parallel-size exceeds every parallel worker")
        duration(self._config.timeouts, "startup", 900)
        for run in runs:
            timeout_for_run(run, self._config.timeouts.get("benchmark"))

    async def run(self) -> RunOutcome:
        self.validate()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        started_at = datetime.now(timezone.utc).isoformat()
        directory = Path(self._config.experiment.output_dir) / self._config.experiment.name / run_id
        directory.mkdir(parents=True, exist_ok=True)
        mode = execution_mode(self._config)
        results = RunResultsManager(directory / "result.json", mode)
        names = tuple(str(run["name"]) for run in configured_runs(self._config))
        session = RunAccumulator(names, self._scoring)
        session.persist(results, run_id, self._metric, "running", started_at, None,
                        self._source_run_id, self._sources)
        self._terminal.info(f"Run: {run_id}\nDirectory: {directory.resolve()}")
        if self._retry_trials is None and (warning := search_warning(self._config)):
            self._terminal.warning(f"WARNING: {warning}")
        self._manifest = ManifestWriter(collect_metadata())
        self._trial_executor = TrialExecutor(
            self._config, self._scoring, self._terminal, self._manifest, self._sources,
        )
        slots = worker_slots(self._config)
        search = (FixedSearchSession(self._retry_trials) if self._retry_trials is not None
                  else create_search(self._config, directory))
        self._terminal.experiment({
            "Experiment": self._config.experiment.name,
            "Sampler": self._config.optimization.get("sampler", "grid"),
            "Trials": search.total,
            "Mode": mode,
            "Workers": len(slots) if slots else 1,
            "Baseline": "enabled" if (
                self._retry_trials is None and baseline_enabled(self._config)
            ) else "disabled",
            "Objective": self._metric,
            "Output": directory.resolve(),
        })
        interrupted = False
        if self._retry_trials is None and baseline_enabled(self._config):
            self._terminal.baseline()
            parameters = TrialParameters("baseline", {}, {})
            baseline_slot = next((slot for slot in slots
                                  if slot.supports({}, self._config.server)), None)
            report, score, by_benchmark = await self._run_trial(
                directory, parameters, baseline_slot,
            )
            session.record(parameters, report, score, by_benchmark, baseline=True)
            session.persist(results, run_id, self._metric, "running", started_at, None,
                            self._source_run_id, self._sources)
            if score:
                self._terminal.info(f"OK Baseline completed — score={score.value:.4f}")
            else:
                detail = (f"{report.failure.code}: {report.failure.message}"
                          if report.failure else report.status.value)
                self._terminal.warning(f"Baseline {report.status.value}: {detail}")
            interrupted = report.status is WorkerStatus.INTERRUPTED
        async def execute(parameters: TrialParameters, slot: WorkerSlot | None):
            return await self._run_trial(directory, parameters, slot)

        def started(position: int, parameters: TrialParameters,
                    slot: WorkerSlot | None) -> None:
            shown = {**parameters.server_args,
                     **{f"env.{key}": value for key, value in parameters.server_env.items()}}
            self._terminal.trial(
                position, search.total, parameters.trial_id, shown,
                slot.name if slot else None,
            )

        scheduled = (sequential_trials(FixedSearchSession(()), execute, started)
                     if interrupted else parallel_trials(
                         search, slots, dict(self._config.server), execute, started,
                     ) if slots else sequential_trials(search, execute, started))
        async for completed in scheduled:
            if interrupted:
                break
            position, parameters = completed.position, completed.parameters
            owner = (f"[{completed.slot.name}][{parameters.trial_id}] "
                     if completed.slot else "")
            report, score, scores_by_benchmark = completed.value
            session.record(parameters, report, score, scores_by_benchmark)
            if score is not None:
                search.complete(parameters, score.value)
                failed_requests = score.errored_requests + score.incomplete_requests
                self._terminal.info(
                    f"{owner}OK Trial completed — score={score.value:.4f}, "
                    f"errors={failed_requests}, error_rate={score.error_rate:.2%}"
                )
                best = session.ranking[0]
                self._terminal.info(
                    f"Best so far: {best.trial_id} — score={best.value:.4f}, "
                    f"error_rate={best.error_rate:.2%}"
                )
            else:
                search.fail(parameters, report.status is WorkerStatus.INTERRUPTED)
                detail = (f"{report.failure.code}: {report.failure.message}"
                          if report.failure else report.status.value)
                self._terminal.warning(
                    f"{owner}Trial {position} {report.status.value}: {detail}"
                )
            session.persist(results, run_id, self._metric, "running", started_at, None,
                            self._source_run_id, self._sources)
            if report.status is WorkerStatus.INTERRUPTED:
                interrupted = True
                break
        status = run_status(tuple(session.reports))
        completed_at = datetime.now(timezone.utc).isoformat()
        session.persist(results, run_id, self._metric, status, started_at, completed_at,
                        self._source_run_id, self._sources)
        reports, ranking = tuple(session.reports), session.ranking
        by_benchmark = session.benchmark_rankings
        report_context = ReportContext(run_id, status, started_at, completed_at,
            self._source_run_id, self._sources, by_benchmark, mode)
        Reporter(directory).write(
            self._metric, reports, ranking, session.baseline, report_context,
        )
        details = results.summary(self._metric, reports, ranking, by_benchmark,
                                  session.baseline)
        summary = f"Run status: {status}\n{details}"
        return RunOutcome(run_id, directory, reports, ranking, summary, status)

    async def _run_trial(
        self, directory: Path, parameters: TrialParameters,
        slot: WorkerSlot | None = None,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        if self._trial_executor is None:
            raise RuntimeError("trial executor is not initialized")
        return await self._trial_executor.execute(directory, parameters, slot)
