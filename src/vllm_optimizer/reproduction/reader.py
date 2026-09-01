"""Validated reading and shell rendering of trial manifests."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
from typing import Mapping

_TRIAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def load_manifest(run: Path, trial_id: str) -> dict[str, object]:
    if not _TRIAL_ID.fullmatch(trial_id):
        raise ValueError("trial ID must use only letters, numbers, '_' or '-'")
    path = Path(run) / "trials" / trial_id / "manifest.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read trial manifest '{path}': {error}") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError(f"Manifest '{path}' has an invalid schema")
    if document.get("trial_id") != trial_id:
        raise ValueError(f"Manifest '{path}' does not match trial '{trial_id}'")
    commands = document.get("commands")
    if not isinstance(commands, list) or any(not isinstance(item, dict) for item in commands):
        raise ValueError(f"Manifest '{path}' has invalid commands")
    return document


def commands(document: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    values = document.get("commands", [])
    return tuple(dict(value) for value in values if isinstance(value, dict))


def render_command(command: Mapping[str, object]) -> str:
    argv = command.get("argv")
    environment = command.get("environment", {})
    if not isinstance(argv, list) or not argv or not all(isinstance(value, str) for value in argv):
        raise ValueError("Manifest contains an invalid command argument array")
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in environment.items()
    ):
        raise ValueError("Manifest contains an invalid command environment")
    prefix = [f"{key}={value}" for key, value in sorted(environment.items())]
    return shlex.join([*prefix, *argv])
