"""Deterministic grid expansion for vLLM arguments and environment values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from itertools import product

from vtune.config.models import VTuneConfig


@dataclass(frozen=True, slots=True)
class TrialParameters:
    trial_id: str
    server_args: Mapping[str, object]
    server_env: Mapping[str, object]


def expand_grid(config: VTuneConfig) -> tuple[TrialParameters, ...]:
    options = [
        *(("arg", key, _values(value, f"tune.{key}"))
          for key, value in sorted(config.tune.items())),
        *(("env", key, _values(value, f"tune_env.{key}"))
          for key, value in sorted(config.tune_env.items())),
    ]
    combinations = product(*(entry[2] for entry in options)) if options else [()]
    trials = []
    for index, combination in enumerate(combinations, start=1):
        arguments: dict[str, object] = {}
        environment: dict[str, object] = {}
        for (kind, name, _), value in zip(options, combination):
            (arguments if kind == "arg" else environment)[name] = value
        trials.append(TrialParameters(f"trial-{index:04d}", arguments, environment))
    return tuple(trials)


def _values(definition: object, label: str) -> tuple[object, ...]:
    if not isinstance(definition, Mapping):
        raise ValueError(f"'{label}' must be a mapping")
    if set(definition) == {"values"}:
        values = definition["values"]
        if not isinstance(values, list) or not values:
            raise ValueError(f"'{label}.values' must be a non-empty list")
        return tuple(values)
    if set(definition) == {"min", "max", "step"}:
        return _range(definition, label)
    raise ValueError(f"'{label}' requires either values or min/max/step")


def _range(definition: Mapping[str, object], label: str) -> tuple[object, ...]:
    try:
        start, stop = Decimal(str(definition["min"])), Decimal(str(definition["max"]))
        step = Decimal(str(definition["step"]))
    except Exception as error:
        raise ValueError(f"'{label}' range values must be numeric") from error
    if step <= 0 or start > stop:
        raise ValueError(f"'{label}' requires step > 0 and min <= max")
    values = []
    current = start
    integral = all(isinstance(definition[key], int) for key in ("min", "max", "step"))
    while current <= stop:
        values.append(int(current) if integral else float(current))
        current += step
    return tuple(values)
