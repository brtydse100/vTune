"""Action-specific command-line validation."""

from __future__ import annotations

from argparse import Namespace


class CLIUsageError(ValueError):
    """A user supplied an invalid combination of command-line options."""


def validate_cli_options(args: Namespace) -> None:
    action = args.action
    if action in (None, "validate"):
        _require(args.config, "--config is required")
        _reject(args.run is not None or args.trial, "--run and --trial require a run command")
        if action == "validate":
            _reject(args.verbose, "--verbose is only valid when running or retrying")
        return
    _reject(args.config is not None, f"--config cannot be used with {action}")
    if action in ("export", "reproduce"):
        _require(args.run is not None, f"{action} requires --run")
        _require(args.trial and len(args.trial) == 1,
                 f"{action} requires exactly one --trial")
        _reject(args.verbose, f"--verbose cannot be used with {action}")
        return
    _require(args.run is not None, "retry requires --run")
    _require(args.trial, "retry requires one or more --trial values")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise CLIUsageError(message)


def _reject(condition: object, message: str) -> None:
    if condition:
        raise CLIUsageError(message)
