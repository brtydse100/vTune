"""Optional OpenAI-compatible report summaries with name-based redaction."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import ipaddress
import json
import os
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reproduction.redaction import redact_values


@dataclass(frozen=True, slots=True)
class LLMSettings:
    base_url: str
    model: str
    api_key_env: str
    timeout: float


_MAX_RESPONSE_BYTES = 1024 * 1024


def settings(config: VTuneConfig) -> LLMSettings | None:
    if not config.analysis:
        return None
    unknown = set(config.analysis) - {"llm_summary", "drift_threshold"}
    if unknown:
        raise ValueError(f"unknown analysis setting(s): {', '.join(sorted(unknown))}")
    drift = config.analysis.get("drift_threshold", 0.05)
    if isinstance(drift, bool) or not isinstance(drift, int | float) or drift < 0:
        raise ValueError("analysis.drift_threshold must be a non-negative number")
    raw = config.analysis.get("llm_summary")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) - {"base_url", "model", "api_key_env", "timeout"}:
        raise ValueError("analysis.llm_summary supports base_url, model, api_key_env, and timeout")
    base_url, model, api_key_env = (raw.get(name) for name in ("base_url", "model", "api_key_env"))
    if not all(isinstance(value, str) and value.strip() for value in (base_url, model, api_key_env)):
        raise ValueError("analysis.llm_summary requires non-empty base_url, model, and api_key_env")
    base_url = _validated_base_url(base_url)
    timeout = raw.get("timeout", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
        raise ValueError("analysis.llm_summary.timeout must be a positive number")
    return LLMSettings(base_url, model, api_key_env, float(timeout))


def generate(settings: LLMSettings, metric: str, ranking: tuple[TrialScore, ...]) -> str:
    key = os.environ.get(settings.api_key_env)
    if not key:
        raise ValueError(f"Set environment variable {settings.api_key_env} to enable the LLM summary")
    rows = [{"trial": item.trial_id, "score": item.value,
             "changes": redact_values(item.server_args), "error_rate": item.error_rate}
            for item in ranking[:5]]
    prompt = ("Summarize this local vLLM tuning outcome in at most five factual bullet points. "
              f"Objective: maximize {metric}. Data: {json.dumps(rows, default=str)}")
    body = json.dumps({"model": settings.model, "messages": [
        {"role": "user", "content": prompt},
    ], "temperature": 0}).encode()
    request = Request(f"{settings.base_url}/chat/completions", body, {
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=settings.timeout) as response:
            payload = _response_json(response)
    except (URLError, OSError) as error:
        raise ValueError("LLM summary unavailable") from error
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM summary response had no chat completion content") from error
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM summary response was empty")
    return content.strip()[:4000]


def _validated_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("analysis.llm_summary.base_url must be an HTTP(S) URL with a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("analysis.llm_summary.base_url must not contain credentials, a query, or a fragment")
    if parsed.scheme == "http" and not _loopback(parsed.hostname):
        raise ValueError("analysis.llm_summary.base_url requires HTTPS except for loopback hosts")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _response_json(response: object) -> object:
    read = getattr(response, "read")
    data = read(_MAX_RESPONSE_BYTES + 1)
    if len(data) > _MAX_RESPONSE_BYTES:
        raise ValueError("LLM summary response exceeded the size limit")
    try:
        return json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("LLM summary response was not valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise ValueError("LLM summary response was not valid JSON") from error


async def summarize(config: VTuneConfig, metric: str, ranking: tuple[TrialScore, ...]) -> tuple[str | None, str | None]:
    configured = settings(config)
    if configured is None:
        return None, None
    try:
        return await asyncio.to_thread(generate, configured, metric, ranking), None
    except ValueError as error:
        return None, str(error)
