"""Attempt-aware artifact paths shared by process-owning workers."""

from pathlib import Path

from vllm_optimizer.workers.base import TrialContext


def attempt_path(path: Path, context: TrialContext) -> Path:
    index = context.values.get("attempt_index", 1)
    return Path(path).parent / "attempts" / f"{int(index):03d}" / Path(path).name


def attempt_directory(path: Path, context: TrialContext) -> Path:
    index = context.values.get("attempt_index", 1)
    return Path(path) / "attempts" / f"{int(index):03d}"
