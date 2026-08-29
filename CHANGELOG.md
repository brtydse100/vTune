# Changelog

## 0.1.0a1 — 2026-08-30

First public alpha release. The entries below preserve the project history in
commit order.

### `c2f4046` — Architecture and MVP definition

- Established the project rules, architecture, MVP specification, roadmap,
  early architecture sketch, and editable Draw.io diagram.

### `780758d` — Configuration and worker lifecycle

- Added typed YAML loading, validation, CLI entry point, process ownership,
  readiness polling, vLLM workers, trial management, and package metadata.

### `d1f71c9` — Benchmarks, scoring, and orchestration

- Added GuideLLM command generation and JSON normalization, grid search,
  scoring, result persistence, run summaries, and the main orchestrator.

### `a15d76b` — Baselines, retries, and reporting

- Added baseline trials, transient retry attempts, automatic benchmark
  timeouts, failure classification, CSV export, and the first static report.

### `537a9be` — Local model paths

- Required an existing local model directory and removed redundant model and
  executable configuration from benchmark settings.

### `e65a4b1` — Persistent search strategies

- Added Grid, Random, and TPE sessions with deterministic seeds and Optuna
  SQLite persistence.

### `e768c03` — Reproducibility manifests

- Stored commands, environment selections, software and GPU metadata, startup
  timing, logs, checksums, and safe command exports for every trial.

### `049934d` — Immutable experiment lifecycle

- Added immutable run directories, run IDs, interruption handling, linked
  retry runs, fixed-configuration retries, and worker factories.

### `e03996c` — Run visibility and integrity

- Made `result.json` available throughout execution and added artifact,
  manifest, source-trial, and retry integrity checks.

### `fe8f5bd` — Decision dashboard and reproduction display

- Added the HTML decision dashboard, score and latency charts, parameter
  effects, top-configuration tables, and display-only reproduction details.

### `40545bc` — Report cleanup

- Removed low-value artifact details and made top-configuration tables show
  only changed, distinct settings.

### `c2f77bf` — Duplicate-free search and logging

- Prevented repeated Random and TPE configurations, added GuideLLM-compatible
  logging levels, verbose terminal streaming, and concise CLI documentation.

### `30bbfaa` — MVP release preparation

- Synchronized documentation with implementation, added contributor guidance,
  MIT licensing, package metadata and typing marker, loopback binding, safe
  experiment names, and secret redaction across persistent and visible output.

### Release validation

- Verified 106 private tests and a clean wheel installation.
- Verified baseline plus TPE tuning using vLLM 0.10.2 and GuideLLM 0.7.3.
- Verified a real GPU trial using vLLM 0.28.0 and GuideLLM 0.7.3.
- Verified the universal wheel in an isolated minimal Linux environment.
- Verified wheel installation, dependency consistency, and CLI startup on
  Windows with Python 3.12.
