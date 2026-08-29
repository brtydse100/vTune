"""Persistent Optuna-backed Random and TPE search sessions."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import optuna
from optuna.trial import TrialState

from vtune.config.models import VTuneConfig
from vtune.search.grid import TrialParameters
from vtune.search.grid import expand_grid


class OptunaSearchSession:
    def __init__(self, config: VTuneConfig, directory: Path, sampler: str, trials: int) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        seed = config.experiment.seed
        backend = (optuna.samplers.RandomSampler(seed=seed) if sampler == "random"
                   else optuna.samplers.TPESampler(seed=seed))
        self._study = optuna.create_study(
            study_name="vtune", direction="maximize", sampler=backend,
            storage=f"sqlite:///{directory / 'study.db'}", load_if_exists=True,
        )
        self._config = config
        self._total = trials
        self._active: dict[str, optuna.Trial] = {}
        self._space = expand_grid(config)
        self._recover_running_trials()
        self._seen = {
            value for trial in self._study.trials
            if isinstance((value := trial.user_attrs.get("vtune_configuration")), str)
        }

    @property
    def total(self) -> int:
        return self._total

    def suggest(self) -> TrialParameters | None:
        if len(self._seen) >= self._total:
            return None
        while True:
            optuna_trial = self._study.ask()
            arguments = self._suggest_section(optuna_trial, self._config.tune, "arg")
            environment = self._suggest_section(optuna_trial, self._config.tune_env, "env")
            fingerprint = _fingerprint(arguments, environment)
            if fingerprint in self._seen:
                optuna_trial.set_user_attr("vtune_status", "duplicate_skipped")
                self._study.tell(optuna_trial, state=TrialState.PRUNED)
                self._enqueue_remaining()
                continue
            optuna_trial.set_user_attr("vtune_configuration", fingerprint)
            trial = TrialParameters(f"trial-{len(self._seen):04d}", arguments, environment)
            self._seen.add(fingerprint)
            self._active[trial.trial_id] = optuna_trial
            return trial

    def complete(self, trial: TrialParameters, value: float) -> None:
        self._study.tell(self._active.pop(trial.trial_id), value)

    def fail(self, trial: TrialParameters, interrupted: bool = False) -> None:
        optuna_trial = self._active.pop(trial.trial_id)
        if interrupted:
            optuna_trial.set_user_attr("vtune_status", "interrupted")
        self._study.tell(optuna_trial, state=TrialState.FAIL)

    def _recover_running_trials(self) -> None:
        for trial in self._study.trials:
            if trial.state is TrialState.RUNNING:
                self._study.tell(trial.number, state=TrialState.FAIL)

    def _enqueue_remaining(self) -> None:
        remaining = next(
            (trial for trial in self._space
             if _fingerprint(trial.server_args, trial.server_env) not in self._seen),
            None,
        )
        if remaining is None:
            return
        parameters = {
            **{f"arg:{name}": value for name, value in remaining.server_args.items()},
            **{f"env:{name}": value for name, value in remaining.server_env.items()},
        }
        self._study.enqueue_trial(parameters)

    @staticmethod
    def _suggest_section(
        trial: optuna.Trial, definitions: Mapping[str, object], prefix: str,
    ) -> dict[str, object]:
        return {
            name: _suggest(trial, f"{prefix}:{name}", definition, name)
            for name, definition in sorted(definitions.items())
        }


def _suggest(
    trial: optuna.Trial, parameter: str, definition: object, label: str,
) -> object:
    if not isinstance(definition, Mapping):
        raise ValueError(f"'{label}' must be a mapping")
    if set(definition) == {"values"}:
        values = definition["values"]
        if not isinstance(values, list) or not values:
            raise ValueError(f"'{label}.values' must be a non-empty list")
        return trial.suggest_categorical(parameter, values)
    if set(definition) != {"min", "max", "step"}:
        raise ValueError(f"'{label}' requires either values or min/max/step")
    low, high, step = definition["min"], definition["max"], definition["step"]
    if all(isinstance(value, int) and not isinstance(value, bool)
           for value in (low, high, step)):
        return trial.suggest_int(parameter, low, high, step=step)
    return trial.suggest_float(parameter, float(low), float(high), step=float(step))


def _fingerprint(
    arguments: Mapping[str, object], environment: Mapping[str, object],
) -> str:
    return json.dumps([arguments, environment], sort_keys=True, default=repr)
