"""Small, dependency-free domain entities for experiment execution."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .states import AttemptStatus, RunStatus, TrialStatus


def _required_text(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _snapshot(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class Run:
    id: str
    experiment_name: str
    status: RunStatus = RunStatus.CREATED

    def __post_init__(self) -> None:
        _required_text(self.id, "run id")
        _required_text(self.experiment_name, "experiment name")


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    name: str
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_text(self.id, "scenario id")
        _required_text(self.name, "scenario name")
        object.__setattr__(self, "parameters", _snapshot(self.parameters))


@dataclass(frozen=True, slots=True)
class Trial:
    id: str
    run_id: str
    number: int
    parameters: Mapping[str, object] = field(default_factory=dict)
    status: TrialStatus = TrialStatus.PENDING

    def __post_init__(self) -> None:
        _required_text(self.id, "trial id")
        _required_text(self.run_id, "run id")
        if self.number < 1:
            raise ValueError("trial number must be at least 1")
        object.__setattr__(self, "parameters", _snapshot(self.parameters))


@dataclass(frozen=True, slots=True)
class Attempt:
    id: str
    trial_id: str
    number: int
    status: AttemptStatus = AttemptStatus.CREATED

    def __post_init__(self) -> None:
        _required_text(self.id, "attempt id")
        _required_text(self.trial_id, "trial id")
        if self.number < 1:
            raise ValueError("attempt number must be at least 1")
