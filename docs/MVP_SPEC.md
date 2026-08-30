# vTune MVP specification

- **Status:** Implemented development MVP
- **Platform:** Linux with NVIDIA GPUs
- **Server:** vLLM
- **Benchmark backends:** GuideLLM and vLLM Bench Serve

This document describes the behavior implemented today. Future capabilities
belong in [ROADMAP.md](ROADMAP.md).

## Product contract

vTune runs local experiments over vLLM server configurations. The user owns
the model, server parameters, benchmark workload, and metric. vTune owns the
repeated process lifecycle:

```text
YAML → search → start vLLM → wait for health → run selected benchmark engine
     → parse metrics → stop owned processes → rank → report
```

The normal workflow is one command:

```bash
vtune --config experiment.yaml
```

Every invocation creates a timestamped run. A completed or interrupted run is
never resumed or overwritten. Manual retries create a new linked run.

## Included behavior

- One local vLLM instance at a time.
- Arbitrary fixed and tunable vLLM flags and environment variables.
- Grid, seeded Random, and seeded TPE search.
- Duplicate-free execution within Random and TPE runs.
- One maximize-only metric.
- One or more named GuideLLM or vLLM Bench Serve runs.
- Exactly one dataset definition per benchmark run.
- GuideLLM profiles, constraints, datasets, and request formats.
- Forward-compatible `vllm bench serve` arguments and normalized JSON results.
- Optional baseline, benchmark repeats, and median repeat aggregation.
- Health-based readiness, automatic benchmark timeouts, and owned cleanup.
- Retry attempts for failures classified as transient.
- Immutable manual retry runs for one or several trial IDs.
- Incremental JSON state, SQLite Optuna storage, CSV ranking, and static HTML.
- Per-trial raw benchmark logs and JSON, results, manifests, and checksums.
- Display-only reproduction and vLLM command export.

## Not in the MVP

- Concurrent, distributed, or remote trials.
- Multiple datasets inside one benchmark run.
- A benchmark backend other than GuideLLM or vLLM Bench Serve.
- Minimize, weighted, constrained, or multi-objective optimization.
- Conditional search spaces, pruning, or server reuse.
- Cross-run comparison or a web service.
- Automatic correctness or response-quality evaluation.
- Windows or macOS execution guarantees.

## Terminology

- **Experiment:** named directory containing related immutable runs.
- **Run:** one vTune invocation and its timestamped output directory.
- **Trial:** one resolved server configuration.
- **Attempt:** one execution attempt for a trial.
- **Benchmark run:** one named configuration for the selected benchmark engine.
- **Repeat:** one execution of a benchmark run for the same trial.
- **Baseline:** fixed server arguments evaluated before tuned trials.

## Configuration

```yaml
schema_version: 1

experiment:
  name: qwen-h100
  output_dir: runs
  seed: 42

server:
  model: /models/Qwen3-32B
  tensor-parallel-size: 4
  dtype: bfloat16

tune:
  max-num-seqs:
    values: [64, 128, 256]
  gpu-memory-utilization:
    min: 0.85
    max: 0.95
    step: 0.05

env:
  CUDA_VISIBLE_DEVICES: "0,1,2,3"

tune_env:
  VLLM_USE_V1:
    values: ["0", "1"]

benchmark:
  repeats: 3
  runs:
    - name: throughput
      request_format: /v1/completions
      profile:
        kind: throughput
        max_concurrency: 16
      constraints:
        - kind: max_duration
          seconds: 2m
      data:
        - kind: synthetic_text
          prompt_tokens: 256
          output_tokens: 128

baseline:
  enabled: true

optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 18

timeouts:
  startup: 900
  benchmark: 20m

execution:
  host: 127.0.0.1
  health_path: /health
  shutdown_grace: 15
  retry:
    max_attempts: 2

logging:
  level: INFO
```

### Required sections

`schema_version`, `experiment`, and `server` are required. A runnable
experiment also requires at least one `benchmark.runs` entry and a non-empty
`optimization.maximize` metric.

`server.model` must be an existing local directory. Relative paths are resolved
from the YAML file. vTune never downloads a model.

### Server values

Entries under `server` other than `model` are fixed vLLM arguments. Top-level
`tune` and `tune_env` accept either:

```yaml
values: [a, b, c]
```

or an inclusive stepped range:

```yaml
min: 1
max: 8
step: 1
```

vLLM flags are rendered deterministically. `true` emits a presence flag;
`false` and `null` omit it; a fixed list repeats the flag for each item. All
processes are launched with argument arrays, never interpolated shell text.
Fixed environment variables use top-level `env`. Unless `server.host` is set
explicitly, vTune supplies
`--host 127.0.0.1`. `execution.host` selects the address used for health checks
and defaults to the same loopback address.

### Benchmark runs

Each run requires a unique filesystem-safe `name`, one `profile` mapping, and
exactly one item in `data`. `constraints` may contain any GuideLLM constraint
mapping. Nested GuideLLM values are flattened to GuideLLM's CLI format.

GuideLLM always writes `results.json`; its console output is preserved in
`benchmark.log`. Profiles such as `throughput`, `concurrent`, and `sweep` are
passed through without a vTune allowlist.

### Search

- `grid` evaluates the complete Cartesian product and rejects `trials`.
- `random` and `tpe` require a positive `trials` value.
- Requested trials are capped with a warning at the number of unique
  configurations.
- A repeated Optuna suggestion is marked skipped and replaced before any
  vLLM process starts.
- `experiment.seed` controls Random and TPE sampling when supplied.

### Scoring

`optimization.maximize` names one GuideLLM metric. For each benchmark repeat,
vTune averages that metric across the workloads returned by the profile. It
then takes the median across repeats for each named benchmark run and the
arithmetic mean across benchmark runs for the overall trial score.

Only completed tuned trials enter the ranking. The baseline is reported
separately and can still be the best observed recommendation in HTML.

### Timeouts and retries

`timeouts.startup` is a positive number of seconds. `timeouts.benchmark` is a
positive duration. Durations accept seconds or strings such as
`30s`, `2m`, and `1h`.

When `timeouts.benchmark` is omitted, vTune uses the GuideLLM duration
constraint, workload strategy count, and a safety margin. Without a duration
constraint it defaults to 180 seconds. The literal value `auto` is invalid.

`execution.retry.max_attempts` defaults to one. Only failures marked retryable
are attempted again. Startup and benchmark timeouts and recognized connection
failures are transient; CUDA OOM, invalid arguments, and unsupported
configurations are not.

### Logging

`logging.level` accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` and
defaults to `INFO`. `DEBUG` streams labeled server and benchmark output while
still writing complete log files. `--verbose` overrides the YAML level with
`DEBUG` for one invocation.

## CLI

```bash
# Run or validate
vtune -c experiment.yaml
vtune validate -c experiment.yaml

# Display stored commands without executing them
vtune reproduce --run runs/NAME/RUN_ID --trial trial-0001

# Export only the stored vLLM command
vtune export --run runs/NAME/RUN_ID --trial trial-0001

# Retry selected configurations in a new linked run
vtune retry --run runs/NAME/RUN_ID --trial trial-0001 --trial trial-0004
```

`reproduce` never executes a command. Redacted environment and CLI argument
values must be supplied manually. Retry verifies the source result, trial directories,
manifest identities, and available artifact checksums before starting.

## Lifecycle

For each attempt, `TrialManager` runs focused workers in order:

1. Build the vLLM command and environment.
2. Start vLLM in an owned process group and capture output.
3. Poll the configured HTTP health endpoint while watching for early exit.
4. Run every benchmark and repeat sequentially.
5. Parse selected-backend JSON into the common benchmark result model.
6. Clean up started workers in reverse order.

A trial failure does not stop later trials. Ctrl+C marks the active trial and
run `interrupted`, cleans up owned processes, and returns exit code 130.

## Persistence

```text
runs/EXPERIMENT/RUN_ID/
├── result.json
├── results.csv
├── report.html
├── study.db                 # Random and TPE only
└── trials/
    └── trial-0001/
        ├── manifest.json
        ├── result.json
        └── attempts/001/
            ├── vllm.log
            └── repeats/001/BENCHMARK/
                ├── benchmark.log
                └── results.json
```

`result.json` is created before execution and updated after every trial. Trial
manifests contain the exact commands with secret-like values redacted,
software/GPU metadata, startup duration, source linkage, and checksums for
generated artifacts.

Configured environment or CLI argument names containing `TOKEN`, `PASSWORD`,
`PASSWD`, `SECRET`, `API_KEY`, or `PRIVATE_KEY` are stored as `<redacted>` in
manifests, run results, CSV, HTML, and terminal summaries. The complete
inherited process environment is never persisted.

## Reports

The static HTML report shows the best observed result, tuned delta from
baseline, changed settings, reproduction command, trial history,
throughput/TTFT plot when available, exploratory parameter importance,
observed parameter effects, per-benchmark winners, distinct top
configurations, and failure summaries.

Effect and importance views are observational, not causal. Fewer than five
successful tuned trials are explicitly labeled low confidence.

## MVP acceptance

The MVP is accepted when private tests, wheel installation, CLI validation,
one real baseline/TPE experiment, one real verbose experiment, cleanup checks,
and artifact/report inspection all pass in the supported WSL/Linux playground.
