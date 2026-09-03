"""Build sanitized run-result document fragments."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.analysis import default_metrics
from vllm_optimizer.reproduction.redaction import redact, redact_environment, redact_values


def score_document(score: TrialScore) -> dict[str, object]:
    return {
        "trial_id": score.trial_id,
        "score": score.value,
        "successful_requests": score.successful_requests,
        "errored_requests": score.errored_requests,
        "incomplete_requests": score.incomplete_requests,
        "excluded_workloads": score.excluded_workloads,
        "error_rate": score.error_rate,
        "server_args": redact_values(score.server_args),
        "server_env": redact_environment(strings(score.server_env)),
    }


def strings(values: Mapping[str, object]) -> dict[str, str]:
    return {str(name): str(value) for name, value in values.items()}


def trial_document(report: TrialReport, source: Mapping[str, str] | None = None) -> dict[str, object]:
    failure = None
    if report.failure:
        failure = {
            "code": report.failure.code,
            "message": report.failure.message,
            "retryable": report.failure.retryable,
        }
    document = {
        "trial_id": report.trial_id,
        "status": report.status.value,
        "failure": failure,
        "benchmark_count": len(report.benchmarks),
        "metrics": default_metrics(report),
        "benchmarks": redact(report.to_dict()["benchmarks"]),
    }
    if report.execution:
        document["execution"] = dict(report.execution)
    if source is not None:
        document["source"] = dict(source)
    return document


def status_counts(trials: tuple[TrialReport, ...]) -> dict[str, int]:
    return {
        status: sum(report.status.value == status for report in trials)
        for status in ("completed", "failed", "interrupted")
    }


def improvement(ranking: tuple[TrialScore, ...], baseline: TrialScore | None) -> float | None:
    if not ranking or baseline is None or baseline.value == 0:
        return None
    return (ranking[0].value - baseline.value) / baseline.value * 100


def duration(started_at: str | None, completed_at: str | None) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        return max(0.0, (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds())
    except ValueError:
        return None
