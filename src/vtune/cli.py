"""Command-line entry point for vTune."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
import sys

from vtune.config.errors import ConfigError
from vtune.config.loader import load_config
from vtune.lifecycle import load_retry_plan
from vtune.orchestrator import Orchestrator
from vtune.reproduction.export import export_vllm_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vtune", description="Experiment with vLLM serving configurations."
    )
    parser.add_argument("action", nargs="?", choices=("validate", "export", "retry"),
                        help="Validate, export a trial, or omit to run.")
    parser.add_argument("--config", "-c")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--trial", action="append")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "export":
            if args.run is None or not args.trial or len(args.trial) != 1:
                raise ValueError("export requires exactly one --run and --trial")
            print(export_vllm_command(args.run, args.trial[0]))
            return 0
        if args.action == "retry":
            if args.run is None or not args.trial:
                raise ValueError("retry requires --run and one or more --trial values")
            plan = load_retry_plan(args.run, args.trial)
            outcome = asyncio.run(Orchestrator(
                plan.config, plan.trials, plan.source_run_id, plan.sources,
            ).run())
        else:
            if not args.config:
                raise ValueError("--config is required")
            config = load_config(args.config)
            if args.action == "validate":
                Orchestrator(config).validate()
                print(f"Configuration valid: {config.experiment.name}")
                print(f"Model: {config.model.path}")
                return 0
            outcome = asyncio.run(Orchestrator(config).run())
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
