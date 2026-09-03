"""Incremental accumulation and persistence for one immutable run."""

from __future__ import annotations

from collections.abc import Mapping

from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.search.grid import TrialParameters


class RunAccumulator:
    def __init__(self, benchmark_names: tuple[str, ...], scoring: ScoringManager) -> None:
        self.reports: list[TrialReport] = []
        self.scores: list[TrialScore] = []
        self.baseline: TrialScore | None = None
        self._benchmark_scores: dict[str, list[TrialScore]] = {name: [] for name in benchmark_names}
        self._scoring = scoring

    def record(
        self,
        parameters: TrialParameters,
        report: TrialReport,
        score: TrialScore | None,
        by_benchmark: Mapping[str, float],
        *,
        baseline: bool = False,
    ) -> None:
        self.reports.append(report)
        if baseline:
            self.baseline = score
            return
        if score is not None:
            self.scores.append(score)
        for name, value in by_benchmark.items():
            self._benchmark_scores[name].append(
                TrialScore(
                    parameters.trial_id,
                    value,
                    score.server_args if score else {},
                    score.server_env if score else {},
                    score.successful_requests if score else 0,
                    score.errored_requests if score else 0,
                    score.incomplete_requests if score else 0,
                    score.excluded_workloads if score else 0,
                )
            )

    def replace(
        self,
        parameters: TrialParameters,
        report: TrialReport,
        score: TrialScore | None,
        by_benchmark: Mapping[str, float],
    ) -> None:
        """Replace an initial result with its sequential finalist validation."""
        if not any(item.trial_id == parameters.trial_id for item in self.reports):
            raise ValueError(f"cannot validate unknown trial '{parameters.trial_id}'")
        self.reports = [item for item in self.reports if item.trial_id != parameters.trial_id]
        self.scores = [item for item in self.scores if item.trial_id != parameters.trial_id]
        for name in self._benchmark_scores:
            self._benchmark_scores[name] = [
                item for item in self._benchmark_scores[name] if item.trial_id != parameters.trial_id
            ]
        self.record(parameters, report, score, by_benchmark)

    @property
    def ranking(self) -> tuple[TrialScore, ...]:
        return self._scoring.rank(self.scores)

    @property
    def benchmark_rankings(self) -> dict[str, tuple[TrialScore, ...]]:
        return {name: self._scoring.rank(values) for name, values in self._benchmark_scores.items()}

    def persist(
        self,
        manager: RunResultsManager,
        run_id: str,
        metric: str,
        status: str,
        started_at: str,
        completed_at: str | None,
        source_run_id: str | None,
        sources: Mapping[str, Mapping[str, str]],
        analysis_summary: str | None = None,
        run_failure: Mapping[str, object] | None = None,
    ) -> None:
        manager.save(
            run_id,
            metric,
            tuple(self.reports),
            self.ranking,
            self.benchmark_rankings,
            self.baseline,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            source_run_id=source_run_id,
            sources=sources,
            analysis_summary=analysis_summary,
            run_failure=run_failure,
        )


def run_status(reports: tuple[TrialReport, ...]) -> str:
    if any(report.status is WorkerStatus.INTERRUPTED for report in reports):
        return "interrupted"
    if any(report.status is WorkerStatus.FAILED for report in reports):
        return "completed_with_failures"
    return "completed"
