"""Best-effort software, operating-system, and GPU metadata collection."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import shutil
import subprocess

from vllm_optimizer import __version__


def collect_metadata() -> dict[str, object]:
    return {
        "vllm_optimizer_version": __version__,
        "vtune_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "software": {name: _package_version(name) for name in ("vllm", "guidellm")},
        "cuda_version": _cuda_version(),
        "gpus": _gpu_metadata(),
    }


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _run(*argv: str) -> str | None:
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _gpu_metadata() -> list[dict[str, str]]:
    executable = shutil.which("nvidia-smi")
    wsl_executable = Path("/usr/lib/wsl/lib/nvidia-smi")
    if executable is None and wsl_executable.is_file():
        executable = str(wsl_executable)
    if executable is None:
        return []
    output = _run(
        executable, "--query-gpu=name,uuid,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    )
    if not output:
        return []
    keys = ("name", "uuid", "driver_version", "memory_mib")
    return [dict(zip(keys, (part.strip() for part in line.split(",", 3))))
            for line in output.splitlines()]


def _cuda_version() -> str | None:
    try:
        import torch
    except ImportError:
        return None
    return str(torch.version.cuda) if torch.version.cuda else None
