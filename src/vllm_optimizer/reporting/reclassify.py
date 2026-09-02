"""Re-evaluate stored benchmark evidence without launching runtime processes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult
from vllm_optimizer.domain.results import Failure, WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.offline import _load_trial, _read_object
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
    stored = tuple(_load_trial(source, item, warnings) for item in summaries
                   if isinstance(item, Mapping))
    destination = Path(output).resolve() if output else _destination(source)
    if destination == source or destination.exists():
        raise ValueError(f"re-evaluation output must be a new directory: {destination}")
    policy = _policy(source, stored, str(document.get("maximize", "")), maximum)
    trials = tuple(_reclassify(item, policy) for item in stored)
    scores = [_trial_score(source, item, policy) for item in trials]
    valid = [item for item in scores if item is not None]
    baseline_id = _baseline_id(document)
    baseline = next((item for item in valid if item.trial_id == baseline_id), None)
    ranking = policy.rank([item for item in valid if item.trial_id != baseline_id])
    by_benchmark = {name: policy.rank([
        score for trial in trials if (score := _benchmark_score(source, trial, policy, name))
    ]) for name in policy.required_runs}
    destination.mkdir(parents=True)
    result = RunResultsManager(destination / "result.json").save(
        str(document.get("run_id", source.name)), policy.metric, trials, ranking,
        by_benchmark, baseline, status="completed", source_run_id=source.name,
    )
    context = ReportContext(str(document.get("run_id", source.name)), "completed",
                            source_run_id=source.name, benchmark_rankings=by_benchmark,
                            benchmark_names=policy.required_runs,
                            minimum_repeats=policy.minimum_repeats)
    csv_path, html = Reporter(destination, source).write(
        policy.metric, trials, ranking, baseline, context)
    return ReclassifiedReport(destination, result, csv_path, html)


def _policy(run: Path, trials: tuple[TrialReport, ...], metric: str,
            maximum: float) -> ScoringManager:
    if not trials:
        raise ValueError("source run contains no trials")
    benchmark = load_manifest(run, trials[0].trial_id).get("benchmark", {})
    if not isinstance(benchmark, Mapping):
        raise ValueError("source manifest has invalid benchmark policy")
    names = tuple(str(item.get("name")) for item in benchmark.get("runs", ())
                  if isinstance(item, Mapping) and item.get("name"))
    repeats = benchmark.get("min_repeats", 1)
    return ScoringManager(metric, repeats if isinstance(repeats, int) else 1, names, maximum)


def _reclassify(report: TrialReport, policy: ScoringManager) -> TrialReport:
    score = policy.score(_results(report))
    request_failure = report.failure and report.failure.code in {
        "benchmark_requests_incomplete", "benchmark_no_completed_requests"}
    if score is not None and (report.status is WorkerStatus.COMPLETED or request_failure):
        return TrialReport(1, report.trial_id, WorkerStatus.COMPLETED, report.benchmarks,
                           report.artifacts, report.attempts, None, report.execution)
    if report.status is WorkerStatus.COMPLETED:
        failure = Failure("benchmark_requests_incomplete",
                          "Stored requests exceed the selected failure policy")
        return TrialReport(1, report.trial_id, WorkerStatus.FAILED, report.benchmarks,
                           report.artifacts, report.attempts, failure, report.execution)
    return report


def _results(report: TrialReport, name: str | None = None) -> tuple[BenchmarkResult, ...]:
    values = []
    for item in report.benchmarks:
        if name is not None and item.get("name") != name:
            continue
        workloads = item.get("workloads", ())
        if not isinstance(workloads, tuple):
            continue
        parsed = tuple(WorkloadResult(int(value.get("index", 0)),
                                     value.get("configuration", {}), value.get("metrics", {}))
                       for value in workloads if isinstance(value, Mapping))
        if parsed:
            values.append(BenchmarkResult(str(item.get("name", "unknown")),
                          str(item.get("backend", "unknown")),
                          str(item.get("backend_version", "unknown")), parsed,
                          Path(str(item.get("raw_artifact", "."))),
                          item.get("repeat") if isinstance(item.get("repeat"), int) else None,
                          item.get("elapsed_seconds") if isinstance(item.get("elapsed_seconds"), (int, float)) else None))
    return tuple(values)


def _trial_score(run: Path, report: TrialReport, policy: ScoringManager) -> TrialScore | None:
    value = policy.score(_results(report)) if report.status is WorkerStatus.COMPLETED else None
    if value is None:
        return None
    manifest = load_manifest(run, report.trial_id)
    parameters = manifest.get("parameters", {})
    selected_args = parameters.get("selected_args", {}) if isinstance(parameters, Mapping) else {}
    selected_env = parameters.get("selected_env", {}) if isinstance(parameters, Mapping) else {}
    quality = policy.quality(_results(report))
    return TrialScore(report.trial_id, value, selected_args, selected_env,
                      quality.successful, quality.errored, quality.incomplete,
                      quality.excluded_workloads)


def _benchmark_score(run: Path, report: TrialReport, policy: ScoringManager,
                     name: str) -> TrialScore | None:
    subset = _results(report, name)
    value = policy.score_each(subset).get(name)
    if value is None or report.status is not WorkerStatus.COMPLETED:
        return None
    score = _trial_score(run, report, policy)
    return TrialScore(report.trial_id, value, score.server_args, score.server_env,
                      score.successful_requests, score.errored_requests,
                      score.incomplete_requests, score.excluded_workloads) if score else None


def _baseline_id(document: Mapping[str, object]) -> str | None:
    value = document.get("baseline")
    return str(value.get("trial_id")) if isinstance(value, Mapping) else None


def _destination(run: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return run / "reclassified" / stamp
