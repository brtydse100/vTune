"""Configuration loading errors exposed to callers."""


class ConfigError(Exception):
    """Base class for user-facing configuration errors."""


class ConfigFileError(ConfigError):
    """Raised when the configuration file cannot be read."""


class ConfigYAMLError(ConfigError):
    """Raised when the configuration file is not valid YAML."""


class ConfigValidationError(ConfigError):
    """Raised when parsed YAML does not match the vLLM Optimizer schema."""
