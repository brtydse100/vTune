"""Protect secret environment values in persistent artifacts."""

from collections.abc import Mapping, Sequence
import re

_SECRET_NAME = re.compile(
    r"(?:^|[-_])(?:TOKEN|PASSWORD|PASSWD|SECRET|API[-_]?KEY|PRIVATE[-_]?KEY)(?:$|[-_])",
    re.I,
)
REDACTED = "<redacted>"


def redact_environment(values: Mapping[str, str]) -> dict[str, str]:
    return {name: REDACTED if is_secret_name(name) else value
            for name, value in values.items()}


def redact_values(values: Mapping[str, object]) -> dict[str, object]:
    return {name: REDACTED if is_secret_name(name) else value
            for name, value in values.items()}


def redact_arguments(values: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for value in values:
        if hide_next:
            redacted.append(REDACTED)
            hide_next = False
        elif value.startswith("--") and "=" in value:
            name, _ = value.split("=", 1)
            redacted.append(f"{name}={REDACTED}" if is_secret_name(name) else value)
        else:
            redacted.append(value)
            hide_next = value.startswith("--") and is_secret_name(value)
    return redacted


def is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name))
