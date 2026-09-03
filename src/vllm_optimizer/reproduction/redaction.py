"""Protect secret environment values in persistent artifacts."""

import re
from collections.abc import Mapping, Sequence

_SECRET_NAME = re.compile(
    r"(?:^|[-_.])(?:TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIALS?|AUTHORIZATION|COOKIE|"
    r"API[-_]?KEY|ACCESS[-_]?KEY(?:[-_]?ID)?|PRIVATE[-_]?KEY|CLIENT[-_]?SECRET)(?:$|[-_.])",
    re.I,
)
REDACTED = "<redacted>"


def redact_environment(values: Mapping[str, str]) -> dict[str, str]:
    return {name: str(_redact(name, value)) for name, value in values.items()}


def redact_values(values: Mapping[str, object]) -> dict[str, object]:
    return {name: _redact(name, value) for name, value in values.items()}


def redact(value: object) -> object:
    """Recursively redact conventionally named secrets in mappings and sequences."""
    if isinstance(value, Mapping):
        return {str(name): _redact(str(name), item) for name, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def _redact(name: str, value: object) -> object:
    if is_secret_name(name):
        return REDACTED
    if name.lower().replace("_", "-") in {"header", "headers"}:
        return _redact_headers(value)
    return redact(value)


def _redact_headers(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(name): REDACTED if is_secret_name(str(name)) else redact(item) for name, item in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_redact_headers(item) for item in value)
    if isinstance(value, str) and ":" in value:
        name, separator, _ = value.partition(":")
        return f"{name}{separator} {REDACTED}" if is_secret_name(name) else value
    return value


def redact_arguments(values: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for value in values:
        if hide_next:
            redacted.append(REDACTED)
            hide_next = False
        elif value.startswith("--") and "=" in value:
            name, item = value.split("=", 1)
            if name in {"--header", "--headers"}:
                redacted.append(f"{name}={_redact_headers(item)}")
            else:
                redacted.append(f"{name}={REDACTED}" if is_secret_name(name) else value)
        elif redacted and redacted[-1] in {"--header", "--headers"}:
            redacted.append(str(_redact_headers(value)))
        else:
            redacted.append(value)
            hide_next = value.startswith("--") and is_secret_name(value)
    return redacted


def is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name))
