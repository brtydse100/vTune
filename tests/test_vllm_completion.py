import asyncio
import json
from pathlib import Path

from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.process import ProcessSpec
from vllm_optimizer.workers.vllm_benchmark import VLLMBenchmarkWorker


class _Process:
    async def wait(self) -> int:
        return 0

    async def stop(self, grace_period: float = 5) -> int:
        return 0


class _Runner:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document

    async def start(self, spec: ProcessSpec, log_path: Path) -> _Process:
        (log_path.parent / "results.json").write_text(json.dumps(self.document), encoding="utf-8")
        return _Process()


def test_vllm_worker_rejects_early_success_exit(tmp_path: Path) -> None:
    run = {"name": "requests", "args": {"num_prompts": 2}}
    config = VTuneConfig(
        1,
        ExperimentConfig("test"),
        {"model": "demo"},
        benchmark={"engine": "vllm", "runs": [run]},
        optimization={"maximize": "requests_per_second"},
    )
    runner = _Runner(
        {"backend": "vllm", "model_id": "demo", "num_prompts": 2, "completed": 1, "request_throughput": 5.0}
    )
    worker = VLLMBenchmarkWorker(config, run, runner, tmp_path)
    context = TrialContext("trial", {"server_endpoint": "http://127.0.0.1:8000"})

    result = asyncio.run(worker.execute(context))

    assert result.status is WorkerStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == "benchmark_requests_incomplete"
    assert "benchmark_results" not in context.values
