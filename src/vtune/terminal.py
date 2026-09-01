"""Timestamped terminal progress with a compact live TTY renderer."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import sys
from threading import Event, RLock, Thread
from time import monotonic

from vtune.config.models import VTuneConfig
from vtune.config.runtime import LOG_LEVELS
from vtune.terminal_style import styled


def with_debug_logging(config: VTuneConfig) -> VTuneConfig:
    return replace(config, logging={**config.logging, "level": "DEBUG"})


class TerminalLogger:
    def __init__(self, level: str) -> None:
        self._threshold = LOG_LEVELS.index(level)
        self._tty = bool(getattr(sys.stdout, "isatty", lambda: False)()) and level != "DEBUG"
        self._started, self._stages, self._drawn = monotonic(), {}, 0
        self._lock, self._stop = RLock(), Event()
        self._thread = Thread(target=self._refresh, daemon=True) if self._tty else None
        if self._thread:
            self._thread.start()

    def close(self) -> float:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        with self._lock:
            self._clear_live()
        return monotonic() - self._started

    def debug(self, message: str) -> None: self._write("DEBUG", message, "dim")
    def info(self, message: str) -> None: self._write("INFO", message)
    def warning(self, message: str) -> None: self._write("WARNING", message, "yellow")

    def experiment(self, values: dict[str, object]) -> None:
        self._write("INFO", "=" * 18 + " vLLM Config Tuner experiment " + "=" * 18, "cyan")
        width = max(map(len, values), default=0)
        self.info("\n".join(f"{name:<{width}}  {value}" for name, value in values.items()))

    def trial(self, position: int, total: int, trial_id: str,
              values: dict[str, object], worker: str | None = None) -> None:
        owner = f" · {worker}" if worker else ""
        self._write(
            "INFO", f"\n{_bar(position, total)} Trial {position} of {total} · {trial_id}{owner}",
            "cyan",
        )
        if values:
            width = max(map(len, values))
            self.info("\n".join(f"{name:<{width}}  {value}" for name, value in values.items()))

    def baseline(self) -> None:
        self.info("\n" + "─" * 18 + " Baseline experiment · fixed configuration " + "─" * 18)

    def stage(self, event: str, worker: str, scope: str | None = None) -> None:
        label, key = _stage_label(worker), f"{scope or ''}:{worker}"
        with self._lock:
            if event == "starting":
                self._stages[key] = (label, scope, monotonic())
                self._render_live()
                return
            label, _, started = self._stages.pop(key, (label, scope, monotonic()))
            self._clear_live()
            icon = "✓" if event == "completed" else "✗"
            tone = "green" if event == "completed" else "red"
            self._write("INFO" if event == "completed" else "WARNING",
                        f"{scope + ' ' if scope else ''}{icon} {label} — {_elapsed(monotonic() - started)}",
                        tone)
            self._render_live()

    def benchmark_score(self, name: str, repeat: int | None, score: float | None) -> None:
        suffix = f" · repeat {repeat}" if repeat is not None else ""
        if score is None:
            self.warning(f"Benchmark {name}{suffix} — no eligible score; all requests failed")
        else:
            self._write("INFO", f"Benchmark {name}{suffix} — score={score:.4f}", "green")

    def benchmark_aggregate(self, name: str, score: float) -> None:
        self._write("INFO", f"Benchmark {name} — repeated score={score:.4f}", "green")

    def session_complete(self, seconds: float) -> None:
        self._write("INFO", f"Session duration: {_elapsed(seconds)}", "green")

    def _refresh(self) -> None:
        while not self._stop.wait(0.12):
            with self._lock:
                self._render_live()

    def _render_live(self) -> None:
        if not self._tty or not self._stages:
            return
        self._clear_live()
        phase = "⠋⠙⠹⠸⠼⠴⠦⠧"[int(monotonic() * 8) % 8]
        for label, scope, started in self._stages.values():
            prefix = f"{scope} " if scope else ""
            print(f"{phase} {prefix}{label} · {_elapsed(monotonic() - started)}", flush=True)
        self._drawn = len(self._stages)

    def _clear_live(self) -> None:
        if self._tty and self._drawn:
            print(f"\033[{self._drawn}A\033[J", end="", flush=True)
            self._drawn = 0

    def _write(self, level: str, message: str, tone: str | None = None) -> None:
        if LOG_LEVELS.index(level) < self._threshold:
            return
        with self._lock:
            self._clear_live()
            stamp = datetime.now().strftime("%H:%M:%S")
            rendered = styled(message, tone, sys.stdout) if tone else message
            print(f"[{stamp} +{_elapsed(monotonic() - self._started)}] {rendered}", flush=True)
            self._render_live()


def _stage_label(worker: str) -> str:
    fixed = {"configuration_builder": "Building configuration", "vllm_runner": "Starting vLLM server",
             "readiness": "Waiting for server readiness", "cleanup": "Stopping owned processes"}
    if worker in fixed:
        return fixed[worker]
    if "_benchmark:" in worker:
        _, name, *repeat = worker.split(":")
        return f"Running benchmark {name}" + (f" ({repeat[0].replace('-', ' ')})" if repeat else "")
    return worker.replace("_", " ").capitalize()


def _elapsed(seconds: float) -> str:
    minutes, remainder = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"


def _bar(position: int, total: int) -> str:
    width, completed = 16, min(position, total)
    filled = round(width * completed / max(total, 1))
    return f"[{('=' * filled).ljust(width, '-')}] {completed}/{total}"
