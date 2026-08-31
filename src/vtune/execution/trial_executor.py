"""Execute and persist one resolved trial on an optional local worker slot."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from vtune.config.models import VTuneConfig
from vtune.config.runtime import max_attempts
from vtune.execution.slots import WorkerSlot, execution_mode
from vtune.managers.results import ResultsManager
from vtune.managers.scoring import ScoringManager, TrialScore
from vtune.managers.trial import TrialManager
from vtune.reproduction.manifest import ManifestWriter
from vtune.search.grid import TrialParameters
from vtune.terminal import TerminalLogger
from vtune.workers.base import TrialContext
from vtune.workers.factory import build_trial_workers
from vtune.domain.trial_report import TrialReport
from vtune.domain.benchmark import BenchmarkResult


class TrialExecutor:
    def __init__(
        self, config: VTuneConfig, scoring: ScoringManager,
        terminal: TerminalLogger, manifest: ManifestWriter,
        sources: Mapping[str, Mapping[str, str]],
    ) -> None:
        self._config = config
        self._scoring = scoring
        self._terminal = terminal
        self._manifest = manifest
        self._sources = sources

    async def execute(
        self, directory: Path, parameters: TrialParameters,
        slot: WorkerSlot | None = None,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        trial_dir = directory / "trials" / parameters.trial_id
        context = TrialContext(parameters.trial_id)
        if slot:
            context.artifacts.update({
                "execution_mode": execution_mode(self._config),
                "execution_worker": slot.name,
                "execution_devices": ",".join(map(str, slot.devices)),
                "execution_port": slot.port,
            })
        scope = f"[{slot.name}][{parameters.trial_id}]" if slot else None
        def progress(event: str, name: str) -> None:
            self._terminal.stage(event, name, scope)
            if event == "completed" and "_benchmark:" in name:
                self._benchmark_progress(name, context)
        outcome = await TrialManager(
            build_trial_workers(self._config, parameters, trial_dir, slot),
            max_attempts(self._config), progress,
        ).execute(context)
        manifest_path = trial_dir / "manifest.json"
        result_path = trial_dir / "result.json"
        context.artifacts["manifest"] = str(manifest_path)
        report = ResultsManager(result_path).save(context, outcome)
        context.artifacts["trial_result"] = str(result_path)
        self._manifest.write(
            manifest_path, self._config, parameters, context,
            outcome.status.value, self._sources.get(parameters.trial_id),
        )
        raw = context.values.get("benchmark_results", ())
        results = raw if isinstance(raw, tuple) else ()
        value = self._scoring.score(results)
        by_benchmark = self._scoring.score_each(results)
        quality = self._scoring.quality(results)
        if not quality.successful and quality.errored + quality.incomplete:
            self._terminal.warning(
                "All benchmark requests failed or were incomplete; this trial is excluded from ranking."
            )
        if len(results) > len(by_benchmark):
            for name, score in by_benchmark.items():
                self._terminal.benchmark_aggregate(name, score)
        if value is None or outcome.failure is not None:
            return report, None, {}
        args = {**{name: value for name, value in self._config.server.items()
                   if name != "model"}, **parameters.server_args}
        env = {**self._config.env, **parameters.server_env}
        return report, TrialScore(
            parameters.trial_id, value, args, env, quality.successful,
            quality.errored, quality.incomplete, quality.excluded_workloads,
        ), by_benchmark

    def _benchmark_progress(self, worker: str, context: TrialContext) -> None:
        values = context.values.get("benchmark_results", ())
        if not isinstance(values, tuple) or not values or not isinstance(values[-1], BenchmarkResult):
            return
        result = values[-1]
        score = self._scoring.score_each((result,)).get(result.run_name)
        repeat = int(worker.rsplit("repeat-", 1)[1]) if "repeat-" in worker else None
        self._terminal.benchmark_score(result.run_name, repeat, score)
