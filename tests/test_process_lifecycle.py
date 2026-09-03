import asyncio
import sys
from pathlib import Path

import pytest

from vllm_optimizer.workers.process import ProcessRunner, ProcessSpec


def test_process_spec_validates_and_snapshots_environment(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ProcessSpec(())
    with pytest.raises(TypeError):
        ProcessSpec((sys.executable,), {"BAD": 1})  # type: ignore[dict-item]
    environment = {"SYNTHETIC_VALUE": "before"}
    spec = ProcessSpec((sys.executable, "-c", "pass"), environment, tmp_path)
    environment["SYNTHETIC_VALUE"] = "after"
    assert spec.env["SYNTHETIC_VALUE"] == "before"
    assert spec.cwd == tmp_path


def test_process_output_environment_and_exit_code(tmp_path: Path) -> None:
    async def run() -> int:
        script = "import os,sys; print(os.environ['SYNTHETIC_VALUE']); print('err',file=sys.stderr); sys.exit(3)"
        process = await ProcessRunner().start(
            ProcessSpec((sys.executable, "-c", script), {"SYNTHETIC_VALUE": "visible"}, tmp_path),
            tmp_path / "process.log",
        )
        return await process.wait()

    assert asyncio.run(run()) == 3
    output = (tmp_path / "process.log").read_text(encoding="utf-8")
    assert "visible" in output and "err" in output


def test_process_capture_stream_and_timeout_termination(tmp_path: Path) -> None:
    async def run() -> int:
        process = await ProcessRunner(capture=True).start(
            ProcessSpec((sys.executable, "-c", "import time; print('start',flush=True); time.sleep(30)")),
            tmp_path / "sleep.log",
        )
        await asyncio.sleep(0.1)
        process.write_log("marker\n")
        return await process.stop(grace_period=0.05)

    assert isinstance(asyncio.run(run()), int)
    assert "marker" in (tmp_path / "sleep.log").read_text(encoding="utf-8")
