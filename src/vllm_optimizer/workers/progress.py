"""Live benchmark progress derived from the vLLM metrics endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import urlopen

from vllm_optimizer.workers.process import ManagedProcess
from vllm_optimizer.workers.progress_policy import progress_limit as _progress_limit
from vllm_optimizer.workers.progress_policy import request_count as _request_count
from vllm_optimizer.workers.progress_policy import request_path as _request_path
from vllm_optimizer.workers.progress_policy import setup_requests as _setup_requests

ProgressCallback = Callable[[str, int | None, float, float], None]
MetricsProbe = Callable[[str], Awaitable[str]]


async def http_metrics_probe(url: str) -> str:
    def request() -> str:
        with urlopen(url, timeout=1.0) as response:
            return response.read().decode("utf-8", errors="replace")

    return await asyncio.to_thread(request)


class BenchmarkProgress:
    def __init__(
        self,
        engine: str,
        run: Mapping[str, object],
        worker: str,
        callback: ProgressCallback | None,
        probe: MetricsProbe = http_metrics_probe,
    ) -> None:
        self._kind, self._limit = _progress_limit(engine, run)
        self._path = _request_path(engine, run)
        self._offset = _setup_requests(engine, run)
        self._worker, self._callback, self._probe = worker, callback, probe
        self._metrics_url: str | None = None
        self._baseline: int | None = None
        self._started = monotonic()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def prepare(self, endpoint: str) -> None:
        if self._kind != "requests":
            return
        parsed = urlsplit(endpoint)
        self._metrics_url = f"{parsed.scheme}://{parsed.netloc}/metrics"
        self._baseline = await self._count()

    def start(self, process: ManagedProcess) -> None:
        if self._kind:
            self._started = monotonic()
            self._task = asyncio.create_task(self._run(process))

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    def complete(self, process: ManagedProcess, requests: int | None = None) -> None:
        """Emit an exact final value when polling missed a fast benchmark."""
        current = min(int(self._limit), requests) if requests is not None else None
        elapsed = monotonic() - self._started
        if hasattr(process, "write_log"):
            self._emit(process, current, elapsed)
        elif self._callback:
            self._callback(self._worker, current, elapsed, self._limit)

    async def _run(self, process: ManagedProcess) -> None:
        while not self._stop.is_set():
            elapsed = monotonic() - self._started
            current = await self._count() if self._kind == "requests" else None
            if current is not None and self._baseline is not None:
                current = max(0, min(int(self._limit), current - self._baseline - self._offset))
            self._emit(process, current, elapsed)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.0)
            except TimeoutError:
                pass

    def _emit(self, process: ManagedProcess, current: int | None, elapsed: float) -> None:
        reported = -1 if self._kind == "requests" and current is None else current
        if self._callback:
            self._callback(self._worker, reported, elapsed, self._limit)
        shown = f"{current if current is not None else '?'}/{int(self._limit)} requests"
        if self._kind == "time":
            shown = f"{int(elapsed):02d}/{int(self._limit):02d}s"
        if hasattr(process, "write_log"):
            process.write_log(f"\n[vllm-optimizer] Progress: {shown}\n")

    async def _count(self) -> int | None:
        if not self._metrics_url:
            return None
        try:
            return _request_count(await self._probe(self._metrics_url), self._path)
        except Exception:
            return None
