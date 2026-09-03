"""Build sanitized orchestrator display values."""

from __future__ import annotations

from pathlib import Path

from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import baseline_enabled
from vllm_optimizer.execution import WorkerSlot
from vllm_optimizer.reproduction.redaction import redact_values
from vllm_optimizer.search import TrialParameters


def experiment_details(
    config: VTuneConfig,
    total: int,
    mode: str,
    slots: tuple[WorkerSlot, ...],
    is_retry: bool,
    metric: str,
    directory: Path,
) -> dict[str, object]:
    return {
        "Experiment": config.experiment.name,
        "Sampler": config.optimization.get("sampler", "grid"),
        "Trials": total,
        "Mode": mode,
        "Workers": len(slots) if slots else 1,
        "Baseline": "enabled" if not is_retry and baseline_enabled(config) else "disabled",
        "Objective": metric,
        "Output": directory.resolve(),
    }


def shown_parameters(parameters: TrialParameters) -> dict[str, object]:
    return redact_values(
        {**parameters.server_args, **{f"env.{key}": value for key, value in parameters.server_env.items()}}
    )
