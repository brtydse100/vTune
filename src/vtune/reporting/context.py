"""Lifecycle context displayed by the static report."""

from dataclasses import dataclass, field
from typing import Mapping

from vtune.managers.scoring import TrialScore


@dataclass(frozen=True, slots=True)
class ReportContext:
    run_id: str = "unknown"
    status: str = "unknown"
    started_at: str | None = None
    completed_at: str | None = None
    source_run_id: str | None = None
    sources: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    benchmark_rankings: Mapping[str, tuple[TrialScore, ...]] = field(default_factory=dict)
    execution_mode: str = "sequential"
