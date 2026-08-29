"""Owned subprocess lifecycle used by execution workers."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import IO, Mapping


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    """A subprocess command and its isolated launch settings."""

    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: Path | None = None

    def __post_init__(self) -> None:
        argv = tuple(self.argv)
        if not argv or not argv[0]:
            raise ValueError("argv must contain a non-empty executable")
        if not all(isinstance(argument, str) for argument in argv):
            raise TypeError("argv values must be strings")
        environment = dict(self.env)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in environment.items()
        ):
            raise TypeError("environment keys and values must be strings")
        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "env", MappingProxyType(environment))
        if self.cwd is not None:
            object.__setattr__(self, "cwd", Path(self.cwd))


class ManagedProcess:
    """A process whose lifetime and log file are owned by vTune."""

    def __init__(
        self, process: asyncio.subprocess.Process, log: IO[str],
        mirror: asyncio.Task[None] | None = None,
    ) -> None:
        self._process = process
        self._log = log
        self._mirror = mirror

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def wait(self) -> int:
        returncode = await self._process.wait()
        try:
            if self._mirror is not None:
                await self._mirror
        finally:
            self._close_log()
        return returncode

    async def stop(self, grace_period: float = 5.0) -> int:
        if grace_period < 0:
            raise ValueError("grace_period must not be negative")
        if self.returncode is not None:
            return await self.wait()
        self._signal_group(force=False)
        try:
            return await asyncio.wait_for(self.wait(), timeout=grace_period)
        except TimeoutError:
            self._signal_group(force=True)
            return await self.wait()

    def _signal_group(self, *, force: bool) -> None:
        if self.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(self.pid, signal.SIGKILL if force else signal.SIGTERM)
            elif force:
                self._process.kill()
            else:
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
        except (ProcessLookupError, PermissionError):
            return
        except (OSError, ValueError):
            if not force and self.returncode is None:
                self._process.terminate()

    def _close_log(self) -> None:
        if not self._log.closed:
            self._log.close()


class ProcessRunner:
    """Starts subprocesses without a shell in a dedicated process group."""

    def __init__(self, stream: bool = False, label: str = "process") -> None:
        self._stream = stream
        self._label = label

    async def start(self, spec: ProcessSpec, log_path: Path) -> ManagedProcess:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("w", encoding="utf-8")
        environment = os.environ.copy()
        environment.update(spec.env)
        ownership = (
            {"start_new_session": True}
            if os.name == "posix"
            else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *spec.argv,
                cwd=spec.cwd,
                env=environment,
                stdout=asyncio.subprocess.PIPE if self._stream else log,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024 * 1024,
                **ownership,
            )
        except BaseException:
            log.close()
            raise
        mirror = None
        if self._stream:
            assert process.stdout is not None
            mirror = asyncio.create_task(_mirror_output(process.stdout, log, self._label))
        return ManagedProcess(process, log, mirror)


async def _mirror_output(
    stream: asyncio.StreamReader, log: IO[str], label: str,
) -> None:
    while line := await stream.readline():
        text = line.decode("utf-8", errors="replace")
        log.write(text)
        log.flush()
        print(f"[{label}] {text}", end="", flush=True)
