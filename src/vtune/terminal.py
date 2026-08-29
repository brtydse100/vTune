"""Terminal logging policy shared by the CLI and experiment runtime."""

from __future__ import annotations

from dataclasses import replace

from vtune.config.models import VTuneConfig
from vtune.config.runtime import LOG_LEVELS


def with_debug_logging(config: VTuneConfig) -> VTuneConfig:
    return replace(config, logging={**config.logging, "level": "DEBUG"})


class TerminalLogger:
    def __init__(self, level: str) -> None:
        self._threshold = LOG_LEVELS.index(level)

    def debug(self, message: str) -> None:
        self._write("DEBUG", message)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARNING", message)

    def _write(self, level: str, message: str) -> None:
        if LOG_LEVELS.index(level) >= self._threshold:
            print(message, flush=True)
