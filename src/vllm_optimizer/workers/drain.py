"""Verify that the vLLM scheduler is idle after a benchmark."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic
from urllib.request import urlopen

from vllm_optimizer.domain.results import Failure, WorkerResult
from vllm_optimizer.workers.attempts import attempt_directory
from vllm_optimizer.workers.base import TrialContext

MetricsProbe = Callable[[str, float], Awaitable[str]]
_METRICS = ("vllm:num_requests_running", "vllm:num_requests_waiting")


async def http_metrics_probe(url: str, timeout: float) -> str:
    def request() -> str:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8")

    return await asyncio.to_thread(request)


class VLLMDrainWorker:
    """Poll vLLM metrics until every scheduler engine is idle."""

    name = "server_drain"

    def __init__(
        self, artifacts: Path, run_name: str, grace: float = 15.0,
        poll_interval: float = 0.25, request_timeout: float = 1.0,
        metrics_probe: MetricsProbe = http_metrics_probe,
        repeat_index: int | None = None, warmup_index: int | None = None,
    ) -> None:
        if grace < 0 or poll_interval <= 0 or request_timeout <= 0:
            raise ValueError("drain grace must be non-negative; poll and request timeouts positive")
        if repeat_index is not None and warmup_index is not None:
            raise ValueError("drain repeat and warmup cannot both be set")
        self._artifacts, self._run_name = Path(artifacts), run_name
        self._grace, self._poll_interval = grace, poll_interval
        self._request_timeout, self._probe = request_timeout, metrics_probe
        self._repeat_index = repeat_index
        self._warmup_index = warmup_index

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        endpoint = context.values.get("server_endpoint")
        if not isinstance(endpoint, str):
            return WorkerResult.failed(Failure("drain_endpoint_missing", "Missing server endpoint"))
        evidence_path = self._evidence_path(context)
        metrics_url = f"{endpoint.rstrip('/')}/metrics"
        evidence: dict[str, object] = {
            "metrics_url": metrics_url, "metrics": list(_METRICS), "samples": [],
        }
        context.artifacts[self._artifact_key()] = str(evidence_path)
        deadline = monotonic() + self._grace
        while True:
            try:
                timeout = max(0.1, min(self._request_timeout, deadline - monotonic()))
                text = await asyncio.wait_for(self._probe(metrics_url, timeout), timeout=timeout)
                values = _read_metrics(text)
            except Exception as error:
                evidence.update({"status": "unavailable", "error": str(error)})
                self._save(evidence_path, evidence)
                return WorkerResult.failed(Failure(
                    "drain_metrics_unavailable",
                    f"Could not read vLLM drain metrics: {error}; evidence: {evidence_path}",
                ))
            sample = {
                "elapsed_seconds": max(0.0, self._grace - max(0.0, deadline - monotonic())),
                **values,
            }
            samples = evidence["samples"]
            assert isinstance(samples, list)
            samples.append(sample)
            if values["running"] == 0 and values["waiting"] == 0:
                evidence.update({"status": "drained", "final": sample})
                self._save(evidence_path, evidence)
                return WorkerResult.completed()
            remaining = deadline - monotonic()
            if remaining <= 0:
                evidence.update({"status": "busy", "final": sample})
                self._save(evidence_path, evidence)
                return WorkerResult.failed(Failure(
                    "server_drain_timeout",
                    f"vLLM remained busy after {self._grace:g}s: "
                    f"running={values['running']}, waiting={values['waiting']}; "
                    f"evidence: {evidence_path}",
                ))
            await asyncio.sleep(min(self._poll_interval, remaining))

    async def cleanup(self, context: TrialContext) -> None:
        """The drain worker owns no process resources."""

    def _evidence_path(self, context: TrialContext) -> Path:
        directory = attempt_directory(self._artifacts, context)
        if self._warmup_index:
            directory /= "warmups" / f"{self._warmup_index:03d}"
        elif self._repeat_index:
            directory /= "repeats" / f"{self._repeat_index:03d}"
        return directory / self._run_name / "drain.json"

    def _artifact_key(self) -> str:
        suffix = (f"_warmup_{self._warmup_index}" if self._warmup_index
                  else f"_repeat_{self._repeat_index}" if self._repeat_index else "")
        return f"benchmark_{self._run_name}{suffix}_drain"

    @staticmethod
    def _save(path: Path, evidence: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def _read_metrics(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for metric in _METRICS:
        samples = []
        for line in text.splitlines():
            fields = line.strip().split(maxsplit=1)
            if len(fields) != 2 or not _matches(fields[0], metric):
                continue
            try:
                value = float(fields[1].split(maxsplit=1)[0])
            except (TypeError, ValueError) as error:
                raise ValueError(f"invalid {metric} sample") from error
            if value < 0 or not value < float("inf"):
                raise ValueError(f"invalid {metric} value")
            samples.append(value)
        if not samples:
            raise ValueError(f"missing {metric} metric")
        values["running" if metric.endswith("running") else "waiting"] = sum(samples)
    return values


def _matches(value: str, metric: str) -> bool:
    return value == metric or value.startswith(f"{metric}{{")
