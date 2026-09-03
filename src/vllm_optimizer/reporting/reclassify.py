"""Re-evaluate stored benchmark evidence without launching runtime processes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vllm_optimizer.benchmarks.policy import BenchmarkPolicy
from vllm_optimizer.domain.results import Failure, WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.scoring import ScoringManager
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.offline import _benchmark_policy, _load_trial, _read_object
from vllm_optimizer.reporting.reclassify_scores import benchmark_score as _benchmark_score
from vllm_optimizer.reporting.reclassify_scores import results as _results
from vllm_optimizer.reporting.reclassify_scores import trial_score as _trial_score
from vllm_optimizer.reporting.reporter import Reporter
from vllm_optimizer.reproduction.reader import load_manifest


@dataclass(frozen=True, slots=True)
class ReclassifiedReport:
    directory: Path
    result: Path
    csv: Path
    html: Path


def reclassify_run(run: Path, maximum: float, output: Path | None = None) -> ReclassifiedReport:
    if isinstance(maximum, bool) or not 0 <= maximum <= 100:
        raise ValueError("maximum failure percentage must be between 0 and 100")
    source = Path(run).resolve()
    document = _read_object(source / "result.json", "run result")
    summaries = document.get("trials")
    if not isinstance(summaries, list):
        raise ValueError("run result has invalid trials")
    warnings: list[str] = []
    stored = tuple(_load_trial(source, item, warnings) for item in summaries if isinstance(item, Mapping))
    destination = Path(output).resolve() if output else _destination(source)
    if destination == source or destination.exists():
        raise ValueError(f"re-evaluation output must be a new directory: {destination}")
    benchmark_policy = _benchmark_policy(document, source, stored).with_maximum(maximum)
    policy = _policy(source, stored, str(document.get("maximize", "")), benchmark_policy)
    trials = tuple(_reclassify(item, policy) for item in stored)
    scores = [_trial_score(source, item, policy) for item in trials]
    valid = [item for item in scores if item is not None]
    baseline_id = _baseline_id(document)
    baseline = next((item for item in valid if item.trial_id == baseline_id), None)
    ranking = policy.rank([item for item in valid if item.trial_id != baseline_id])
    by_benchmark = {
        name: policy.rank([score for trial in trials if (score := _benchmark_score(source, trial, policy, name))])
        for name in policy.required_runs
    }
    destination.mkdir(parents=True)
    result = RunResultsManager(destination / "result.json", benchmark_policy=benchmark_policy.to_dict()).save(
        str(document.get("run_id", source.name)),
        policy.metric,
        trials,
        ranking,
        by_benchmark,
        baseline,
        status="completed",
        source_run_id=source.name,
    )
    context = ReportContext(
        str(document.get("run_id", source.name)),
        "completed",
        source_run_id=source.name,
        benchmark_rankings=by_benchmark,
        benchmark_names=policy.required_runs,
        minimum_repeats=policy.minimum_repeats,
        drift_threshold=benchmark_policy.drift_threshold,
        maximum_failure_percentage=maximum,
    )
    csv_path, html = Reporter(destination, source).write(policy.metric, trials, ranking, baseline, context)
    return ReclassifiedReport(destination, result, csv_path, html)


def _policy(
    run: Path, trials: tuple[TrialReport, ...], metric: str, benchmark_policy: BenchmarkPolicy
) -> ScoringManager:
    if not trials:
        raise ValueError("source run contains no trials")
    benchmark = load_manifest(run, trials[0].trial_id).get("benchmark", {})
    if not isinstance(benchmark, Mapping):
        raise ValueError("source manifest has invalid benchmark policy")
    names = tuple(
        str(item.get("name")) for item in benchmark.get("runs", ()) if isinstance(item, Mapping) and item.get("name")
    )
    return ScoringManager(metric, benchmark_policy.minimum_repeats, names, benchmark_policy.maximum_failure_percentage)


def _reclassify(report: TrialReport, policy: ScoringManager) -> TrialReport:
    score = policy.score(_results(report))
    request_failure = report.failure and report.failure.code in {
        "benchmark_requests_incomplete",
        "benchmark_no_completed_requests",
    }
    if score is not None and (report.status is WorkerStatus.COMPLETED or request_failure):
        return TrialReport(
            1,
            report.trial_id,
            WorkerStatus.COMPLETED,
            report.benchmarks,
            report.artifacts,
            report.attempts,
            None,
            report.execution,
        )
    if report.status is WorkerStatus.COMPLETED:
        failure = Failure("benchmark_requests_incomplete", "Stored requests exceed the selected failure policy")
        return TrialReport(
            1,
            report.trial_id,
            WorkerStatus.FAILED,
            report.benchmarks,
            report.artifacts,
            report.attempts,
            failure,
            report.execution,
        )
    return report


def _baseline_id(document: Mapping[str, object]) -> str | None:
    value = document.get("baseline")
    return str(value.get("trial_id")) if isinstance(value, Mapping) else None


def _destination(run: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return run / "reclassified" / stamp
