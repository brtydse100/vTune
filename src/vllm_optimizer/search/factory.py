"""Build and validate the configured search session."""

from pathlib import Path

from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.search.grid import expand_grid
from vllm_optimizer.search.grid_session import GridSearchSession
from vllm_optimizer.search.optuna_session import OptunaSearchSession
from vllm_optimizer.search.strategy import SearchSession


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
    unique = len(expand_grid(config))
    return sampler, min(trials, unique)


def search_warning(config: VTuneConfig) -> str | None:
    sampler, effective = validate_search(config)
    requested = config.optimization.get("trials")
    if sampler != "grid" and isinstance(requested, int) and requested > effective:
        return (f"Requested {requested} trials, but the search space contains only "
                f"{effective} unique configurations; running {effective} trials.")
    return None


def create_search(config: VTuneConfig, directory: Path) -> SearchSession:
    sampler, trials = validate_search(config)
    if sampler == "grid":
        return GridSearchSession(config)
    return OptunaSearchSession(config, directory, sampler, trials)
