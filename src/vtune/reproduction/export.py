"""Render a stored vLLM command for a POSIX shell."""

from pathlib import Path

from vtune.reproduction.reader import commands, load_manifest, render_command


def export_vllm_command(run: Path, trial_id: str) -> str:
    document = load_manifest(run, trial_id)
    command = next((item for item in commands(document) if item.get("kind") == "vllm"), None)
    if command is None:
        raise ValueError(f"Trial '{trial_id}' has no stored vLLM command")
    return render_command(command)
