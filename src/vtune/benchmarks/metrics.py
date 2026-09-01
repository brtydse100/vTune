"""Canonical metric normalization shared by benchmark adapters."""

from __future__ import annotations

from collections.abc import Mapping


_GUIDELLM_METRICS = {
    "requests_per_second": "requests_per_second",
    "output_tokens_per_second": "output_tokens_per_second",
    "total_tokens_per_second": "tokens_per_second",
    "time_to_first_token_ms": "time_to_first_token_ms",
    "time_per_output_token_ms": "time_per_output_token_ms",
    "inter_token_latency_ms": "inter_token_latency_ms",
}
_VLLM_THROUGHPUT = {
    "requests_per_second": ("requests_per_second", "request_throughput"),
    "output_tokens_per_second": ("output_tokens_per_second", "output_throughput"),
    "total_tokens_per_second": ("total_tokens_per_second", "total_token_throughput"),
}
_VLLM_LATENCY = {
    "time_to_first_token_ms": "ttft",
    "time_per_output_token_ms": "tpot",
    "inter_token_latency_ms": "itl",
    "end_to_end_latency_ms": "e2el",
}


def normalize_guidellm_metrics(raw: Mapping[str, object]) -> dict[str, object]:
    """Return GuideLLM metrics with backend-neutral canonical fields."""
    result = dict(raw)
    for canonical, source in _GUIDELLM_METRICS.items():
        if summary := metric_summary(raw.get(source)):
            result[canonical] = summary
    if summary := metric_summary(raw.get("request_latency"), scale=1000.0):
        result["end_to_end_latency_ms"] = summary
    result["request_totals"] = request_totals(raw.get("request_totals"))
    return result


def normalize_vllm_metrics(raw: Mapping[str, object]) -> dict[str, object]:
    """Return vLLM Bench Serve metrics with the same canonical fields."""
    result = dict(raw)
    for canonical, aliases in _VLLM_THROUGHPUT.items():
        value = next((raw[name] for name in aliases if name in raw), None)
        if summary := metric_summary(value):
            result[canonical] = summary
    for canonical, stem in _VLLM_LATENCY.items():
        if summary := _vllm_latency(raw, stem):
            result[canonical] = summary
    result["request_totals"] = request_totals(
        raw.get("request_totals"), completed=raw.get("completed"),
        failed=raw.get("failed"), requested=raw.get("num_prompts"),
    )
    return result


def metric_summary(value: object, scale: float = 1.0) -> dict[str, float]:
    """Extract average, median, and P99 without fabricating absent values."""
    if (number := _number(value)) is not None:
        return {"average": number * scale}
    if not isinstance(value, Mapping):
        return {}
    successful = value.get("successful")
    source = successful if isinstance(successful, Mapping) else value
    result: dict[str, float] = {}
    for target, names in {
        "average": ("average", "mean"),
        "median": ("median", "p50"),
        "p99": ("p99",),
    }.items():
        number = next((_number(source.get(name)) for name in names
                       if _number(source.get(name)) is not None), None)
        if number is not None:
            result[target] = number * scale
    percentiles = source.get("percentiles")
    if isinstance(percentiles, Mapping):
        for target, name in (("median", "p50"), ("p99", "p99")):
            if target not in result and (number := _number(percentiles.get(name))) is not None:
                result[target] = number * scale
    return result


def request_totals(
    value: object, *, completed: object = None, failed: object = None,
    requested: object = None,
) -> dict[str, int]:
    source = value if isinstance(value, Mapping) else {}
    successful = _count(source.get("successful", completed))
    errored = _count(source.get("errored", source.get("failed", failed)))
    incomplete = _count(source.get("incomplete"))
    total = _count(source.get("total", requested))
    return {
        "successful": successful,
        "errored": errored,
        "incomplete": max(incomplete, total - successful - errored),
    }


def _vllm_latency(raw: Mapping[str, object], stem: str) -> dict[str, float]:
    values = {
        "average": raw.get(f"mean_{stem}_ms"),
        "median": raw.get(f"median_{stem}_ms", raw.get(f"p50_{stem}_ms")),
        "p99": raw.get(f"p99_{stem}_ms"),
    }
    return {name: number for name, value in values.items()
            if (number := _number(value)) is not None}


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
