"""Command-line entry point for vTune."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
import sys

from vtune.config.errors import ConfigError
from vtune.config.loader import load_config
from vtune.orchestrator import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vtune", description="Experiment with vLLM serving configurations."
    )
    parser.add_argument("action", nargs="?", choices=("validate",),
                        help="Validate without running; omit for a normal experiment.")
    parser.add_argument("--config", "-c", required=True)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.action == "validate":
            Orchestrator(config).validate()
            print(f"Configuration valid: {config.experiment.name}")
            print(f"Model: {config.model.id}")
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
    completed = any(report.status.value == "completed" for report in outcome.trials)
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
