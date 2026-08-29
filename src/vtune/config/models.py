"""Typed configuration values used by vTune."""

from dataclasses import dataclass, field
from typing import Any, Mapping


ConfigMapping = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    name: str
    output_dir: str = "runs"
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class VTuneConfig:
    schema_version: int
    experiment: ExperimentConfig
    server: ConfigMapping
    tune: ConfigMapping = field(default_factory=dict)
    env: ConfigMapping = field(default_factory=dict)
    tune_env: ConfigMapping = field(default_factory=dict)
    benchmark: ConfigMapping = field(default_factory=dict)
    baseline: ConfigMapping = field(default_factory=dict)
    optimization: ConfigMapping = field(default_factory=dict)
    analysis: ConfigMapping = field(default_factory=dict)
    timeouts: ConfigMapping = field(default_factory=dict)
    logging: ConfigMapping = field(default_factory=dict)
    execution: ConfigMapping = field(default_factory=dict)
