"""CSV and static HTML generation for a completed run."""

from __future__ import annotations

import csv
from html import escape
import json
from pathlib import Path

from vtune.domain.trial_report import TrialReport
from vtune.managers.scoring import TrialScore
from vtune.reporting.analysis import parameter_importance, trial_metric


class Reporter:
    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    def write(
        self, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
    ) -> tuple[Path, Path]:
        self._directory.mkdir(parents=True, exist_ok=True)
        csv_path = self._directory / "results.csv"
        html_path = self._directory / "report.html"
        self._write_csv(csv_path, ranking)
        html_path.write_text(
            self._html(metric, trials, ranking, baseline), encoding="utf-8"
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

    def _html(
        self, metric: str, trials: tuple[TrialReport, ...],
        ranking: tuple[TrialScore, ...], baseline: TrialScore | None,
    ) -> str:
        importance = parameter_importance(ranking)
        best = ranking[0] if ranking else None
        rows = "".join(
            f"<tr><td>{index}</td><td>{escape(item.trial_id)}</td>"
            f"<td>{item.value:.4f}</td><td><code>{escape(json.dumps(dict(item.server_args)))}</code></td></tr>"
            for index, item in enumerate(ranking, start=1)
        )
        bars = "".join(
            f"<div>{escape(name)} <span class='bar' style='width:{value * 60:.1f}%'></span> "
            f"{value:.1%}</div>" for name, value in importance.items()
        ) or "<p>Not enough varied trials to calculate importance.</p>"
        chart = _scatter(trials)
        baseline_text = f"{baseline.value:.4f}" if baseline else "unavailable"
        best_text = f"{best.trial_id} ({best.value:.4f})" if best else "unavailable"
        return f"""<!doctype html><html><head><meta charset='utf-8'><title>vTune report</title>
<style>body{{font:15px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.5rem;border-bottom:1px solid #ddd;text-align:left}}
.bar{{display:inline-block;background:#4f46e5;height:.8rem;min-width:2px}}code{{font-size:12px}}</style></head>
<body><h1>vTune report</h1><p>Maximize: <code>{escape(metric)}</code></p>
<p>Best configuration: <strong>{escape(best_text)}</strong><br>Baseline: {escape(baseline_text)}</p>
<h2>Parameter importance</h2>{bars}<h2>Throughput vs latency</h2>{chart}
<h2>Trial ranking</h2><table><thead><tr><th>Rank</th><th>Trial</th><th>Score</th><th>Arguments</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>"""


def _scatter(trials: tuple[TrialReport, ...]) -> str:
    points = []
    for report in trials:
        throughput = trial_metric(report, "output_tokens_per_second")
        latency = trial_metric(report, "time_to_first_token_ms")
        if throughput is not None and latency is not None:
            points.append((report.trial_id, throughput, latency))
    if not points:
        return "<p>Throughput and latency metrics were not both available.</p>"
    max_x = max(point[1] for point in points) or 1
    max_y = max(point[2] for point in points) or 1
    circles = "".join(
        f"<circle cx='{40 + x / max_x * 520:.1f}' cy='{300 - y / max_y * 250:.1f}' r='5'>"
        f"<title>{escape(name)}: {x:.2f} tok/s, {y:.2f} ms</title></circle>"
        for name, x, y in points
    )
    return ("<svg viewBox='0 0 600 330' role='img' aria-label='Throughput versus latency'>"
            "<path d='M40 20V300H580' fill='none' stroke='#555'/>" + circles +
            "<text x='230' y='325'>output tokens/second</text>"
            "<text x='5' y='15'>TTFT ms</text></svg>")
