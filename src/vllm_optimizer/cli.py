"""Command-line entry points for vLLM Optimizer."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
import sys

from vllm_optimizer.config.errors import ConfigError
from vllm_optimizer.config.loader import load_config
from vllm_optimizer.config.runtime import model_path
from vllm_optimizer.cli_options import CLIUsageError, validate_cli_options
from vllm_optimizer.lifecycle import load_retry_plan
from vllm_optimizer.orchestrator import Orchestrator
from vllm_optimizer.reporting.offline import regenerate_report
from vllm_optimizer.reproduction.display import reproduce_trial
from vllm_optimizer.reproduction.export import export_vllm_command
from vllm_optimizer.terminal import with_debug_logging
from vllm_optimizer.terminal_style import styled


def build_parser(prog: str = "vllm-opt") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog, description="Benchmark and optimize vLLM serving configurations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Commands:
  {prog} --config experiment.yaml                 Start an experiment
  {prog} validate --config experiment.yaml        Validate configuration only
  {prog} retry --run RUN --trial ID [--trial ID]  Retry selected trial(s)
  {prog} reproduce --run RUN --trial ID           Print a saved trial command
  {prog} export --run RUN --trial ID              Export a vLLM serve command
  {prog} report --run RUN [--output DIRECTORY]    Regenerate an HTML report""",
    )
    parser.add_argument(
        "action", nargs="?", choices=("validate", "export", "reproduce", "retry", "report"),
        help="Post-run action; omit to start a new experiment.")
    parser.add_argument("--config", "-c", metavar="YAML",
                        help="Experiment YAML for a new run or validation.")
    parser.add_argument("--run", type=Path, metavar="DIRECTORY",
                        help="Existing immutable run directory.")
    parser.add_argument("--trial", action="append", metavar="ID",
                        help="Trial ID; repeat the option when retrying several trials.")
    parser.add_argument("--output", type=Path, metavar="DIRECTORY",
                        help="Destination for an offline regenerated report.")
    parser.add_argument("--verbose", action="store_true",
                        help="Override logging.level with DEBUG and stream child logs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return _run(argv, "vllm-opt")


def legacy_main(argv: Sequence[str] | None = None) -> int:
    print(
        "The 'vtune' command is deprecated; use 'vllm-opt' instead.",
        file=sys.stderr,
    )
    return _run(argv, "vtune")


def _run(argv: Sequence[str] | None, prog: str) -> int:
    args = build_parser(prog).parse_args(argv)
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
        elif args.action == "report":
            generated = regenerate_report(args.run, args.output)
            print(f"Offline report regenerated: {generated.directory}")
            for warning in generated.warnings:
                print(f"Integrity warning: {warning}", file=sys.stderr)
            return 0
        else:
            config = load_config(args.config)
            config = with_debug_logging(config) if args.verbose else config
            if args.action == "validate":
                Orchestrator(config).validate()
                print(f"Configuration valid: {config.experiment.name}")
                print(f"Model: {model_path(config)}")
                return 0
            outcome = asyncio.run(Orchestrator(config).run())
    except CLIUsageError as error:
        print(styled(f"Command error: {error}", "red", sys.stderr), file=sys.stderr)
        return 2
    except ConfigError as error:
        print(styled(f"Configuration error: {error}", "red", sys.stderr), file=sys.stderr)
        return 2
    except (OSError, TypeError, ValueError) as error:
        print(styled(f"Experiment error: {error}", "red", sys.stderr), file=sys.stderr)
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
