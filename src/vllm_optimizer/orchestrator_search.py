"""Schedule search trials and persist every completed transition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.execution import WorkerSlot, parallel_trials, sequential_trials
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.run_session import RunAccumulator
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.orchestrator_messages import shown_parameters
from vllm_optimizer.search import TrialParameters
from vllm_optimizer.search.strategy import SearchSession
from vllm_optimizer.terminal import TerminalLogger

TrialRun = Callable[
    [TrialParameters, WorkerSlot | None], Awaitable[tuple[TrialReport, TrialScore | None, dict[str, float]]]
]


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    parameters: dict[str, TrialParameters]
    slots: dict[str, WorkerSlot | None]
    interrupted: bool


async def run_search(
    search: SearchSession,
    slots: tuple[WorkerSlot, ...],
    fixed: dict[str, object],
    execute: TrialRun,
    terminal: TerminalLogger,
    session: RunAccumulator,
    results: RunResultsManager,
    run_id: str,
    metric: str,
    started_at: str,
    interrupted: bool,
    source_run_id: str | None,
    sources: Mapping[str, Mapping[str, str]],
) -> SearchOutcome:
    parameters_by_id: dict[str, TrialParameters] = {}
    slots_by_id: dict[str, WorkerSlot | None] = {}

    def started(position: int, parameters: TrialParameters, slot: WorkerSlot | None) -> None:
        terminal.trial(
            position, search.total, parameters.trial_id, shown_parameters(parameters), slot.name if slot else None
        )

    if interrupted:
        return SearchOutcome(parameters_by_id, slots_by_id, True)
    scheduled = (
        parallel_trials(search, slots, fixed, execute, started)
        if slots
        else sequential_trials(search, execute, started)
    )
    async for completed in scheduled:
        position, parameters = completed.position, completed.parameters
        parameters_by_id[parameters.trial_id] = parameters
        slots_by_id[parameters.trial_id] = completed.slot
        report, score, scores_by_benchmark = completed.value
        session.record(parameters, report, score, scores_by_benchmark)
        owner = f"[{completed.slot.name}][{parameters.trial_id}] " if completed.slot else ""
        if score is not None:
            search.complete(parameters, score.value)
            failed = score.errored_requests + score.incomplete_requests
            terminal.info(
                f"{owner}OK Trial completed — score={score.value:.4f}, errors={failed}, error_rate={score.error_rate:.2%}"
            )
        else:
            search.fail(parameters, report.status is WorkerStatus.INTERRUPTED)
            detail = f"{report.failure.code}: {report.failure.message}" if report.failure else report.status.value
            terminal.warning(f"{owner}Trial {position} {report.status.value}: {detail}")
        session.persist(results, run_id, metric, "running", started_at, None, source_run_id, sources)
        if report.status is WorkerStatus.INTERRUPTED:
            return SearchOutcome(parameters_by_id, slots_by_id, True)
    return SearchOutcome(parameters_by_id, slots_by_id, False)
