"""CSV and static HTML generation for a completed run."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore
from vtune.reporting.context import ReportContext
from vtune.reporting.dashboard import render_dashboard


class Reporter:
    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    def write(
        self, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
        context: ReportContext | None = None,
    ) -> tuple[Path, Path]:
        self._directory.mkdir(parents=True, exist_ok=True)
        csv_path = self._directory / "results.csv"
        html_path = self._directory / "report.html"
        self._write_csv(csv_path, ranking)
        html_path.write_text(
            render_dashboard(
                self._directory, metric, trials, ranking, baseline,
                context or ReportContext(),
            ),
            encoding="utf-8",
        )
        return csv_path, html_path

    @staticmethod
    def _write_csv(path: Path, ranking: tuple[TrialScore, ...]) -> None:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=("rank", "trial_id", "score", "server_args", "server_env")
            )
            writer.writeheader()
            for rank, item in enumerate(ranking, start=1):
                writer.writerow({"rank": rank, "trial_id": item.trial_id,
                                 "score": item.value,
                                 "server_args": json.dumps(dict(item.server_args), sort_keys=True),
                                 "server_env": json.dumps(dict(item.server_env), sort_keys=True)})
