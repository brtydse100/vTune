"""Command-line entry point for vTune."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from vtune.config.errors import ConfigError
from vtune.config.loader import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vtune",
        description="Experiment with vLLM serving configurations.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser(
        "validate",
        help="Validate an experiment configuration without starting vLLM.",
    )
    validate.add_argument("--config", "-c", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            config = load_config(args.config)
        except ConfigError as error:
            print(f"Configuration error: {error}", file=sys.stderr)
            return 2

        print(f"Configuration valid: {config.experiment.name}")
        print(f"Model: {config.model.id}")
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2
