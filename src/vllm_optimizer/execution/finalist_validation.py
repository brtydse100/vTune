"""Sequential validation of drifted finalists before reporting a winner."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.execution.slots import WorkerSlot
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.run_session import RunAccumulator
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.measurement import benchmark_samples, sequentially_drifted
from vllm_optimizer.search.grid import TrialParameters

TrialRun = Callable[
    [Path, TrialParameters, WorkerSlot | None, str | None],
    Awaitable[tuple[TrialReport, TrialScore | None, Mapping[str, float]]],
]


async def validate_drifted_finalists(
    directory: Path,
    session: RunAccumulator,
    results: RunResultsManager,
    run_id: str,
    started_at: str,
    metric: str,
    threshold: float,
    parameters_by_id: Mapping[str, TrialParameters],
    slots_by_id: Mapping[str, WorkerSlot | None],
    run_trial: TrialRun,
    warn: Callable[[str], None],
    source_run_id: str | None,
    sources: Mapping[str, Mapping[str, str]],
) -> None:
    reports = {report.trial_id: report for report in session.reports}
    for finalist in session.ranking[:2]:
        report = reports.get(finalist.trial_id)
        if report is None or not _report_has_drift(report, metric, threshold):
            continue
        parameters = parameters_by_id[finalist.trial_id]
        warn(f"Sequentially validating drifted finalist {finalist.trial_id}")
        validated, score, by_benchmark = await run_trial(
            directory, parameters, slots_by_id.get(finalist.trial_id), "validation-001"
        )
        session.replace(parameters, validated, score, by_benchmark)
        session.persist(results, run_id, metric, "running", started_at, None, source_run_id, sources)


def _report_has_drift(report: TrialReport, metric: str, threshold: float) -> bool:
    return any(
        sequentially_drifted(values, threshold) for values in benchmark_samples(report.benchmarks, metric).values()
    )
