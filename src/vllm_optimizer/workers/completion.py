"""Strict request-completion validation shared by benchmark workers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard, cast

from vllm_optimizer.domain.results import Failure


def completed_requests(result: object) -> bool:
    for workload in getattr(result, "workloads", ()):
        metrics = getattr(workload, "metrics", {})
        totals = metrics.get("request_totals", {}) if isinstance(metrics, Mapping) else {}
        if not isinstance(totals, Mapping) or "successful" not in totals:
            return True
        if _valid_count(totals.get("successful")) and totals["successful"] > 0:
            return True
    return False


def max_requests(run: Mapping[str, object]) -> tuple[bool, int | None]:
    constraints = run.get("constraints", [])
    if not isinstance(constraints, list):
        return False, None
    for constraint in constraints:
        if isinstance(constraint, Mapping) and constraint.get("kind") == "max_requests":
            count = constraint.get("count")
            valid = isinstance(count, int) and not isinstance(count, bool) and count > 0
            return True, count if valid else None
    return False, None


def reported_request_total(result: object) -> int | None:
    workloads = getattr(result, "workloads", ())
    totals = {
        metrics.get("request_total")
        for workload in workloads
        if isinstance((metrics := getattr(workload, "metrics", {})), Mapping)
        and isinstance(metrics.get("request_total"), int)
        and not isinstance(metrics.get("request_total"), bool)
    }
    return totals.pop() if len(totals) == 1 else None


def observed_requests(result: object) -> int:
    total = 0
    for workload in getattr(result, "workloads", ()):
        metrics = getattr(workload, "metrics", {})
        totals = metrics.get("request_totals") if isinstance(metrics, Mapping) else None
        if isinstance(totals, Mapping):
            total += sum(
                value for name in ("successful", "errored", "incomplete") if _valid_count(value := totals.get(name))
            )
    return total


def request_count_failure(
    result: object, expected: int | None, backend: str = "GuideLLM", max_failure_percentage: float = 0
) -> Failure | None:
    if expected is None or expected <= 0:
        return Failure("benchmark_request_total_missing", f"{backend} benchmark is missing a positive request total")
    workloads = getattr(result, "workloads", ())
    if not workloads:
        return Failure(
            "benchmark_request_total_missing",
            f"{backend} result contains no workload metrics; it cannot be scored safely",
        )
    for workload in workloads:
        failure = _workload_failure(getattr(workload, "metrics", {}), expected, backend, max_failure_percentage)
        if failure is not None:
            return failure
    return None


def _workload_failure(metrics: object, expected: int, backend: str, max_failure_percentage: float) -> Failure | None:
    totals = metrics.get("request_totals") if isinstance(metrics, Mapping) else None
    request_total = metrics.get("request_total") if isinstance(metrics, Mapping) else None
    if not isinstance(totals, Mapping) or not _valid_count(request_total):
        return Failure(
            "benchmark_request_total_missing",
            f"{backend} result is missing the normalized request total; it cannot be scored safely",
        )
    successful, errored, incomplete = (totals.get("successful"), totals.get("errored"), totals.get("incomplete"))
    if not all(_valid_count(value) for value in (successful, errored, incomplete)):
        return Failure("benchmark_request_totals_invalid", f"{backend} result has invalid normalized request totals")
    successful, errored, incomplete = cast(int, successful), cast(int, errored), cast(int, incomplete)
    observed = successful + errored + incomplete
    failure_percentage = 100 * (errored + incomplete) / observed if observed else 100
    if (
        request_total != expected
        or observed != expected
        or not successful
        or failure_percentage > max_failure_percentage
    ):
        return Failure(
            "benchmark_requests_incomplete",
            f"{backend} benchmark expected {expected} requests with at most "
            f"{max_failure_percentage:g}% failures; observed "
            f"{successful} successful, {errored} errored, {incomplete} incomplete, "
            f"total {request_total} ({failure_percentage:.2f}% failures)",
        )
    return None


def _valid_count(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
