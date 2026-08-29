"""Atomic persistence of a backend-neutral trial reproduction manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from vtune.config.models import VTuneConfig
from vtune.reproduction.models import CommandRecord
from vtune.reproduction.redaction import redact_environment
from vtune.search.grid import TrialParameters
from vtune.workers.base import TrialContext


class ManifestWriter:
    def __init__(self, metadata: Mapping[str, object]) -> None:
        self._metadata = dict(metadata)

    def write(
        self, path: Path, config: VTuneConfig, parameters: TrialParameters,
        context: TrialContext, status: str,
    ) -> None:
        document = {
            "schema_version": 1,
            "trial_id": context.trial_id,
            "status": status,
            "model_path": config.model.path,
            "parameters": {
                "fixed_args": dict(config.server.args),
                "selected_args": dict(parameters.server_args),
                "fixed_env": redact_environment(_strings(config.server.env)),
                "selected_env": redact_environment(_strings(parameters.server_env)),
            },
            "benchmark": dict(config.benchmark),
            "commands": [_command_document(command) for command in context.commands],
            "startup": [record.to_dict() for record in context.startups],
            "metadata": self._metadata,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        context.artifacts["manifest"] = str(path)


def _strings(values: Mapping[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in values.items()}


def _command_document(command: CommandRecord) -> dict[str, object]:
    document = command.to_dict()
    environment = document.get("environment", {})
    if not isinstance(environment, dict):
        raise TypeError("command environment must be a mapping")
    document["environment"] = redact_environment(environment)
    return document
