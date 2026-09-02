"""Action-specific command-line validation."""

from __future__ import annotations

from argparse import Namespace


class CLIUsageError(ValueError):
    """A user supplied an invalid combination of command-line options."""


def validate_cli_options(args: Namespace) -> None:
    action = args.action
    failure_percentage = getattr(args, "max_failure_percentage", None)
    accept_any = bool(getattr(args, "accept_any_request_failures", False))
    if action in (None, "validate"):
        _require(args.config, "--config is required")
        _reject(args.run is not None or args.trial, "--run and --trial require a run command")
        if action == "validate":
            _reject(args.verbose, "--verbose is only valid when running or retrying")
        _reject(args.output is not None, "--output is only valid with report")
        _reject(failure_percentage is not None or accept_any,
                "failure policy options are only valid with reclassify")
        return
    _reject(args.config is not None, f"--config cannot be used with {action}")
    if action in ("export", "reproduce"):
        _require(args.run is not None, f"{action} requires --run")
        _require(args.trial and len(args.trial) == 1,
                 f"{action} requires exactly one --trial")
        _reject(args.verbose, f"--verbose cannot be used with {action}")
        _reject(args.output is not None, f"--output cannot be used with {action}")
        _reject(failure_percentage is not None or accept_any,
                f"failure policy options cannot be used with {action}")
        return
    if action == "report":
        _require(args.run is not None, "report requires --run")
        _reject(args.trial, "--trial cannot be used with report")
        _reject(args.verbose, "--verbose cannot be used with report")
        _reject(failure_percentage is not None or accept_any,
                "failure policy options cannot be used with report")
        return
    if action == "reclassify":
        _require(args.run is not None, "reclassify requires --run")
        _reject(args.trial or args.verbose, "--trial and --verbose cannot be used with reclassify")
        chosen = failure_percentage is not None
        _require(chosen != accept_any,
                 "choose exactly one of --max-failure-percentage or --accept-any-request-failures")
        if chosen:
            _require(0 <= failure_percentage <= 100,
                     "--max-failure-percentage must be between 0 and 100")
        return
    _require(args.run is not None, "retry requires --run")
    _require(args.trial, "retry requires one or more --trial values")
    _reject(args.output is not None, "--output cannot be used with retry")
    _reject(failure_percentage is not None or accept_any,
            "failure policy options cannot be used with retry")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise CLIUsageError(message)


def _reject(condition: object, message: str) -> None:
    if condition:
        raise CLIUsageError(message)
