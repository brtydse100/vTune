"""Health-based readiness worker for a locally managed server."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from vtune.domain.results import Failure, WorkerResult
from vtune.workers.base import TrialContext
from vtune.workers.process import ManagedProcess

HealthProbe = Callable[[str, float], Awaitable[bool]]


async def http_health_probe(url: str, timeout: float) -> bool:
    """Return whether an HTTP endpoint responds with a successful status."""

    def request() -> bool:
        try:
            with urlopen(url, timeout=timeout) as response:
                return 200 <= response.status < 300
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
        process = context.values.get("server_process")
        if not isinstance(process, ManagedProcess):
            return WorkerResult.failed(
                Failure("server_exited_early", "No managed server process is available")
            )

        deadline = monotonic() + self._startup_timeout
        while True:
            if process.returncode is not None:
                return self._early_exit(process.returncode)
            remaining = deadline - monotonic()
            if remaining <= 0:
                return WorkerResult.failed(
                    Failure(
                        "server_startup_timeout",
                        f"vLLM was not ready after {self._startup_timeout:g} seconds",
                        retryable=True,
                    )
                )

            probe_timeout = min(self._request_timeout, remaining)
            try:
                healthy = await asyncio.wait_for(
                    self._health_probe(self._health_url, probe_timeout),
                    timeout=probe_timeout,
                )
            except TimeoutError:
                healthy = False
            if process.returncode is not None:
                return self._early_exit(process.returncode)
            if healthy:
                context.values["server_endpoint"] = self._endpoint
                return WorkerResult.completed()

            remaining = deadline - monotonic()
            if remaining <= 0:
                continue
            await asyncio.sleep(min(self._poll_interval, remaining))

    async def cleanup(self, context: TrialContext) -> None:
        """Readiness owns no resources."""

    @staticmethod
    def _early_exit(returncode: int) -> WorkerResult[None]:
        return WorkerResult.failed(
            Failure(
                "server_exited_early",
                f"vLLM exited before becoming ready (code {returncode})",
            )
        )
