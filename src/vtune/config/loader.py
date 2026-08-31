"""Load and validate vTune YAML configuration files."""

from pathlib import Path
import re
from typing import Any

import yaml

from .errors import ConfigFileError, ConfigValidationError, ConfigYAMLError
from .models import ExperimentConfig, VTuneConfig
from .runtime import logging_level


_OPTIONAL_SECTIONS = (
    "benchmark",
    "baseline",
    "optimization",
    "analysis",
    "timeouts",
    "logging",
    "execution",
)
_TOP_LEVEL_KEYS = {
    "schema_version",
    "experiment",
    "server",
    "tune",
    "env",
    "tune_env",
    *_OPTIONAL_SECTIONS,
}
_EXPERIMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def load_config(path: str | Path) -> VTuneConfig:
    """Read *path* and return a validated, typed vTune configuration."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigFileError(f"Cannot read configuration '{source}': {error}") from error

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigYAMLError(f"Invalid YAML in '{source}': {error}") from error

    try:
        return _build_config(raw, source.parent)
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(f"Invalid configuration: {error}") from error


def _build_config(raw: Any, config_directory: Path) -> VTuneConfig:
    root = _mapping(raw, "configuration")
    unknown = sorted(set(root) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigValidationError(
            f"Unknown top-level configuration key(s): {', '.join(unknown)}"
        )

    schema_version = root.get("schema_version", 1)
    if schema_version != 1 or isinstance(schema_version, bool):
        raise ConfigValidationError("'schema_version' must be 1")

    experiment = _build_experiment(_required_mapping(root, "experiment"))
    server = _build_server(_required_mapping(root, "server"), config_directory)
    tune = dict(_mapping(root.get("tune", {}), "'tune'"))
    env = dict(_mapping(root.get("env", {}), "'env'"))
    tune_env = dict(_mapping(root.get("tune_env", {}), "'tune_env'"))
    if "model" in tune:
        raise ConfigValidationError("'server.model' cannot be tuned")
    optional = {
        name: dict(_mapping(root.get(name, {}), f"'{name}'"))
        for name in _OPTIONAL_SECTIONS
    }
    config = VTuneConfig(
        schema_version=1,
        experiment=experiment,
        server=server,
        tune=tune,
        env=env,
        tune_env=tune_env,
        **optional,
    )
    logging_level(config)
    return config


def _build_experiment(raw: dict[str, Any]) -> ExperimentConfig:
    _reject_unknown(raw, {"name", "output_dir", "seed"}, "experiment")
    seed = raw.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ConfigValidationError("'experiment.seed' must be an integer")
    name = _nonempty_string(raw.get("name"), "experiment.name")
    if not _EXPERIMENT_NAME.fullmatch(name):
        raise ConfigValidationError(
            "'experiment.name' must use only letters, numbers, '_' or '-'"
        )
    return ExperimentConfig(
        name=name,
        output_dir=_nonempty_string(raw.get("output_dir", "runs"), "experiment.output_dir"),
        seed=seed,
    )


def _build_server(raw: dict[str, Any], config_directory: Path) -> dict[str, Any]:
    configured = Path(_nonempty_string(raw.get("model"), "server.model")).expanduser()
    resolved = configured if configured.is_absolute() else config_directory / configured
    resolved = resolved.resolve()
    if not resolved.is_dir():
        raise ConfigValidationError(f"'server.model' is not a directory: {resolved}")
    return {**raw, "model": str(resolved)}


def _required_mapping(root: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in root:
        raise ConfigValidationError(f"Missing required section '{name}'")
    return _mapping(root[name], f"'{name}'")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{label} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ConfigValidationError(f"{label} keys must be strings")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"'{label}' must be a non-empty string")
    return value


def _reject_unknown(raw: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ConfigValidationError(
            f"Unknown key(s) in '{section}': {', '.join(unknown)}"
        )
