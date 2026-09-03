"""Small ANSI styling helpers for interactive terminal output."""

from __future__ import annotations

import os
import sys
from typing import TextIO

_CODES = {"cyan": "36", "green": "32", "red": "31", "yellow": "33", "dim": "2", "highlight": "1;96"}


def supports_color(stream: TextIO) -> bool:
    """Return whether *stream* is an interactive color-capable terminal."""
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    return bool(is_tty and "NO_COLOR" not in os.environ and os.environ.get("TERM", "").lower() != "dumb")


def styled(message: str, tone: str, stream: TextIO | None = None) -> str:
    """Wrap *message* in ANSI color when the selected stream supports it."""
    target = stream or sys.stdout
    code = _CODES.get(tone)
    return f"\033[{code}m{message}\033[0m" if code and supports_color(target) else message


def stage_label(worker: str) -> str:
    fixed = {
        "configuration_builder": "Building configuration",
        "vllm_runner": "Starting vLLM server",
        "readiness": "Waiting for server readiness",
        "cleanup": "Stopping owned processes",
    }
    if worker in fixed:
        return fixed[worker]
    if "_benchmark:" in worker:
        _, name, *repeat = worker.split(":")
        return f"Running benchmark {name}" + (f" ({repeat[0].replace('-', ' ')})" if repeat else "")
    return worker.replace("_", " ").capitalize()


def elapsed(seconds: float) -> str:
    minutes, remainder = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"


def progress_bar(position: int, total: int) -> str:
    width, completed = 16, min(position, total)
    filled = round(width * completed / max(total, 1))
    return f"[{('=' * filled).ljust(width, '-')}] {completed}/{total}"
