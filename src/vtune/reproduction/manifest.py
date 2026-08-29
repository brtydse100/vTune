"""Atomic persistence of a backend-neutral trial reproduction manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from vtune.config.models import VTuneConfig
from vtune.lifecycle.integrity import describe_artifacts
from vtune.reproduction.models import CommandRecord
from vtune.reproduction.redaction import (
    redact_arguments, redact_environment, redact_values,
)
from vtune.search.grid import TrialParameters
from vtune.workers.base import TrialContext


class ManifestWriter:
    def __init__(self, metadata: Mapping[str, object]) -> None:
        self._metadata = dict(metadata)

    def write(
        self, path: Path, config: VTuneConfig, parameters: TrialParameters,
        context: TrialContext, status: str,
        source: Mapping[str, str] | None = None,
    ) -> None:
        document = {
            "schema_version": 1,
            "trial_id": context.trial_id,
            "status": status,
            "model_path": config.model.path,
            "parameters": {
                "fixed_args": redact_values(config.server.args),
                "selected_args": redact_values(parameters.server_args),
                "fixed_env": redact_environment(_strings(config.server.env)),
                "selected_env": redact_environment(_strings(parameters.server_env)),
            },
            "benchmark": dict(config.benchmark),
            "policy": {
                "timeouts": dict(config.timeouts),
                "execution": dict(config.execution),
            },
            "artifacts": describe_artifacts(context.artifacts),
            "commands": [_command_document(command) for command in context.commands],
            "startup": [record.to_dict() for record in context.startups],
            "metadata": self._metadata,
        }
        if source is not None:
            document["source"] = dict(source)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        context.artifacts["manifest"] = str(path)


def _strings(values: Mapping[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in values.items()}


def _command_document(command: CommandRecord) -> dict[str, object]:
    document = command.to_dict()
    argv = document.get("argv", [])
    if not isinstance(argv, list) or not all(isinstance(value, str) for value in argv):
        raise TypeError("command arguments must be strings")
    document["argv"] = redact_arguments(argv)
    environment = document.get("environment", {})
    if not isinstance(environment, dict):
        raise TypeError("command environment must be a mapping")
    document["environment"] = redact_environment(environment)
    return document
