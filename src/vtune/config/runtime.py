"""Validated runtime policy values derived from an experiment configuration."""

from vtune.config.models import VTuneConfig


LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def model_path(config: VTuneConfig) -> str:
    value = config.server.get("model")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("server.model must be a non-empty local model path")
    return value


def logging_level(config: VTuneConfig) -> str:
    unknown = set(config.logging) - {"level"}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown logging setting(s): {names}")
    level = config.logging.get("level", "INFO")
    if not isinstance(level, str) or level.upper() not in LOG_LEVELS:
        raise ValueError("logging.level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return level.upper()


def maximize_metric(config: VTuneConfig) -> str:
    metric = config.optimization.get("maximize")
    if not isinstance(metric, str) or not metric.strip():
        raise ValueError("optimization requires a non-empty 'maximize' metric")
    return metric


def positive(values: object, key: str, default: float) -> float:
    value = values.get(key, default)  # type: ignore[union-attr]
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(f"'{key}' must be a positive number")
    return float(value)


def server_port(config: VTuneConfig) -> int:
    value = config.server.get("port", 8000)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError("server.port must be a valid integer port")
    return value


def max_attempts(config: VTuneConfig) -> int:
    retry = config.execution.get("retry", {})
    if not isinstance(retry, dict):
        raise ValueError("execution.retry must be a mapping")
    value = retry.get("max_attempts", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("execution.retry.max_attempts must be a positive integer")
    return value


def baseline_enabled(config: VTuneConfig) -> bool:
    unknown = set(config.baseline) - {"enabled"}
    enabled = config.baseline.get("enabled", True)
    if unknown or not isinstance(enabled, bool):
        raise ValueError("baseline supports only a boolean 'enabled' setting")
    return enabled
