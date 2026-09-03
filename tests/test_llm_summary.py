import asyncio
import json

import pytest

import vllm_optimizer.reporting.llm_summary as module
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.managers.scoring import TrialScore


def _config(summary: object) -> VTuneConfig:
    return VTuneConfig(
        1, ExperimentConfig("summary"), {"model": "demo"}, analysis={"drift_threshold": 0.05, "llm_summary": summary}
    )


def test_summary_settings_validation() -> None:
    valid = module.settings(
        _config({"base_url": "https://example.com/v1/", "model": "small", "api_key_env": "SUMMARY_KEY", "timeout": 2})
    )
    assert valid == module.LLMSettings("https://example.com/v1", "small", "SUMMARY_KEY", 2.0)
    assert module.settings(VTuneConfig(1, ExperimentConfig("none"), {"model": "demo"})) is None

    for value in (
        {},
        {"base_url": "http://example.com", "model": "x", "api_key_env": "KEY"},
        {"base_url": "https://user:pass@example.com", "model": "x", "api_key_env": "KEY"},
        {"base_url": "https://example.com", "model": "x", "api_key_env": "KEY", "timeout": 0},
    ):
        with pytest.raises(ValueError):
            module.settings(_config(value))


def test_generate_and_async_summary_redact_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size=-1):
            return json.dumps({"choices": [{"message": {"content": " factual result "}}]}).encode()

    captured = {}

    def open_request(request, timeout):
        captured["body"] = request.data
        captured["authorization"] = request.headers["Authorization"]
        return Response()

    monkeypatch.setenv("SUMMARY_KEY", "sentinel-key")
    monkeypatch.setattr(module, "urlopen", open_request)
    settings = module.LLMSettings("https://example.com/v1", "small", "SUMMARY_KEY", 1)
    ranking = (TrialScore("trial", 2.0, {"API_KEY": "sentinel-value", "safe": 1}, {}),)

    assert module.generate(settings, "requests_per_second", ranking) == "factual result"
    assert b"sentinel-value" not in captured["body"]
    assert captured["authorization"] == "Bearer sentinel-key"
    assert asyncio.run(
        module.summarize(
            _config({"base_url": "https://example.com/v1", "model": "small", "api_key_env": "SUMMARY_KEY"}),
            "requests_per_second",
            ranking,
        )
    ) == ("factual result", None)


def test_summary_failures_are_bounded_and_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = module.LLMSettings("https://example.com/v1", "small", "MISSING", 1)
    with pytest.raises(ValueError, match="Set environment"):
        module.generate(settings, "metric", ())

    class Large:
        def read(self, size=-1):
            return b"x" * size

    with pytest.raises(ValueError, match="size limit"):
        module._response_json(Large())

    monkeypatch.delenv("MISSING", raising=False)
    config = _config({"base_url": "https://example.com", "model": "x", "api_key_env": "MISSING"})
    summary, error = asyncio.run(module.summarize(config, "metric", ()))
    assert summary is None and error and "MISSING" in error
