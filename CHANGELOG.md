# Release notes

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
