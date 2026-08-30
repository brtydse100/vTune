"""Duration parsing and GuideLLM timeout estimation."""

from __future__ import annotations

from collections.abc import Mapping
import re

_DURATION = re.compile(r"^(\d+(?:\.\d+)?)\s*([smh]?)$")
_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600}


def parse_duration(value: object, label: str = "duration") -> float:
    if isinstance(value, bool):
        raise ValueError(f"'{label}' must be a positive duration")
    if isinstance(value, int | float):
        seconds = float(value)
    elif isinstance(value, str) and (match := _DURATION.fullmatch(value.strip().lower())):
        seconds = float(match.group(1)) * _UNITS[match.group(2)]
    else:
        raise ValueError(f"'{label}' must use seconds, '30s', '2m', or '1h'")
    if seconds <= 0:
        raise ValueError(f"'{label}' must be positive")
    return seconds


def timeout_for_run(run: Mapping[str, object], configured: object = None) -> float:
    """Return an explicit timeout or estimate duration plus a safety margin."""
    if configured is not None:
        return parse_duration(configured, "timeouts.benchmark")
    duration = _duration_constraint(run)
    if duration is None:
        return 180.0
    expected = duration * _strategy_count(run.get("profile"))
    return expected + max(30.0, expected * 0.25)


def normalize_durations(value: object) -> object:
    """Convert duration strings recursively before passing values to GuideLLM."""
    if isinstance(value, list):
        return [normalize_durations(item) for item in value]
    if isinstance(value, str):
        return parse_duration(value)
    return value


def _duration_constraint(run: Mapping[str, object]) -> float | None:
    constraints = run.get("constraints", [])
    if not isinstance(constraints, list):
        return None
    for constraint in constraints:
        if isinstance(constraint, Mapping) and constraint.get("kind") == "max_duration":
            seconds = constraint.get("seconds")
            if isinstance(seconds, list):
                return sum(parse_duration(item, "max_duration.seconds") for item in seconds)
            return parse_duration(seconds, "max_duration.seconds")
    return None


def _strategy_count(profile: object) -> int:
    if not isinstance(profile, Mapping):
        return 1
    for key in ("streams", "rates"):
        value = profile.get(key)
        if isinstance(value, list):
            return max(1, len(value))
    size = profile.get("sweep_size")
    return size if isinstance(size, int) and size > 0 else 1
