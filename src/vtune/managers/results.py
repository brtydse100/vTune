"""Collection and persistence of completed trial execution data."""

from __future__ import annotations

import json
from pathlib import Path

from vtune.domain.benchmark import BenchmarkResult
from vtune.domain.results import WorkerResult
from vtune.domain.trial_report import TrialReport
from vtune.workers.base import TrialContext


class ResultsManager:
    def __init__(self, output_path: Path) -> None:
        self._output_path = Path(output_path)

    def save(self, context: TrialContext, outcome: WorkerResult[TrialContext]) -> TrialReport:
        report = TrialReport(
            1, context.trial_id, outcome.status,
            tuple(self._benchmark_document(result)
                  for result in self._benchmark_results(context)),
            {key: str(value) for key, value in context.artifacts.items()},
            outcome.failure,
        )
        self._write(report)
        return report

    def summary(self, report: TrialReport) -> str:
        workloads = sum(len(benchmark["workloads"]) for benchmark in report.benchmarks)
        lines = [f"Trial: {report.trial_id} ({report.status.value})",
                 f"Benchmarks: {len(report.benchmarks)} | Workloads: {workloads}"]
        for benchmark in report.benchmarks:
            lines.append(f"  {benchmark['name']}: {len(benchmark['workloads'])} workload(s)")
        if report.failure:
            lines.append(f"Failure: {report.failure.code}: {report.failure.message}")
        lines.append(f"Result: {self._output_path}")
        return "\n".join(lines)

    def _write(self, report: TrialReport) -> None:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._output_path.with_suffix(self._output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self._output_path)

    @staticmethod
    def _benchmark_results(context: TrialContext) -> tuple[BenchmarkResult, ...]:
        values = context.values.get("benchmark_results", ())
        if not isinstance(values, tuple) or any(
            not isinstance(value, BenchmarkResult) for value in values
        ):
            raise ValueError("trial benchmark results have an invalid shape")
        return values

    @staticmethod
    def _benchmark_document(result: BenchmarkResult) -> dict[str, object]:
        return {
            "name": result.run_name, "backend": result.backend,
            "backend_version": result.backend_version,
            "raw_artifact": str(result.raw_artifact),
            "workloads": [
                {"index": item.index, "configuration": item.configuration,
                 "metrics": item.metrics} for item in result.workloads
            ],
        }
