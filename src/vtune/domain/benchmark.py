"""Backend-neutral benchmark results consumed by scoring and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class WorkloadResult:
    index: int
    configuration: Mapping[str, object]
    metrics: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("workload index must not be negative")
        object.__setattr__(self, "configuration", _freeze(self.configuration))
        object.__setattr__(self, "metrics", _freeze(self.metrics))


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    run_name: str
    backend: str
    backend_version: str
    workloads: tuple[WorkloadResult, ...]
    raw_artifact: Path

    def __post_init__(self) -> None:
        if not self.run_name.strip() or not self.backend.strip() or not self.backend_version.strip():
            raise ValueError("benchmark run, backend, and version must not be empty")
        if not self.workloads:
            raise ValueError("benchmark result must contain at least one workload")
        object.__setattr__(self, "workloads", tuple(self.workloads))
        object.__setattr__(self, "raw_artifact", Path(self.raw_artifact))
