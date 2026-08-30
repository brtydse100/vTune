"""Health-based readiness worker for a locally managed server."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from vtune.domain.results import Failure, WorkerResult
from vtune.reproduction.models import StartupRecord
from vtune.workers.base import TrialContext
from vtune.workers.failure_details import classified_failure
from vtune.workers.process import ManagedProcess

HealthProbe = Callable[[str, float], Awaitable[bool]]


async def http_health_probe(url: str, timeout: float) -> bool:
    """Return whether an HTTP endpoint responds with a successful status."""

    def request() -> bool:
        try:
            with urlopen(url, timeout=timeout) as response:
                return HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    return await asyncio.to_thread(request)


class ReadinessWorker:
    """Poll server health while watching for early process termination."""

    name = "readiness"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        path: str = "/health",
        startup_timeout: float = 900.0,
        poll_interval: float = 0.5,
        request_timeout: float = 2.0,
        health_probe: HealthProbe = http_health_probe,
    ) -> None:
        if startup_timeout <= 0 or poll_interval <= 0 or request_timeout <= 0:
            raise ValueError("readiness timeouts and poll interval must be positive")
        self._endpoint = f"http://{host}:{port}"
        self._health_url = f"{self._endpoint}/{path.lstrip('/')}"
        self._startup_timeout = startup_timeout
        self._poll_interval = poll_interval
        self._request_timeout = request_timeout
        self._health_probe = health_probe

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        marker = context.values.get("vllm_started_at")
        started = float(marker) if isinstance(marker, int | float) else monotonic()
        process = context.values.get("server_process")
        if not isinstance(process, ManagedProcess):
            return WorkerResult.failed(
                Failure("server_exited_early", "No managed server process is available")
            )

        try:
            return await self._wait_until_ready(process, context)
        finally:
            context.startups.append(StartupRecord(
                int(context.values.get("attempt_index", 1)), monotonic() - started,
            ))

    async def _wait_until_ready(
        self, process: ManagedProcess, context: TrialContext,
    ) -> WorkerResult[None]:
        deadline = monotonic() + self._startup_timeout
        while True:
            if process.returncode is not None:
                return self._early_exit(process.returncode, context)
            remaining = deadline - monotonic()
            if remaining <= 0:
                log_path = Path(str(context.artifacts.get("vllm_log", "")))
                return WorkerResult.failed(classified_failure(
                    log_path, "server_startup_timeout",
                    f"vLLM startup timed out after {self._startup_timeout:g}s; "
                    f"process is alive; health endpoint {self._health_url} was not ready; "
                    f"full log: {log_path}", True,
                ))
            probe_timeout = min(self._request_timeout, remaining)
            try:
                healthy = await asyncio.wait_for(
                    self._health_probe(self._health_url, probe_timeout),
                    timeout=probe_timeout,
                )
            except TimeoutError:
                healthy = False
            if process.returncode is not None:
                return self._early_exit(process.returncode, context)
            if healthy:
                context.values["server_endpoint"] = self._endpoint
                return WorkerResult.completed()
            remaining = deadline - monotonic()
            if remaining > 0:
                await asyncio.sleep(min(self._poll_interval, remaining))

    async def cleanup(self, context: TrialContext) -> None:
        """Readiness owns no resources."""

    @staticmethod
    def _early_exit(returncode: int, context: TrialContext) -> WorkerResult[None]:
        log_path = context.artifacts.get("vllm_log", "")
        return WorkerResult.failed(
            classified_failure(
                Path(str(log_path)), "server_exited_early",
                f"vLLM exited before becoming ready (code {returncode})",
            )
        )
