"""Human-readable, non-executing reproduction output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from vllm_optimizer.reproduction.reader import commands, load_manifest, render_command
from vllm_optimizer.reproduction.redaction import REDACTED


def reproduce_trial(run: Path, trial_id: str) -> str:
    document = load_manifest(run, trial_id)
    lines = [
        f"Trial: {trial_id}", f"Status: {document.get('status', 'unknown')}",
        f"Model: {document.get('model_path', 'unknown')}",
    ]
    source = document.get("source")
    if isinstance(source, Mapping):
        lines.append(f"Source: {source.get('run_id')} / {source.get('trial_id')}")
    lines.extend(_metadata(document.get("metadata")))
    lines.extend(_startup(document.get("startup")))
    lines.append("\nCommands (display only; nothing was executed):")
    redacted = False
    for index, command in enumerate(commands(document), start=1):
        kind = str(command.get("kind", "command"))
        details = [f"attempt {command.get('attempt', '?')}"]
        if command.get("benchmark") is not None:
            details.append(str(command["benchmark"]))
        if command.get("repeat") is not None:
            details.append(f"repeat {command['repeat']}")
        rendered = render_command(command)
        redacted = redacted or REDACTED in rendered
        lines.extend((f"\n{index}. {kind} ({', '.join(details)})", rendered))
    if redacted:
        lines.append(
            "\nWARNING: <redacted> values must be supplied manually before use."
        )
    return "\n".join(lines)


def _metadata(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    software = value.get("software", {})
    versions = json.dumps(software, sort_keys=True) if isinstance(software, Mapping) else "{}"
    gpus = value.get("gpus", [])
    gpu_names = ", ".join(str(gpu.get("name")) for gpu in gpus
                          if isinstance(gpu, Mapping)) if isinstance(gpus, list) else ""
    return [f"Python: {value.get('python_version', 'unknown')}",
            f"Software: {versions}", f"CUDA: {value.get('cuda_version', 'unknown')}",
            f"GPU: {gpu_names or 'unknown'}"]


def _startup(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rendered = ", ".join(
        f"attempt {item.get('attempt')}: {item.get('seconds')}s"
        for item in value if isinstance(item, Mapping)
    )
    return [f"Startup: {rendered}"] if rendered else []
