"""Load and validate vTune YAML configuration files."""

from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigFileError, ConfigValidationError, ConfigYAMLError
from .models import ExperimentConfig, ModelConfig, ServerConfig, VTuneConfig


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
    "model",
    "server",
    *_OPTIONAL_SECTIONS,
}


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
        return _build_config(raw)
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(f"Invalid configuration: {error}") from error


def _build_config(raw: Any) -> VTuneConfig:
    root = _mapping(raw, "configuration")
    unknown = sorted(set(root) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigValidationError(
            f"Unknown top-level configuration key(s): {', '.join(unknown)}"
        )

    if root.get("schema_version") != 1 or isinstance(
        root.get("schema_version"), bool
    ):
        raise ConfigValidationError("'schema_version' must be 1")

    experiment = _build_experiment(_required_mapping(root, "experiment"))
    model = _build_model(_required_mapping(root, "model"))
    server = _build_server(_required_mapping(root, "server"))
    optional = {
        name: dict(_mapping(root.get(name, {}), f"'{name}'"))
        for name in _OPTIONAL_SECTIONS
    }
    return VTuneConfig(
        schema_version=1,
        experiment=experiment,
        model=model,
        server=server,
        **optional,
    )


def _build_experiment(raw: dict[str, Any]) -> ExperimentConfig:
    _reject_unknown(raw, {"name", "output_dir", "seed"}, "experiment")
    seed = raw.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ConfigValidationError("'experiment.seed' must be an integer")
    return ExperimentConfig(
        name=_nonempty_string(raw.get("name"), "experiment.name"),
        output_dir=_nonempty_string(raw.get("output_dir", "runs"), "experiment.output_dir"),
        seed=seed,
    )


def _build_model(raw: dict[str, Any]) -> ModelConfig:
    _reject_unknown(raw, {"id", "revision"}, "model")
    revision = raw.get("revision")
    if revision is not None:
        revision = _nonempty_string(revision, "model.revision")
    return ModelConfig(id=_nonempty_string(raw.get("id"), "model.id"), revision=revision)


def _build_server(raw: dict[str, Any]) -> ServerConfig:
    fields = {"args", "tune", "env", "tune_env"}
    _reject_unknown(raw, fields, "server")
    mappings = {
        name: dict(_mapping(raw.get(name, {}), f"'server.{name}'"))
        for name in ("args", "tune", "env", "tune_env")
    }
    return ServerConfig(**mappings)


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
