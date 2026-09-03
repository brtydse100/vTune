"""Normalized request-quality summaries for persistence and reporting."""

from __future__ import annotations

from collections.abc import Mapping


def request_quality(metrics: object) -> dict[str, int | float]:
    totals = metrics.get("request_totals") if isinstance(metrics, Mapping) else None
    values = totals if isinstance(totals, Mapping) else {}
    successful = _count(values.get("successful"))
    errored = _count(values.get("errored"))
    incomplete = _count(values.get("incomplete"))
    failed, total = errored + incomplete, successful + errored + incomplete
    return {
        "successful_requests": successful,
        "failed_requests": failed,
        "errored_requests": errored,
        "incomplete_requests": incomplete,
        "total_requests": total,
        "failure_percentage": 100 * failed / total if total else 100.0,
    }


def aggregate_quality(workloads: object) -> dict[str, int | float]:
    summaries = (
        [request_quality(item.get("metrics")) for item in workloads if isinstance(item, Mapping)]
        if isinstance(workloads, (list, tuple))
        else []
    )
    successful = sum(int(item["successful_requests"]) for item in summaries)
    errored = sum(int(item["errored_requests"]) for item in summaries)
    incomplete = sum(int(item["incomplete_requests"]) for item in summaries)
    failed, total = errored + incomplete, successful + errored + incomplete
    return {
        "successful_requests": successful,
        "failed_requests": failed,
        "errored_requests": errored,
        "incomplete_requests": incomplete,
        "total_requests": total,
        "failure_percentage": 100 * failed / total if total else 100.0,
    }


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
