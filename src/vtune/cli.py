"""Command-line entry point for vTune."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
import sys

from vtune.config.errors import ConfigError
from vtune.config.loader import load_config
from vtune.cli_options import CLIUsageError, validate_cli_options
from vtune.lifecycle import load_retry_plan
from vtune.orchestrator import Orchestrator
from vtune.reproduction.display import reproduce_trial
from vtune.reproduction.export import export_vllm_command
from vtune.terminal import with_debug_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vtune", description="Experiment with vLLM serving configurations."
    )
    parser.add_argument(
        "action", nargs="?", choices=("validate", "export", "reproduce", "retry"),
        help="Post-run action; omit to start a new experiment.")
    parser.add_argument("--config", "-c", metavar="YAML",
                        help="Experiment YAML for a new run or validation.")
    parser.add_argument("--run", type=Path, metavar="DIRECTORY",
                        help="Existing immutable run directory.")
    parser.add_argument("--trial", action="append", metavar="ID",
                        help="Trial ID; repeat the option when retrying several trials.")
    parser.add_argument("--verbose", action="store_true",
                        help="Override logging.level with DEBUG and stream child logs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_cli_options(args)
        if args.action == "export":
            print(export_vllm_command(args.run, args.trial[0]))
            return 0
        if args.action == "reproduce":
            print(reproduce_trial(args.run, args.trial[0]))
            return 0
        if args.action == "retry":
            plan = load_retry_plan(args.run, args.trial)
            for warning in plan.warnings:
                print(f"Integrity warning: {warning}", file=sys.stderr)
            retry_config = with_debug_logging(plan.config) if args.verbose else plan.config
            outcome = asyncio.run(Orchestrator(
                retry_config, plan.trials, plan.source_run_id, plan.sources,
            ).run())
        else:
            config = load_config(args.config)
            config = with_debug_logging(config) if args.verbose else config
            if args.action == "validate":
                Orchestrator(config).validate()
                print(f"Configuration valid: {config.experiment.name}")
                print(f"Model: {config.model.path}")
                return 0
            outcome = asyncio.run(Orchestrator(config).run())
    except CLIUsageError as error:
        print(f"Command error: {error}", file=sys.stderr)
        return 2
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    except (OSError, TypeError, ValueError) as error:
        print(f"Experiment error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Experiment interrupted", file=sys.stderr)
        return 130
    print(outcome.summary)
    if outcome.status == "interrupted":
        return 130
    completed = any(report.status.value == "completed" for report in outcome.trials)
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
