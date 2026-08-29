"""Protect secret environment values in persistent artifacts."""

from collections.abc import Mapping
import re

_SECRET_NAME = re.compile(r"(?:TOKEN|PASSWORD|PASSWD|SECRET|API_KEY|PRIVATE_KEY)", re.I)
REDACTED = "<redacted>"


def redact_environment(values: Mapping[str, str]) -> dict[str, str]:
    return {
        name: REDACTED if _SECRET_NAME.search(name) else value
        for name, value in values.items()
    }
