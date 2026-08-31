# Release notes

## Unreleased

## v0.1.0a7 â€” Correctness and trust

- Persisted typed per-trial execution assignments separately from artifacts.
- Stopped deriving median and P99 values when a backend supplied only an average.
- Offline regeneration recomputes derived metric summaries without changing its source run.
- Hardened optional LLM endpoints and made integrity warnings precise.

## v0.1.0a6 — Trustworthy progress and GuideLLM completion

_August 31, 2026_

### Progress and diagnostics

- Added timestamped live terminal stages, TTY loading animation, trial progress,
  per-repeat scores, and final session duration.
- Removed repeated artifact folders for `benchmark.repeats: 1` and added a
  clear warning when every benchmark request fails or is ineligible.

### Reports and configuration

- Made `schema_version` optional while retaining version-1 compatibility.
- Added ordered benchmark tables, labelled chart axes, standard metric tables,
  scoring/importance explanations, run duration, and persisted metric summaries.
- Added optional secret-safe OpenAI-compatible report summaries configured with
  `analysis.llm_summary` and an environment-variable API key.
- Expanded CLI help and documented GuideLLM throughput completion behavior.

### GuideLLM reliability

- Removed vTune's interactive-console override so GuideLLM retains its normal
  request-draining lifecycle.
- Mark a benchmark as failed with a targeted diagnostic when GuideLLM exits
  without any completed requests.

## v0.1.0a5 — Native benchmarks and explicit parallel trials

_August 31, 2026_

### vLLM Bench Serve

- Added `benchmark.engine: vllm` as an alternative to the default GuideLLM
  backend, with forward-compatible `vllm bench serve` argument pass-through.
- Made `--backend vllm` automatic instead of requiring it in every run.
- Added canonical throughput aliases, request-failure accounting, raw JSON and
  log preservation, exact command capture, retries, repeats, and timeouts.
- Added random, ShareGPT, Hugging Face, custom, and prefix-repetition examples.

### Parallel trials

- Added opt-in local parallel execution with explicit, exclusive GPU workers
  and deterministic per-worker ports.
- Kept search suggestions, Optuna updates, ranking, and persistence under one
  coordinator while trial process groups execute concurrently.
- Recorded resolved worker, device, port, and execution mode in artifacts and
  labeled parallel reports with a hardware-contention warning.
- Added failure isolation and cancellation cleanup across active workers.

## v0.1.0a4 — Easier setup and actionable diagnostics

_August 30, 2026_

### Installation

- Added the optional `runtime` installation extra for vLLM and GuideLLM.
- Added actionable errors when either runtime executable is unavailable.
- Clarified the difference between experiment and inspection installations.

### Runtime diagnostics

- Reworked progress so each stage resolves on one line and baseline failures
  show their complete diagnostic immediately.
- Preserved root-cause exception lines in failure excerpts instead of showing
  only the end of long tracebacks.

### Documentation

- Added a complete commented YAML reference covering every vTune section,
  tuning syntax, benchmark profile, request route, and dataset family.
- Added a dedicated installation guide for core-only and experiment-runtime
  environments, including native Windows and WSL differences.

## v0.1.0a3 — Clearer benchmarks and trustworthy results

_August 30, 2026_

### Runtime and diagnostics

- Added one-based trial IDs, structured lifecycle progress, best-so-far output,
  default failure details, and richer timeout diagnostics.
- Accepted duration strings for startup timeouts and made omitted benchmark
  timeouts automatic; the literal `auto` value is no longer accepted.
- Capped excessive trial requests with a warning instead of stopping the run.
- Accepted underscore-style vLLM argument names and fixed false secret
  redaction of token-count settings.

### Ranking and reports

- Added GuideLLM request-success and error accounting.
- Excluded workloads with more than 50% failed or incomplete requests.
- Ranked eligible trials by error rate, error count, then objective value.
- Added transparent ranking evidence and eligibility explanations to reports.

### Documentation

- Added a complete YAML example and examples for every exposed GuideLLM
  profile, constraint, request format, and dataset family.

## v0.1.0a2 — Cleaner configuration and safer delivery

_August 30, 2026_

See the [complete release notes](docs/releases/v0.1.0a2.md).

### Reports

- Added offline report regeneration from validated immutable run artifacts.
  Regeneration never starts vLLM or GuideLLM and never overwrites an existing
  destination.

### Configuration

- Simplified YAML to place fixed vLLM arguments directly under `server`, with
  the required local model at `server.model`. Tunable arguments, fixed
  environment variables, and tunable environment variables now use top-level
  `tune`, `env`, and `tune_env` sections.

### Project delivery

- Added pull-request package and documentation checks across supported Python
  versions, with immutable Node 24 action revisions.
- Added code ownership and protected-main contribution guidance.
- Clarified CUDA compatibility and simplified the five-minute quick start.

## v0.1.0a1 — Local vLLM tuning, reproducible trials, and decision reports

_August 30, 2026_

vTune's first public alpha turns a small YAML file into a complete local vLLM
optimization run. It owns server startup and shutdown, benchmarks each unique
configuration, preserves reproducibility data, and produces a report focused
on the settings that actually changed.

### Highlights

- Local-first baseline, Grid, Random, and Optuna TPE experiments.
- GuideLLM workloads with vLLM lifecycle and readiness management.
- Immutable runs, linked retries, failure isolation, and duplicate prevention.
- CSV, JSON, and self-contained HTML results with parameter-effect views.
- Exact, secret-redacted commands and environment metadata for reproduction.

### What's changed

#### Experiment engine

- Added typed YAML configuration, arbitrary vLLM flags and environment values,
  readiness polling, process ownership, and trial management (`780758d`).
- Added GuideLLM execution, normalized metrics, scoring, orchestration, baseline
  trials, retries, intelligent timeouts, and failure classification
  (`d1f71c9`, `a15d76b`).
- Made the local model path the single model source (`537a9be`).

#### Search and lifecycle

- Added persistent Grid, Random, and TPE sessions with deterministic seeds and
  Optuna SQLite storage (`e65a4b1`).
- Added immutable run IDs, interruption handling, linked multi-trial retries,
  worker factories, and integrity checks (`049934d`, `e03996c`).
- Prevented Random and TPE from executing duplicate resolved configurations
  (`c2f77bf`).

#### Reproduction and reports

- Stored exact commands, selected environment values, software and GPU details,
  timing, checksums, logs, and exit state for each trial (`e768c03`).
- Added a decision dashboard with baseline comparison, score history,
  throughput/latency tradeoffs, and observed parameter effects (`fe8f5bd`).
- Reduced top-configuration tables to distinct settings that changed
  (`40545bc`).

#### Safety and contributor experience

- Added GuideLLM-compatible log levels and optional live verbose output
  (`c2f77bf`).
- Added loopback-only defaults, safe experiment names, persistent secret
  redaction, packaging metadata, MIT licensing, and contributor docs
  (`30bbfaa`, `c2f4046`).

### Validation

- All 106 private tests passed.
- A real baseline plus two-trial TPE run completed with vLLM `0.28.0` and
  GuideLLM `0.7.3`; its three trials completed and artifacts were inspected.
  This was a small compatibility workload, not a general performance claim.
- The exact universal wheel passed installation, dependency, import, and CLI
  checks on Ubuntu 24.04/Python 3.12 and Windows/Python 3.12.
- Package metadata, archive contents, and dependency security checks passed.

### Install

```bash
pip install vtune==0.1.0a1
```

The `py3-none-any` wheel installs on Linux, Windows, and macOS because vTune is
pure Python. Running vLLM experiments remains Linux-only; Windows supports
configuration and stored-result inspection, not native vLLM execution.

See the [quick start](README.md#quick-start) and
[compatibility notes](https://brtydse100.github.io/vTune/compatibility/)
before the first GPU run.

**Full changelog:** `c2f4046...47a5d1a`
