"""Incremental accumulation and persistence for one immutable run."""

from __future__ import annotations

from typing import Mapping

from vtune.domain.trial_report import TrialReport
from vtune.managers.run_results import RunResultsManager
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.search.grid import TrialParameters


class RunAccumulator:
    def __init__(self, benchmark_names: tuple[str, ...], scoring: ScoringManager) -> None:
        self.reports: list[TrialReport] = []
        self.scores: list[TrialScore] = []
        self.baseline: TrialScore | None = None
        self._benchmark_scores: dict[str, list[TrialScore]] = {
            name: [] for name in benchmark_names
        }
        self._scoring = scoring

    def record(
        self, parameters: TrialParameters, report: TrialReport,
        score: TrialScore | None, by_benchmark: Mapping[str, float],
        *, baseline: bool = False,
    ) -> None:
        self.reports.append(report)
        if baseline:
            self.baseline = score
            return
        if score is not None:
            self.scores.append(score)
        for name, value in by_benchmark.items():
            self._benchmark_scores[name].append(TrialScore(
                parameters.trial_id, value,
                score.server_args if score else {}, score.server_env if score else {},
            ))

    @property
    def ranking(self) -> tuple[TrialScore, ...]:
        return self._scoring.rank(self.scores)

    @property
    def benchmark_rankings(self) -> dict[str, tuple[TrialScore, ...]]:
        return {name: self._scoring.rank(values)
                for name, values in self._benchmark_scores.items()}

    def persist(
        self, manager: RunResultsManager, run_id: str, metric: str,
        status: str, started_at: str, completed_at: str | None,
        source_run_id: str | None,
        sources: Mapping[str, Mapping[str, str]],
    ) -> None:
        manager.save(
            run_id, metric, tuple(self.reports), self.ranking,
            self.benchmark_rankings, self.baseline, status=status,
            started_at=started_at, completed_at=completed_at,
            source_run_id=source_run_id, sources=sources,
        )
