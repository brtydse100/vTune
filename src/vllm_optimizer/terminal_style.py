"""Small ANSI styling helpers for interactive terminal output."""

from __future__ import annotations

import os
import sys
from typing import TextIO


_CODES = {
    "cyan": "36",
    "green": "32",
    "red": "31",
    "yellow": "33",
    "dim": "2",
    "highlight": "1;96",
}


def supports_color(stream: TextIO) -> bool:
    """Return whether *stream* is an interactive color-capable terminal."""
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    return bool(is_tty and "NO_COLOR" not in os.environ
                and os.environ.get("TERM", "").lower() != "dumb")


def styled(message: str, tone: str, stream: TextIO | None = None) -> str:
    """Wrap *message* in ANSI color when the selected stream supports it."""
    target = stream or sys.stdout
    code = _CODES.get(tone)
    return f"\033[{code}m{message}\033[0m" if code and supports_color(target) else message
