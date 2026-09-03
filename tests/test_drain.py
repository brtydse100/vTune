import asyncio
from pathlib import Path

from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.drain import VLLMDrainWorker

METRICS = """# HELP vllm:num_requests_running running
vllm:num_requests_running{{engine=\"0\"}} {running}
vllm:num_requests_waiting {waiting}
"""


def _probe(values: list[str]):
    async def probe(url: str, timeout: float) -> str:
        return values.pop(0)

    return probe


def _run(tmp_path: Path, probe, grace: float = 0.02):
    worker = VLLMDrainWorker(tmp_path, "requests", grace, 0.001, 0.01, probe)
    return asyncio.run(worker.execute(TrialContext("trial", {"server_endpoint": "http://127.0.0.1:8000"})))


def test_drain_accepts_zero_metrics(tmp_path: Path) -> None:
    result = _run(tmp_path, _probe([METRICS.format(running=0, waiting=0)]))

    assert result.status.value == "completed"
    assert (tmp_path / "attempts" / "001" / "requests" / "drain.json").exists()


def test_drain_waits_for_delayed_zero(tmp_path: Path) -> None:
    result = _run(tmp_path, _probe([METRICS.format(running=1, waiting=0), METRICS.format(running=0, waiting=0)]))

    assert result.status.value == "completed"


def test_drain_fails_when_server_stays_busy(tmp_path: Path) -> None:
    result = _run(tmp_path, _probe([METRICS.format(running=1, waiting=0)]), grace=0)

    assert result.failure is not None
    assert result.failure.code == "server_drain_timeout"


def test_drain_fails_when_metrics_are_unavailable(tmp_path: Path) -> None:
    async def unavailable(url: str, timeout: float) -> str:
        raise OSError("metrics unavailable")

    result = _run(tmp_path, unavailable)

    assert result.failure is not None
    assert result.failure.code == "drain_metrics_unavailable"
