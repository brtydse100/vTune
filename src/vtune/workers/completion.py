"""Strict request-completion validation shared by benchmark workers."""

from __future__ import annotations

from collections.abc import Mapping

from vtune.domain.results import Failure


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


def request_count_failure(
    result: object, expected: int | None, backend: str = "GuideLLM",
) -> Failure | None:
    if expected is None or expected <= 0:
        return Failure(
            "benchmark_request_total_missing",
            f"{backend} benchmark is missing a positive request total",
        )
    workloads = getattr(result, "workloads", ())
    if not workloads:
        return Failure(
            "benchmark_request_total_missing",
            f"{backend} result contains no workload metrics; it cannot be scored safely",
        )
    for workload in workloads:
        failure = _workload_failure(getattr(workload, "metrics", {}), expected, backend)
        if failure is not None:
            return failure
    return None


def _workload_failure(metrics: object, expected: int, backend: str) -> Failure | None:
    totals = metrics.get("request_totals") if isinstance(metrics, Mapping) else None
    request_total = metrics.get("request_total") if isinstance(metrics, Mapping) else None
    if (not isinstance(totals, Mapping) or not _valid_count(request_total)):
        return Failure(
            "benchmark_request_total_missing",
            f"{backend} result is missing the normalized request total; "
            "it cannot be scored safely",
        )
    successful, errored, incomplete = (
        totals.get("successful"), totals.get("errored"), totals.get("incomplete"),
    )
    if not all(_valid_count(value) for value in (successful, errored, incomplete)):
        return Failure(
            "benchmark_request_totals_invalid",
            f"{backend} result has invalid normalized request totals",
        )
    observed = successful + errored + incomplete
    if (request_total != expected or observed != expected or errored or incomplete
            or successful != expected):
        return Failure(
            "benchmark_requests_incomplete",
            f"{backend} benchmark expected {expected} successful requests; observed "
            f"{successful} successful, {errored} errored, {incomplete} incomplete, "
            f"total {request_total}",
        )
    return None


def _valid_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
