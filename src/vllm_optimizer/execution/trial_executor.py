"""Execute and persist one resolved trial on an optional local worker slot."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import max_attempts
from vllm_optimizer.execution.slots import WorkerSlot, execution_mode
from vllm_optimizer.managers.results import ResultsManager
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.managers.trial import TrialManager
from vllm_optimizer.reproduction.manifest import ManifestWriter
from vllm_optimizer.search.grid import TrialParameters
from vllm_optimizer.terminal import TerminalLogger
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.factory import build_trial_workers
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.domain.benchmark import BenchmarkResult


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
        slot: WorkerSlot | None = None, artifact_subdirectory: str | None = None,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        trial_dir = directory / "trials" / parameters.trial_id
        if artifact_subdirectory:
            trial_dir /= artifact_subdirectory
        context = TrialContext(parameters.trial_id)
        context.execution["mode"] = execution_mode(self._config)
        if slot:
            context.execution.update({
                "worker": slot.name,
                "devices": list(slot.devices),
                "port": slot.port,
            })
        scope = f"[{slot.name}][{parameters.trial_id}]" if slot else None
        def progress(event: str, name: str) -> None:
            self._terminal.stage(event, name, scope)
            if event == "completed" and "_benchmark:" in name and "warmup" not in name:
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
