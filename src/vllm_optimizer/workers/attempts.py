"""Attempt-aware artifact paths shared by process-owning workers."""

from pathlib import Path

from vllm_optimizer.workers.base import TrialContext


def attempt_path(path: Path, context: TrialContext) -> Path:
    return Path(path).parent / "attempts" / f"{_index(context):03d}" / Path(path).name


def attempt_directory(path: Path, context: TrialContext) -> Path:
    return Path(path) / "attempts" / f"{_index(context):03d}"


def _index(context: TrialContext) -> int:
    value = context.values.get("attempt_index", 1)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("attempt index must be an integer")
    return value
