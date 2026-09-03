"""Create run identity and scoring policy for orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vllm_optimizer.benchmarks.configuration import configured_failure_percentage, configured_min_repeats
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.managers.scoring import ScoringManager


@dataclass(frozen=True, slots=True)
class RunIdentity:
    run_id: str
    started_at: str
    directory: Path


def run_identity(config: VTuneConfig) -> RunIdentity:
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    directory = Path(config.experiment.output_dir) / config.experiment.name / run_id
    return RunIdentity(run_id, datetime.now(UTC).isoformat(), directory)


def scoring(config: VTuneConfig, metric: str, run_names: tuple[str, ...]) -> ScoringManager:
    return ScoringManager(metric, configured_min_repeats(config), run_names, configured_failure_percentage(config))
