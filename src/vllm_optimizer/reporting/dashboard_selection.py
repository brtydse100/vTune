"""Select and reproduce dashboard recommendations."""

from __future__ import annotations

from pathlib import Path

from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reproduction.export import export_vllm_command


def best_command(directory: Path, best: TrialScore | None) -> str:
    if best is None:
        return "Unavailable: no completed tuned trial."
    try:
        return export_vllm_command(directory, best.trial_id)
    except ValueError as error:
        return f"Unavailable: {error}"


def improvement(best: TrialScore | None, baseline: TrialScore | None) -> float | None:
    if best is None or baseline is None or baseline.value == 0:
        return None
    return (best.value - baseline.value) / baseline.value * 100


def best_observed(best_tuned: TrialScore | None, baseline: TrialScore | None) -> TrialScore | None:
    candidates = [item for item in (best_tuned, baseline) if item is not None]
    return (
        min(
            candidates,
            key=lambda item: (-item.value, item.error_rate, item.errored_requests + item.incomplete_requests),
        )
        if candidates
        else None
    )
