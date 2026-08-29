"""Render a stored vLLM command for a POSIX shell."""

import json
from pathlib import Path
import shlex


def export_vllm_command(run: Path, trial_id: str) -> str:
    path = Path(run) / "trials" / trial_id / "manifest.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        commands = document["commands"]
        command = next(item for item in commands if item.get("kind") == "vllm")
        argv = command["argv"]
        environment = command.get("environment", {})
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, StopIteration,
            TypeError, AttributeError) as error:
        raise ValueError(f"Cannot export trial manifest '{path}': {error}") from error
    if not isinstance(argv, list) or not all(isinstance(value, str) for value in argv):
        raise ValueError(f"Manifest '{path}' contains an invalid vLLM command")
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in environment.items()
    ):
        raise ValueError(f"Manifest '{path}' contains an invalid environment")
    prefix = [f"{key}={value}" for key, value in sorted(environment.items())]
    return shlex.join([*prefix, *argv])
