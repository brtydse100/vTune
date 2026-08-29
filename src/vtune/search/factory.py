"""Build and validate the configured search session."""

from pathlib import Path

from vtune.config.models import VTuneConfig
from vtune.search.grid import expand_grid
from vtune.search.grid_session import GridSearchSession
from vtune.search.optuna_session import OptunaSearchSession
from vtune.search.strategy import SearchSession


def validate_search(config: VTuneConfig) -> tuple[str, int]:
    allowed = {"maximize", "sampler", "trials"}
    unknown = set(config.optimization) - allowed
    sampler = config.optimization.get("sampler", "grid")
    trials = config.optimization.get("trials")
    if unknown:
        raise ValueError(f"unknown optimization setting(s): {', '.join(sorted(unknown))}")
    if sampler not in {"grid", "random", "tpe"}:
        raise ValueError("optimization.sampler must be grid, random, or tpe")
    if sampler == "grid":
        if trials is not None:
            raise ValueError("optimization.trials is not used by grid search")
        return sampler, len(expand_grid(config))
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("optimization.trials must be a positive integer")
    expand_grid(config)
    return sampler, trials


def create_search(config: VTuneConfig, directory: Path) -> SearchSession:
    sampler, trials = validate_search(config)
    if sampler == "grid":
        return GridSearchSession(config)
    return OptunaSearchSession(config, directory, sampler, trials)
