import asyncio
import json
from pathlib import Path

import pytest

import vllm_optimizer.managers.run_finalization as finalization_module
import vllm_optimizer.orchestrator as orchestrator_module
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.orchestrator import Orchestrator
from vllm_optimizer.terminal import TerminalLogger


def _config(tmp_path: Path) -> VTuneConfig:
    return VTuneConfig(
        1,
        ExperimentConfig("fault", str(tmp_path)),
        {"model": "demo"},
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
        optimization={"maximize": "requests_per_second"},
    )


def test_coordinator_failure_atomically_finalizes_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_metadata() -> dict[str, object]:
        raise RuntimeError("sentinel must not be persisted")

    monkeypatch.setattr(orchestrator_module, "collect_metadata", fail_metadata)

    with pytest.raises(RuntimeError, match="sentinel"):
        asyncio.run(Orchestrator(_config(tmp_path)).run())

    result_paths = list(tmp_path.glob("fault/*/result.json"))
    assert len(result_paths) == 1
    document = json.loads(result_paths[0].read_text(encoding="utf-8"))
    assert document["status"] == "failed"
    assert document["completed_at"]
    assert document["run_failure"] == {"code": "coordinator_failure", "message": "Coordinator failed (RuntimeError)"}
    assert "sentinel" not in result_paths[0].read_text(encoding="utf-8")


def _result_document(tmp_path: Path) -> dict[str, object]:
    result_path = next(tmp_path.glob("fault/*/result.json"))
    return json.loads(result_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("failure", [RuntimeError("search"), KeyboardInterrupt()])
def test_search_failure_and_interrupt_get_terminal_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    def fail_search(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise failure

    monkeypatch.setattr(orchestrator_module, "create_search", fail_search)
    with pytest.raises(type(failure)):
        asyncio.run(Orchestrator(_config(tmp_path)).run())
    document = _result_document(tmp_path)
    assert document["status"] == ("interrupted" if isinstance(failure, KeyboardInterrupt) else "failed")
    assert document["completed_at"]


@pytest.mark.parametrize("target", ["reporter", "summary"])
def test_final_output_failures_overwrite_completed_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    if target == "reporter":
        monkeypatch.setattr(
            finalization_module.Reporter,
            "write",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("reporter")),
        )
    else:
        monkeypatch.setattr(
            finalization_module.RunResultsManager,
            "summary",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("summary")),
        )
    monkeypatch.setattr(orchestrator_module, "collect_metadata", lambda: {})
    with pytest.raises(RuntimeError, match=target):
        asyncio.run(Orchestrator(_config(tmp_path), trials=()).run())
    assert _result_document(tmp_path)["status"] == "failed"


def test_failure_after_success_preserves_completed_trial_and_closes_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    closes = 0

    async def execute(self: object, directory: Path, parameters: object, slot=None, artifact_subdirectory=None):
        nonlocal calls
        del self, directory, slot, artifact_subdirectory
        calls += 1
        if calls == 2:
            raise OSError("manifest write failed")
        report = TrialReport(1, parameters.trial_id, orchestrator_module.WorkerStatus.COMPLETED, (), {})
        score = orchestrator_module.TrialScore(parameters.trial_id, 1.0, parameters.server_args, {}, 1)
        return report, score, {"requests": 1.0}

    original_close = TerminalLogger.close

    def close(terminal: TerminalLogger) -> float:
        nonlocal closes
        closes += 1
        return original_close(terminal)

    monkeypatch.setattr(orchestrator_module.TrialExecutor, "execute", execute)
    monkeypatch.setattr(orchestrator_module, "collect_metadata", lambda: {})
    monkeypatch.setattr(TerminalLogger, "close", close)
    with pytest.raises(OSError, match="manifest"):
        asyncio.run(Orchestrator(_config(tmp_path)).run())
    document = _result_document(tmp_path)
    assert document["status"] == "failed"
    assert len(document["trials"]) == 1
    assert closes == 1


def test_real_task_cancellation_is_recorded_as_interrupted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    async def execute(*args: object, **kwargs: object):
        del args, kwargs
        started.set()
        await asyncio.Event().wait()

    async def scenario() -> None:
        monkeypatch.setattr(orchestrator_module.TrialExecutor, "execute", execute)
        monkeypatch.setattr(orchestrator_module, "collect_metadata", lambda: {})
        task = asyncio.create_task(Orchestrator(_config(tmp_path)).run())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    document = _result_document(tmp_path)
    assert document["status"] == "interrupted"
    assert document["run_failure"]["code"] == "interrupted"
