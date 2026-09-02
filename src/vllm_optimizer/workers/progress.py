"""Live benchmark progress derived from the vLLM metrics endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import re
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import urlopen

from vllm_optimizer.benchmarks.timing import parse_duration
from vllm_optimizer.workers.process import ManagedProcess

ProgressCallback = Callable[[str, int | None, float, float], None]
MetricsProbe = Callable[[str], Awaitable[str]]
_SAMPLE = re.compile(r"^(?P<name>[^\s{]+)(?:\{(?P<labels>.*)\})?\s+"
                     r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$")


async def http_metrics_probe(url: str) -> str:
    def request() -> str:
        with urlopen(url, timeout=1.0) as response:
            return response.read().decode("utf-8", errors="replace")
    return await asyncio.to_thread(request)


class BenchmarkProgress:
    def __init__(
        self, engine: str, run: Mapping[str, object], worker: str,
        callback: ProgressCallback | None, probe: MetricsProbe = http_metrics_probe,
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
                current = max(0, min(
                    int(self._limit), current - self._baseline - self._offset,
                ))
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


def _request_count(text: str, path: str) -> int | None:
    http_total = success_total = 0.0
    found_http = found_success = False
    for line in text.splitlines():
        match = _SAMPLE.match(line)
        if not match:
            continue
        name, labels, value = match.group("name", "labels", "value")
        if (name == "http_requests_total" and f'handler="{path}"' in (labels or "")
                and 'method="POST"' in (labels or "")):
            http_total, found_http = http_total + float(value), True
        elif name == "vllm:request_success_total":
            success_total, found_success = success_total + float(value), True
    return int(http_total if found_http else success_total) if found_http or found_success else None


def _progress_limit(engine: str, run: Mapping[str, object]) -> tuple[str | None, float]:
    if engine == "vllm":
        args = run.get("args", {})
        value = args.get("num_prompts", args.get("num-prompts")) if isinstance(args, Mapping) else None
        return ("requests", float(value)) if isinstance(value, int) and value > 0 else (None, 0)
    constraints = run.get("constraints", [])
    if isinstance(constraints, list):
        for item in constraints:
            if isinstance(item, Mapping) and item.get("kind") == "max_requests":
                value = item.get("count")
                if isinstance(value, int) and value > 0:
                    return "requests", float(value * _strategy_count(run.get("profile")))
        for item in constraints:
            if isinstance(item, Mapping) and item.get("kind") == "max_duration":
                seconds = item.get("seconds")
                values = seconds if isinstance(seconds, list) else [seconds]
                return "time", sum(parse_duration(value) for value in values) * _strategy_count(run.get("profile"))
    return None, 0


def _strategy_count(profile: object) -> int:
    if not isinstance(profile, Mapping):
        return 1
    for key in ("streams", "rates"):
        if isinstance(value := profile.get(key), list):
            return max(1, len(value))
    value = profile.get("sweep_size")
    return value if isinstance(value, int) and value > 0 else 1


def _request_path(engine: str, run: Mapping[str, object]) -> str:
    if engine == "guidellm":
        return str(run.get("request_format", "/v1/completions"))
    args = run.get("args", {})
    return str(args.get("endpoint", "/v1/completions")) if isinstance(args, Mapping) else "/v1/completions"


def _setup_requests(engine: str, run: Mapping[str, object]) -> int:
    if engine != "vllm" or not isinstance((args := run.get("args", {})), Mapping):
        return 0
    warmups = args.get("num_warmups", args.get("num-warmups", 0))
    initial = int(args.get("ready_check_timeout_sec",
                           args.get("ready-check-timeout-sec", 600)) != 0)
    return initial + (warmups if isinstance(warmups, int) and warmups > 0 else 0)
