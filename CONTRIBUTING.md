# Contributing to vLLM Config Tuner

vLLM Config Tuner favors small, explicit components over framework-heavy abstractions.
Read [the architecture](docs/ARCHITECTURE.md) before changing execution flow.

All contributions go through a pull request. Direct pushes and force pushes to
`main` are blocked for contributors; the repository owner reviews and merges
accepted changes after the required package and documentation checks pass.

## Development setup

Requirements are Python 3.11+, Linux, and—only for real benchmark runs—an
NVIDIA GPU with working `vllm` and `guidellm` commands.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
vtune --help
```

The public repository intentionally does not contain tests. Maintainers run a
private suite outside the checkout. Contributors should describe how they
verified a change and must not treat passing tests as a substitute for source
review.

## Where changes belong

- `config/`: YAML loading and runtime policy validation.
- `domain/`: tool-independent immutable records and statuses.
- `workers/`: one focused external operation per worker.
- `managers/`: orchestration policy, scoring, and persistence.
- `search/`: search-space expansion and sampler sessions.
- `benchmarks/`: backend command construction, timing, and parsing.
- `reporting/`: CSV, analysis, charts, tables, and static HTML composition.
- `reproduction/`: manifests, redaction, metadata, display, and export.
- `lifecycle/`: completed-run integrity and manual retry planning.

## Adding a component

For a worker, implement `execute(context)` and `cleanup(context)` from
`workers/base.py`. Return structured `WorkerResult` values; never terminate the
run or an unrelated process from a worker.

For a search strategy, implement `SearchSession` from `search/strategy.py` and
add validation/construction in `search/factory.py`. A strategy must preserve
deterministic IDs and never execute a resolved configuration twice.

For a benchmark backend, keep backend-specific CLI serialization and parsing
outside the domain model. Launch commands as argument arrays through
`ProcessRunner`; never use shell interpolation.

For reporting, consume persisted/domain results. Reporting must not launch
servers or benchmarks and must label exploratory statistics honestly.

## Project rules

- State the plan and obtain approval before editing.
- Keep responsibilities narrow and follow SOLID pragmatically.
- Files normally stay at or below 150 lines and never exceed 200 lines unless
  generated or vendored.
- Preserve immutable completed runs and owned-process cleanup.
- Keep documentation synchronized with user-visible behavior.
- Never commit tests, fixtures, snapshots, credentials, model files, run
  artifacts, virtual environments, or generated packages.

## Before submitting

1. Review every changed line and dependency.
2. Run the relevant private tests and broader regressions when shared behavior
   changed.
3. Build and install the wheel in a fresh environment.
4. Run a real GPU smoke test for lifecycle or benchmark changes.
5. Confirm no `vtune`-owned process remains and no private artifact is tracked.
6. Update README, MVP specification, architecture, or roadmap when behavior or
   an extension point changed.
