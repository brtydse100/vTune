import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import vllm_optimizer.reproduction.metadata as metadata
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.search.grid import expand_grid
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.failure_details import classified_failure, log_excerpt
from vllm_optimizer.workers.process import ProcessRunner, ProcessSpec
from vllm_optimizer.workers.readiness import ReadinessWorker


def test_readiness_success_timeout_and_early_exit(tmp_path: Path) -> None:
    async def scenario(probe, script="import time; time.sleep(30)", startup=0.1):
        process = await ProcessRunner().start(
            ProcessSpec((sys.executable, "-c", script)), tmp_path / f"{id(probe)}.log"
        )
        context = TrialContext("trial", {"server_process": process, "attempt_index": 1})
        context.artifacts["vllm_log"] = str(tmp_path / f"{id(probe)}.log")
        worker = ReadinessWorker(startup_timeout=startup, poll_interval=0.01, request_timeout=0.01, health_probe=probe)
        result = await worker.execute(context)
        await process.stop(0.05)
        return result, context

    async def healthy(url, timeout):
        return True

    result, context = asyncio.run(scenario(healthy))
    assert result.status.value == "completed"
    assert context.values["server_endpoint"] == "http://127.0.0.1:8000"
    assert context.startups[0].attempt == 1

    async def unhealthy(url, timeout):
        return False

    result, _ = asyncio.run(scenario(unhealthy, startup=0.03))
    assert result.failure and result.failure.code == "server_startup_timeout"

    result, _ = asyncio.run(scenario(unhealthy, "raise SystemExit(4)", 0.2))
    assert result.failure and result.failure.code == "server_exited_early"


def test_failure_classification_and_excerpt(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text("noise\nRuntimeError: CUDA out of memory\nlast line\n", encoding="utf-8")
    failure = classified_failure(log, "default", "worker failed")
    assert failure.code == "cuda_oom" and "RuntimeError" in failure.message
    assert "last line" in log_excerpt(log, 1)
    assert log_excerpt(tmp_path / "missing.log") == ""


def test_metadata_collection_with_and_without_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata.shutil, "which", lambda name: "nvidia-smi")
    monkeypatch.setattr(
        metadata.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="Synthetic GPU, GPU-1, 999.0, 1024\n"),
    )
    document = metadata.collect_metadata()
    assert document["gpus"] == [
        {"name": "Synthetic GPU", "uuid": "GPU-1", "driver_version": "999.0", "memory_mib": "1024"}
    ]
    monkeypatch.setattr(
        metadata.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.SubprocessError("failure"))
    )
    assert metadata._run("missing") is None
    monkeypatch.setattr(metadata.shutil, "which", lambda name: None)
    assert metadata._gpu_metadata() == []


def test_grid_ranges_and_invalid_definitions() -> None:
    config = VTuneConfig(
        1,
        ExperimentConfig("grid"),
        {"model": "demo"},
        tune={"integer": {"min": 1, "max": 3, "step": 1}},
        tune_env={"float": {"min": 0.5, "max": 1.0, "step": 0.5}},
    )
    trials = expand_grid(config)
    assert len(trials) == 6
    assert trials[0].server_args == {"integer": 1}
    assert trials[-1].server_env == {"float": 1.0}
    for definition in ({"values": []}, {"min": 2, "max": 1, "step": 1}, {"unknown": 1}):
        bad = VTuneConfig(1, ExperimentConfig("bad"), {"model": "demo"}, tune={"x": definition})
        with pytest.raises(ValueError):
            expand_grid(bad)
