"""Terminal logging policy shared by the CLI and experiment runtime."""

from __future__ import annotations

from dataclasses import replace
import sys
from time import monotonic

from vtune.config.models import VTuneConfig
from vtune.config.runtime import LOG_LEVELS


def with_debug_logging(config: VTuneConfig) -> VTuneConfig:
    return replace(config, logging={**config.logging, "level": "DEBUG"})


class TerminalLogger:
    def __init__(self, level: str) -> None:
        self._threshold = LOG_LEVELS.index(level)
        self._color = bool(getattr(sys.stdout, "isatty", lambda: False)())
        self._inline = self._color and level != "DEBUG"
        self._stage_started: dict[str, float] = {}

    def debug(self, message: str) -> None:
        self._write("DEBUG", message)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARNING", message)

    def experiment(self, values: dict[str, object]) -> None:
        self.info("=" * 24 + " vTune experiment " + "=" * 24)
        width = max(map(len, values), default=0)
        self.info("\n".join(f"{name:<{width}}  {value}" for name, value in values.items()))

    def trial(self, position: int, total: int, trial_id: str,
              values: dict[str, object], worker: str | None = None) -> None:
        owner = f" · {worker}" if worker else ""
        self.info(f"\n{'─' * 20} Trial {position} of {total} · {trial_id}{owner} {'─' * 20}")
        if values:
            width = max(map(len, values))
            self.info("\n".join(f"{name:<{width}}  {value}" for name, value in values.items()))

    def baseline(self) -> None:
        self.info(f"\n{'─' * 18} Baseline experiment · fixed configuration {'─' * 18}")

    def stage(self, event: str, worker: str, scope: str | None = None) -> None:
        label = _stage_label(worker)
        prefix = f"{scope} " if scope else ""
        key = f"{scope}:{worker}" if scope else worker
        if event == "starting":
            self._stage_started[key] = monotonic()
            if self._inline and scope is None:
                print(f"{self._symbol('…')} {label}", end="", flush=True)
            return
        elapsed = monotonic() - self._stage_started.pop(key, monotonic())
        symbol = self._symbol("✓" if event == "completed" else "✗")
        method = self.info if event == "completed" else self.warning
        if self._inline and scope is None:
            print("\r\033[2K", end="", flush=True)
        method(f"{prefix}{symbol} {label} — {_elapsed(elapsed)}")

    def _symbol(self, value: str) -> str:
        if not self._color:
            return {"…": "...", "✓": "OK", "✗": "ERROR"}[value]
        colors = {"…": "36", "✓": "32", "✗": "31"}
        return f"\033[{colors[value]}m{value}\033[0m"

    def _write(self, level: str, message: str) -> None:
        if LOG_LEVELS.index(level) >= self._threshold:
            print(message, flush=True)


def _stage_label(worker: str) -> str:
    if worker == "configuration_builder":
        return "Building configuration"
    if worker == "vllm_runner":
        return "Starting vLLM server"
    if worker == "readiness":
        return "Waiting for server readiness"
    if worker == "cleanup":
        return "Stopping owned processes"
    if worker.startswith("guidellm_benchmark:"):
        _, name, repeat = worker.split(":", 2)
        return f"Running benchmark {name} ({repeat.replace('-', ' ')})"
    return worker.replace("_", " ").capitalize()


def _elapsed(seconds: float) -> str:
    minutes, remainder = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"
