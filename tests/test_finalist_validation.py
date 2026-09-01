import asyncio
from pathlib import Path

from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.execution.finalist_validation import validate_drifted_finalists
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.run_session import RunAccumulator
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.search.grid import TrialParameters


def _report(values: list[float]) -> TrialReport:
    return TrialReport(1, "trial-0001", WorkerStatus.COMPLETED, ({
        "name": "requests", "workloads": ({"metrics": {"score": value}},),
    } for value in values), {}, {})


def test_drifted_finalist_is_rerun_and_replaced(tmp_path: Path) -> None:
    parameters = TrialParameters("trial-0001", {}, {})
    initial = _report([1, 1, 2, 2])
    validated = _report([1, 1, 1, 1])
    session = RunAccumulator(("requests",), ScoringManager("score"))
    session.record(parameters, initial, TrialScore("trial-0001", 2, {}, {}), {"requests": 2})
    calls: list[str | None] = []

    async def rerun(directory, trial, slot, artifact_subdirectory):
        calls.append(artifact_subdirectory)
        return validated, TrialScore("trial-0001", 1, {}, {}), {"requests": 1}

    asyncio.run(validate_drifted_finalists(
        tmp_path, session, RunResultsManager(tmp_path / "result.json"),
        "run", "2026-01-01T00:00:00+00:00", "score", 0.05,
        {parameters.trial_id: parameters}, {parameters.trial_id: None},
        rerun, lambda message: None, None, {},
    ))

    assert calls == ["validation-001"]
    assert session.ranking[0].value == 1
    assert session.reports[0].benchmarks[0]["workloads"][0]["metrics"]["score"] == 1
