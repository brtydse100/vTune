"""Optional, secret-safe OpenAI-compatible report summaries."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from vtune.config.models import VTuneConfig
from vtune.managers.scoring import TrialScore
from vtune.reproduction.redaction import redact_values


@dataclass(frozen=True, slots=True)
class LLMSettings:
    base_url: str
    model: str
    api_key_env: str
    timeout: float


def settings(config: VTuneConfig) -> LLMSettings | None:
    if not config.analysis:
        return None
    unknown = set(config.analysis) - {"llm_summary"}
    if unknown:
        raise ValueError(f"unknown analysis setting(s): {', '.join(sorted(unknown))}")
    raw = config.analysis.get("llm_summary")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) - {"base_url", "model", "api_key_env", "timeout"}:
        raise ValueError("analysis.llm_summary supports base_url, model, api_key_env, and timeout")
    base_url, model, api_key_env = (raw.get(name) for name in ("base_url", "model", "api_key_env"))
    if not all(isinstance(value, str) and value.strip() for value in (base_url, model, api_key_env)):
        raise ValueError("analysis.llm_summary requires non-empty base_url, model, and api_key_env")
    if not base_url.startswith(("https://", "http://")):
        raise ValueError("analysis.llm_summary.base_url must be an HTTP(S) URL")
    timeout = raw.get("timeout", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
        raise ValueError("analysis.llm_summary.timeout must be a positive number")
    return LLMSettings(base_url.rstrip("/"), model, api_key_env, float(timeout))


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
            payload = json.loads(response.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as error:
        raise ValueError(f"LLM summary unavailable: {error}") from error
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM summary response had no chat completion content") from error
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM summary response was empty")
    return content.strip()[:4000]


async def summarize(config: VTuneConfig, metric: str, ranking: tuple[TrialScore, ...]) -> tuple[str | None, str | None]:
    configured = settings(config)
    if configured is None:
        return None, None
    try:
        return await asyncio.to_thread(generate, configured, metric, ranking), None
    except ValueError as error:
        return None, str(error)
