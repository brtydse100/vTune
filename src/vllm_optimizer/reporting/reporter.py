"""CSV and static HTML generation for a completed run."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.dashboard import render_dashboard
from vllm_optimizer.reproduction.redaction import redact_environment, redact_values


class Reporter:
    def __init__(self, directory: Path, artifact_directory: Path | None = None) -> None:
        self._directory = Path(directory)
        self._artifact_directory = Path(artifact_directory or directory)

    def write(
        self, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
        context: ReportContext | None = None,
    ) -> tuple[Path, Path]:
        self._directory.mkdir(parents=True, exist_ok=True)
        csv_path = self._directory / "results.csv"
        html_path = self._directory / "report.html"
        safe_ranking = tuple(_redacted(score) for score in ranking)
        safe_baseline = _redacted(baseline) if baseline else None
        self._write_csv(csv_path, safe_ranking)
        html_path.write_text(
            render_dashboard(
                self._artifact_directory, metric, trials, safe_ranking, safe_baseline,
                context or ReportContext(),
            ),
            encoding="utf-8",
        )
        return csv_path, html_path

    @staticmethod
    def _write_csv(path: Path, ranking: tuple[TrialScore, ...]) -> None:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=("rank", "trial_id", "score", "successful_requests",
                                    "errored_requests", "incomplete_requests", "error_rate",
                                    "excluded_workloads", "server_args", "server_env")
            )
            writer.writeheader()
            for rank, item in enumerate(ranking, start=1):
                writer.writerow({"rank": rank, "trial_id": item.trial_id,
                                 "score": item.value,
                                 "successful_requests": item.successful_requests,
                                 "errored_requests": item.errored_requests,
                                 "incomplete_requests": item.incomplete_requests,
                                 "error_rate": item.error_rate,
                                 "excluded_workloads": item.excluded_workloads,
                                 "server_args": json.dumps(dict(item.server_args), sort_keys=True),
                                 "server_env": json.dumps(dict(item.server_env), sort_keys=True)})


def _redacted(score: TrialScore) -> TrialScore:
    environment = {str(name): str(value) for name, value in score.server_env.items()}
    return TrialScore(score.trial_id, score.value, redact_values(score.server_args),
                      redact_environment(environment), score.successful_requests,
                      score.errored_requests, score.incomplete_requests,
                      score.excluded_workloads)
