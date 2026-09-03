import asyncio
import json
from pathlib import Path

import pytest

import vllm_optimizer.orchestrator as orchestrator_module
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.execution.trial_executor import TrialExecutor
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.orchestrator import Orchestrator


def _config(tmp_path: Path, sampler: str = "grid") -> VTuneConfig:
    return VTuneConfig(
        1,
        ExperimentConfig("synthetic", str(tmp_path), 7),
        {"model": "demo"},
        tune={"max-num-seqs": {"values": [1, 2]}},
        benchmark={
            "repeats": 1,
            "min_repeats": 1,
            "warmup_repeats": 0,
            "runs": [
                {
                    "name": "requests",
                    "profile": {"kind": "synchronous"},
                    "constraints": [{"kind": "max_requests", "count": 1}],
                    "data": [{"kind": "synthetic_text"}],
                }
            ],
        },
        baseline={"enabled": False},
        optimization={
            "maximize": "requests_per_second",
            "sampler": sampler,
            **({} if sampler == "grid" else {"trials": 2}),
        },
    )


def test_complete_synthetic_run_selects_same_winner_everywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(self: TrialExecutor, directory: Path, parameters, slot=None, artifact_subdirectory=None):
        value = float(parameters.server_args["max-num-seqs"])
        benchmark = {
            "name": "requests",
            "backend": "synthetic",
            "workloads": (
                {
                    "index": 0,
                    "configuration": {},
                    "metrics": {
                        "requests_per_second": {"average": value},
                        "request_totals": {"successful": 1, "errored": 0, "incomplete": 0},
                    },
                },
            ),
        }
        report = TrialReport(1, parameters.trial_id, WorkerStatus.COMPLETED, (benchmark,), {})
        score = TrialScore(parameters.trial_id, value, parameters.server_args, parameters.server_env, 1)
        return report, score, {"requests": value}

    monkeypatch.setattr(TrialExecutor, "execute", execute)
    monkeypatch.setattr(orchestrator_module, "collect_metadata", lambda: {})

    outcome = asyncio.run(Orchestrator(_config(tmp_path)).run())

    assert outcome.status == "completed"
    assert outcome.ranking[0].value == 2
    persisted = json.loads((outcome.directory / "result.json").read_text(encoding="utf-8"))
    assert persisted["best"]["trial_id"] == outcome.ranking[0].trial_id
    assert persisted["best_by_benchmark"]["requests"]["trial_id"] == outcome.ranking[0].trial_id
    assert persisted["benchmark_policy"] == {
        "repeats": 1,
        "minimum_repeats": 1,
        "warmup_repeats": 0,
        "drift_threshold": 0.05,
        "maximum_failure_percentage": 0.0,
    }
    assert outcome.ranking[0].trial_id in (outcome.directory / "report.html").read_text(encoding="utf-8")


def test_random_and_tpe_synthetic_runs_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(self: TrialExecutor, directory: Path, parameters, slot=None, artifact_subdirectory=None):
        value = float(parameters.server_args["max-num-seqs"])
        report = TrialReport(1, parameters.trial_id, WorkerStatus.COMPLETED, (), {})
        return report, TrialScore(parameters.trial_id, value, parameters.server_args, {}, 1), {"requests": value}

    monkeypatch.setattr(TrialExecutor, "execute", execute)
    monkeypatch.setattr(orchestrator_module, "collect_metadata", lambda: {})

    for sampler in ("random", "tpe"):
        outcome = asyncio.run(Orchestrator(_config(tmp_path / sampler, sampler)).run())
        assert len(outcome.trials) == 2
        assert outcome.ranking[0].value == 2
