"""Successful and exceptional finalization of an active run."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vllm_optimizer.benchmarks.configuration import configured_failure_percentage, configured_min_repeats
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.run_session import RunAccumulator, run_status
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting import Reporter
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.llm_summary import summarize
from vllm_optimizer.terminal import TerminalLogger


@dataclass(frozen=True, slots=True)
class FinalizedRun:
    reports: tuple[TrialReport, ...]
    ranking: tuple[TrialScore, ...]
    summary: str
    status: str


@dataclass(frozen=True, slots=True)
class RunOutcome:
    run_id: str
    directory: Path
    trials: tuple[TrialReport, ...]
    ranking: tuple[TrialScore, ...]
    summary: str
    status: str


class RunFinalizer:
    def __init__(self, config: VTuneConfig, metric: str, terminal: TerminalLogger) -> None:
        self._config, self._metric, self._terminal = config, metric, terminal
        self._active: tuple[RunResultsManager, RunAccumulator, str, str] | None = None

    def start(self, results: RunResultsManager, session: RunAccumulator, run_id: str, started_at: str) -> None:
        self._active = results, session, run_id, started_at

    def fail(self, error: BaseException, source_run_id: str | None, sources: Mapping[str, Mapping[str, str]]) -> None:
        try:
            if self._active is None:
                return
            results, session, run_id, started_at = self._active
            interrupted = isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit))
            session.persist(
                results,
                run_id,
                self._metric,
                "interrupted" if interrupted else "failed",
                started_at,
                datetime.now(UTC).isoformat(),
                source_run_id,
                sources,
                run_failure={
                    "code": "interrupted" if interrupted else "coordinator_failure",
                    "message": "Run interrupted" if interrupted else f"Coordinator failed ({type(error).__name__})",
                },
            )
        finally:
            self._terminal.close()

    async def complete(
        self,
        source_run_id: str | None,
        sources: Mapping[str, Mapping[str, str]],
        benchmark_names: tuple[str, ...],
        execution_mode: str,
    ) -> FinalizedRun:
        if self._active is None:
            raise RuntimeError("run finalizer is not active")
        results, session, run_id, started_at = self._active
        status, completed_at = run_status(tuple(session.reports)), datetime.now(UTC).isoformat()
        reports, ranking, by_benchmark = tuple(session.reports), session.ranking, session.benchmark_rankings
        llm_summary, llm_error = await summarize(self._config, self._metric, ranking)
        if llm_error:
            self._terminal.warning(llm_error)
        context = ReportContext(
            run_id,
            status,
            started_at,
            completed_at,
            source_run_id,
            sources,
            by_benchmark,
            execution_mode,
            benchmark_names,
            llm_summary,
            llm_error,
            configured_min_repeats(self._config),
            float(self._config.analysis.get("drift_threshold", 0.05)),
            configured_failure_percentage(self._config),
        )
        session.persist(
            results, run_id, self._metric, status, started_at, completed_at, source_run_id, sources, llm_summary
        )
        Reporter(results.output_path.parent).write(self._metric, reports, ranking, session.baseline, context)
        details = results.summary(self._metric, reports, ranking, by_benchmark, session.baseline)
        self._terminal.session_complete(self._terminal.close())
        self._active = None
        return FinalizedRun(reports, ranking, f"Run status: {status}\n{details}", status)
