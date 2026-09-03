import asyncio
from pathlib import Path

import pytest

import vllm_optimizer.execution.trial_executor as module
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult
from vllm_optimizer.domain.results import Failure, WorkerResult
from vllm_optimizer.execution.slots import WorkerSlot
from vllm_optimizer.managers.scoring import ScoringManager
from vllm_optimizer.reproduction.manifest import ManifestWriter
from vllm_optimizer.search.grid import TrialParameters
from vllm_optimizer.terminal import TerminalLogger


def _config(tmp_path: Path) -> VTuneConfig:
    return VTuneConfig(
        1,
        ExperimentConfig("executor", str(tmp_path)),
        {"model": "demo", "dtype": "float16"},
        env={"SAFE": "yes"},
        benchmark={
            "repeats": 1,
            "min_repeats": 1,
            "warmup_repeats": 0,
            "runs": [{"name": "requests", "profile": {}, "constraints": [], "data": [{}]}],
        },
        optimization={"maximize": "requests_per_second"},
    )


def test_trial_executor_persists_and_scores_synthetic_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Worker:
        name = "synthetic_benchmark:requests:repeat-1"

        async def execute(self, context):
            context.values["benchmark_results"] = (
                BenchmarkResult(
                    "requests",
                    "synthetic",
                    "1",
                    (
                        WorkloadResult(
                            0,
                            {},
                            {
                                "requests_per_second": {"average": 5.0},
                                "request_totals": {"successful": 1, "errored": 0, "incomplete": 0},
                            },
                        ),
                    ),
                    tmp_path / "raw.json",
                    1,
                    0.1,
                ),
            )
            return WorkerResult.completed()

        async def cleanup(self, context):
            return None

    monkeypatch.setattr(module, "build_trial_workers", lambda *args, **kwargs: (Worker(),))
    executor = module.TrialExecutor(
        _config(tmp_path),
        ScoringManager("requests_per_second", 1, ("requests",)),
        TerminalLogger("WARNING"),
        ManifestWriter({}),
        {},
    )

    report, score, by_benchmark = asyncio.run(
        executor.execute(
            tmp_path / "run", TrialParameters("trial-1", {"max-num-seqs": 2}, {}), WorkerSlot("gpu", (0,), 8100)
        )
    )

    assert report.status.value == "completed"
    assert score and score.value == 5 and score.server_args["dtype"] == "float16"
    assert by_benchmark == {"requests": 5.0}
    assert (tmp_path / "run" / "trials" / "trial-1" / "result.json").exists()
    assert (tmp_path / "run" / "trials" / "trial-1" / "manifest.json").exists()


def test_trial_executor_excludes_failed_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Worker:
        name = "failure"

        async def execute(self, context):
            return WorkerResult.failed(Failure("synthetic_failure", "failed"))

        async def cleanup(self, context):
            return None

    monkeypatch.setattr(module, "build_trial_workers", lambda *args, **kwargs: (Worker(),))
    executor = module.TrialExecutor(
        _config(tmp_path), ScoringManager("requests_per_second"), TerminalLogger("WARNING"), ManifestWriter({}), {}
    )
    report, score, by_benchmark = asyncio.run(
        executor.execute(tmp_path / "run", TrialParameters("trial-failed", {}, {}))
    )
    assert report.failure and score is None and by_benchmark == {}
