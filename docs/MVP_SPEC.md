# vTune First MVP Specification

**Status:** Proposed
**Target:** First useful local release
**Primary platform:** Linux with NVIDIA GPUs
**Primary benchmark backend:** GuideLLM

## 1. Purpose

vTune is a local-first experimentation engine for vLLM serving
configurations. A user describes fixed parameters, tunable parameters,
benchmark scenarios, an optimization target, and constraints in YAML. vTune
then manages the complete experiment loop:

```text
Resolve experiment configuration
             ↓
Choose a server configuration
             ↓
Start and monitor vLLM
             ↓
Run every configured benchmark scenario
             ↓
Normalize and persist metrics
             ↓
Stop vLLM and release resources
             ↓
Choose the next configuration
             ↓
Rank results and generate reports
```

The MVP must be dependable enough to run unattended for several hours. Search
sophistication and presentation polish are secondary to correct process
management, trustworthy measurements, retryability, comparison, and
reproducibility.

## 2. Product promise

> You define what to tune and how success is measured. vTune runs the
> experiments and shows what actually worked.

vTune must not maintain an allowlist of supported vLLM arguments. Fixed and
tunable CLI arguments and environment variables are rendered generically so
new vLLM options can be tested without a vTune release.

## 3. MVP boundaries

### Included

- Local execution on one machine.
- One managed vLLM server at a time.
- Arbitrary fixed and tunable vLLM CLI arguments.
- Arbitrary fixed and tunable environment variables.
- Named benchmark scenarios, including different datasets and workload levels.
- GuideLLM benchmark adapter.
- Grid, random, and TPE search.
- One primary scalar optimization target.
- Constraints scoped to one, some, or all scenarios.
- Overall, per-scenario, and per-dataset result rankings.
- SQLite-backed persistence with immutable timestamped runs.
- Automatic retry attempts for selected transient failures.
- Basic comparison between completed or interrupted runs.
- Health-based startup detection and reliable process cleanup.
- Warm-up, repeated measurements, and configurable aggregation.
- Trial-level failure isolation and structured failure categories.
- Concise terminal progress and complete per-trial logs.
- CSV and JSON export.
- A small static HTML report.
- Exact trial manifests and reproduction commands.

### Explicitly excluded from the first MVP

- Distributed workers, Ray, Kubernetes, or remote execution.
- More than one vLLM server running concurrently. This is an explicit
  post-MVP feature specified under **Parallel local instances** in the roadmap;
  the MVP data model and process ownership rules must not prevent it.
- Multi-objective search and Pareto-guided sampling.
- Automatic server reuse between distinct optimizer trials.
- `vllm bench serve` as a second benchmark backend.
- NSGA-II, CMA-ES, Gaussian-process, or custom samplers.
- Web dashboards or a long-running control service.
- Automated model-loading optimization.
- Windows and macOS execution guarantees.
- Automatic correctness or output-quality evaluation.
- Conditional search-space expressions.
- Automatic detection of all invalid parameter combinations.

These are roadmap items rather than rejected ideas. The MVP architecture must
leave room for them without implementing them prematurely.

## 4. Terminology

The implementation and documentation must use these terms consistently.

### Experiment

A named collection of related runs, such as `qwen-h100`.

### Run

One invocation of `vtune --config`. A run is immutable after it finishes and
is never resumed or overwritten.

### Trial

One resolved vLLM server configuration within a run.

### Attempt

One execution attempt for a trial. A retry creates another attempt while
preserving every earlier attempt and its failure information.

### Scenario

One named benchmark workload, such as a dataset at a particular concurrency,
request rate, input length, or output length.

### Scenario evaluation

The result of running one scenario during a successful attempt. A trial may
have several scenario evaluations.

### Repeat

One measured repetition of a scenario. Repeats are aggregated into a scenario
evaluation.

### Ranking

A post-processing rule that orders completed trials. An experiment may expose
several rankings without rerunning benchmarks.

### Optimization target

The single ranking score used by TPE to choose future trials. Other rankings
remain useful analysis views, but TPE is not assumed to have optimized for
them.

### Baseline

A fixed server configuration evaluated using the same scenarios and
measurement procedure. It is used for comparison and optional score
normalization.

## 5. Primary user workflow

Starting an experiment must require only the vTune command and a configuration
flag:

```bash
vtune --config experiment.yaml
```

The short form is:

```bash
vtune -c experiment.yaml
```

This single command validates the configuration, creates a new immutable run,
runs the baseline and trials, persists results incrementally, and generates
the final exports and report.
Users must not need to invoke separate validation, status, export, or report
commands for the normal workflow.

Runtime behavior can be adjusted with optional flags without changing the
configuration file:

```bash
vtune --config experiment.yaml --verbose
```

Management commands may exist for advanced or post-run use, but they are not
part of the required path:

```bash
vtune validate --config experiment.yaml
vtune status --run runs/qwen-h100
vtune report --run runs/qwen-h100
vtune export --run runs/qwen-h100 --format csv
vtune reproduce --run runs/qwen-h100 --trial 17
vtune retry --run runs/qwen-h100/20260828-143012 --trial 17
vtune compare --base runs/qwen-h100/20260827-090000 \
  --candidate runs/qwen-h100/20260828-143012
```

The exact package name may change before publication if naming or package-index
availability requires it, but the command model should remain stable.

## 6. Proposed YAML contract

```yaml
schema_version: 1

experiment:
  name: qwen-h100
  output_dir: runs
  seed: 42

model:
  path: /models/Qwen3-32B

server:
  args:
    tensor-parallel-size: 4
    dtype: bfloat16

  tune:
    max-num-seqs:
      values: [64, 128, 256]

    max-num-batched-tokens:
      values: [4096, 8192, 16384]

    gpu-memory-utilization:
      min: 0.85
      max: 0.95
      step: 0.05

    attention-backend:
      values: [FLASH_ATTN, FLASHINFER]

  env:
    CUDA_VISIBLE_DEVICES: "0,1,2,3"

  tune_env:
    SOME_VLLM_ENV:
      values: ["0", "1"]

benchmark:
  repeats: 3  # vTune automatically uses the median
  runs:
    - name: chat-low-load
      request_format: /v1/completions
      profile:
        kind: concurrent
        streams: [4]
        warmup: 30
      constraints:
        - kind: max_duration
          seconds: 2m
      data:
        - kind: synthetic_text
          prompt_tokens: 1800
          output_tokens: 20

    - name: chat-high-load
      request_format: /v1/completions
      profile:
        kind: concurrent
        streams: [64]
        warmup: 30
      constraints:
        - kind: max_duration
          seconds: 2m
      data:
        - kind: synthetic_text
          prompt_tokens: 1800
          output_tokens: 20

baseline:
  enabled: true

optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 50

timeouts:
  startup: 900
  benchmark: auto

logging:
  verbose: false
  show_latest_server_status: true

execution:
  shutdown_grace: 20
  retry:
    max_attempts: 2
```

`model.path` is required, must point to an existing local model directory, and
is resolved relative to the YAML file when it is not absolute.

Unknown top-level vTune keys must be rejected with a useful validation error.
Unknown entries inside `server.args`, `server.tune`, `server.env`, and
`server.tune_env` must be accepted because they are intentional passthrough
values.

## 7. Configuration rules

### 7.1 CLI argument rendering

The MVP must define deterministic behavior for:

- Strings, integers, and floats: `name: value` becomes `--name value`.
- `true`: emits a presence-only flag such as `--enable-feature`.
- `false` and `null`: omit the flag.
- Lists in fixed arguments: emit the argument once per value.
- Tunable `values`: treat the complete selected value as one choice.
- Argument names: preserve the YAML spelling after adding the `--` prefix.
- Model identifier: render immediately after `vllm serve` unless overridden by
  the supported command template.

Arguments must be passed to the operating system as an argument array, not as
an interpolated shell string. A quoted shell representation is generated only
for display and export.

### 7.2 Search-space values

The MVP supports:

```yaml
parameter:
  values: [a, b, c]
```

```yaml
integer_parameter:
  min: 1
  max: 8
  step: 1
  type: int
```

```yaml
float_parameter:
  min: 0.80
  max: 0.95
  step: 0.05
  type: float
```

Range endpoints are inclusive when they fall on the generated step sequence.
Configuration validation must reject a zero or negative step, an inverted
range, an empty values list, duplicate parameter definitions, and collisions
between fixed and tunable parameters.

Floating-point sequences must be generated deterministically using decimal
arithmetic rather than repeated binary floating-point addition.

### 7.3 Environment variables and secrets

- Environment variable values are converted to strings before process launch.
- Trial manifests store only variables explicitly configured by the user plus
  a documented allowlist of system metadata.
- The complete parent process environment must never be exported.
- Names matching common secret patterns such as `TOKEN`, `PASSWORD`, `SECRET`,
  or `API_KEY` are redacted in logs, reports, and shell exports by default.
- The internal manifest records that a redacted variable was present without
  storing its value unless the user explicitly enables secret persistence.

### 7.4 Duration and unit handling

Durations accept integer or decimal values with `ms`, `s`, `m`, or `h` units.
Internally they are stored in milliseconds. Normalized metric names include
their units where ambiguity is possible, for example `ttft_p99_ms`.

## 8. Search behavior

### Grid

- Enumerates the Cartesian product in deterministic order.
- Evaluates the complete grid; `optimization.trials` is rejected for this sampler.

### Random

- Samples from the declared space using the experiment seed.
- Runs exactly `optimization.trials` suggestions.
- Persists suggestions and outcomes in the run's `study.db`.

### TPE

- Uses Optuna's TPE sampler and the experiment seed.
- Uses Optuna's default startup behavior.
- Optimizes one scalar target score.
- Persists completed and failed outcomes in the run's `study.db`.
- Marks stale Optuna `RUNNING` trials as failed when reopening a study.

TPE optimizes only `optimization.maximize`. Secondary rankings must be labeled
as the best configurations *among evaluated trials*, not as independently
optimized global results.

## 9. Scenario evaluation and scoring

### 9.1 Measurement procedure

For every successful server startup:

1. Execute the configured warm-up.
2. Run each scenario in declared order.
3. Run each scenario the configured number of repeats.
4. Store raw output and parsed metrics for every repeat.
5. Aggregate repeats into one scenario evaluation.
6. Compute constraints and ranking scores only from aggregated evaluations.

The default repeat aggregation is median. Supported MVP aggregation methods
are `mean`, `median`, `min`, and `max`.

vTune never adds an implicit benchmark warm-up. Step 1 applies only when the
user includes `warmup` in the GuideLLM profile, identically for baseline and
tuned trials.

### 9.2 Primary score methods

The primary target supports:

- `single`: use one named scenario.
- `mean`: equal mean across selected scenarios.
- `weighted_mean`: weighted mean across selected scenarios.
- `worst_case`: optimize the weakest selected scenario.

### 9.3 Normalization

Supported modes are:

- `none`: aggregate raw metric values.
- `baseline_ratio`: divide each scenario value by its matching baseline value
  before aggregation.

`baseline_ratio` is recommended when scenario metric scales differ
substantially. A throughput ratio above `1.0` is better than the baseline. For
a minimized metric such as latency, the scoring layer must orient the ratio so
larger normalized scores consistently mean better performance, or clearly keep
the configured minimization direction throughout. The chosen convention must
be stored in the resolved experiment manifest.

### 9.4 Constraints

Constraints may select scenarios by explicit names, `all`, or a metadata
filter. The MVP supports `min`, `max`, `mean`, and `median` aggregation across
selected scenarios and the operators `<`, `<=`, `>`, and `>=`.

A missing required metric causes the constraint evaluation to fail with the
reason `missing_metric`; it must never silently pass.

## 10. Lifecycle and process management

### 10.1 Run, trial, and attempt states

```text
Run:     created → running → completed | completed_with_failures
                           → failed | interrupted

Trial:   pending → running → completed | failed | interrupted

Attempt: created → starting_server → warming_up → benchmarking
                 → stopping_server → completed | failed | interrupted
```

Every state transition is timestamped and persisted before the next phase.

### 10.2 Startup readiness

vTune must:

- Launch vLLM in a dedicated process group.
- Capture stdout and stderr immediately.
- Detect early process exit without waiting for the startup timeout.
- Poll a configurable HTTP readiness endpoint.
- Require a successful readiness response before benchmarking.
- Display elapsed startup time, process state, endpoint state, and the latest
  useful server log line.
- Fail only the active trial after the startup timeout.

Log text may enrich diagnostics but must not be the sole readiness signal.

### 10.3 Port ownership

- vTune allocates or validates a port before server launch.
- A pre-existing listener on a user-selected port is an error.
- vTune records the process identifier it launched.
- Cleanup targets only the owned process group.
- vTune must never terminate an unrelated process based solely on port usage or
  executable name.

### 10.4 Shutdown and cleanup

After success, failure, timeout, or user interruption, vTune must:

1. Stop the benchmark process if it is still running.
2. Request graceful vLLM termination.
3. Wait for `shutdown_grace`.
4. Force termination of the owned process group if necessary.
5. Confirm the owned processes exited.
6. Record cleanup failures separately from benchmark results.

Ctrl+C stops the current trial safely, persists its interrupted state, cleans
up owned processes, and then exits. A second Ctrl+C may force immediate cleanup
but must still avoid unrelated processes.

## 11. Timeout behavior

- `startup` is always explicit and measured from process launch.
- `benchmark: auto` equals warm-up duration plus the sum of scenario durations
  and configured repeats, plus a documented safety margin.
- Explicit benchmark timeouts override the automatic value.
- Timeout errors identify the exact phase, scenario, and repeat.
- A timed-out trial does not crash the study.

## 12. Failure model

Failures must have a machine-readable category and a human-readable detail.
The MVP categories are:

```text
configuration_invalid
server_launch_failed
server_exited_early
server_oom
server_startup_timeout
server_unhealthy
warmup_failed
benchmark_launch_failed
benchmark_timeout
benchmark_parse_failed
benchmark_failed
missing_metric
constraint_violated
cleanup_failed
user_interrupted
internal_error
```

Expected operational failures mark only the active trial. `internal_error`
should preserve a traceback and stop the overall run by default because study
integrity may be uncertain. A future policy may allow users to continue after
selected internal errors.

OOM and common invalid-option failures should be classified using process exit
status and conservative log matching. The original output must always be
preserved even when classification is uncertain.

### 12.1 Retry behavior

- The run orchestrator decides whether an attempt is retryable.
- A retry creates a new attempt for the same trial configuration.
- The first successful attempt completes the trial and contributes its metrics.
- Failed attempts remain visible but do not contribute performance metrics.
- If all attempts fail, the trial fails and the run continues.
- OOM, invalid configuration, unsupported options, and `interrupted` attempts
  do not retry automatically.
- Manual retry after a run finishes creates a new linked validation run rather
  than modifying the original run.

## 13. Persistence and experiment identity

### 13.1 Directory layout

```text
runs/
└── qwen-h100/
    └── 20260828-143012/
        ├── run.db
        ├── source-config.yaml
        ├── resolved-config.yaml
        ├── run.json
        ├── results.csv
        ├── results.json
        ├── report.html
        ├── logs/
        │   └── vtune.log
        └── trials/
            ├── 0000/
            │   ├── manifest.json
            │   ├── result.json
            │   └── attempts/
            │       ├── 000/
            │       │   ├── server.log
            │       │   ├── benchmark.log
            │       │   └── scenarios/
            │       └── 001/
            └── 0001/
```

### 13.2 Fingerprints

vTune generates:

- An **experiment-definition fingerprint** from the normalized search space,
  model,
  scenarios, benchmark settings, scoring rules, constraints, and relevant
  execution settings.
- A **server configuration fingerprint** from the resolved model, vLLM
  arguments, and configured environment variables, excluding runtime-only
  fields such as port and process identifier.

Canonical serialization must be deterministic. Secret values excluded from
persistence still need a safe one-way contribution to fingerprints when their
change could affect results.

### 13.3 Immutable run identity

- Every invocation creates a new run under the named experiment directory.
- Run directories use a collision-safe timestamped identifier.
- Finished and interrupted runs are never overwritten or continued.
- Partial results from an interrupted run remain reportable and comparable.
- Manual retries create a linked run with `source_run_id` and `source_trial_id`.
- A future seeding feature may teach a new optimizer about previous results
  without changing the original run.

### 13.4 SQLite responsibilities

For Random and TPE runs, Optuna stores search parameters, scalar scores, and
trial states in `study.db`. vTune's backend-neutral domain results remain in
`result.json`; the Optuna schema is not their source of truth.

Filesystem artifacts are written atomically where practical. A crash between
database and artifact writes must be detectable. Stale active attempts are
marked `interrupted`; a subsequent invocation creates a new run.

## 14. Benchmark adapter contract

Although the MVP implements only GuideLLM, it must use an internal adapter
interface with these responsibilities:

```text
validate configuration
build an argument-array command
calculate expected duration
run warm-up
run one scenario repeat
parse raw output
return normalized metrics plus backend-native metrics
report backend version
```

The normalized metric schema should initially include, when emitted by the
backend:

- `requests_per_second`
- `input_tokens_per_second`
- `output_tokens_per_second`
- `ttft_mean_ms`
- `ttft_p50_ms`
- `ttft_p90_ms`
- `ttft_p99_ms`
- `tpot_mean_ms`
- `tpot_p50_ms`
- `tpot_p90_ms`
- `tpot_p99_ms`
- request count
- success count
- failure count

Backend-native results are preserved unchanged alongside normalized metrics.
The adapter must not invent a missing percentile or convert a failed request
into a successful measurement.

## 15. Reproducibility manifest

Every trial records:

- Trial identifier and status.
- Exact vLLM and GuideLLM argument arrays.
- Explicit environment overrides with secret-like values redacted.
- Local model path and fixed/selected server parameters.
- vLLM version.
- GuideLLM version.
- vTune and Python versions plus operating-system information.
- GPU name, UUID, memory, driver, and CUDA version when detectable.
- Benchmark configuration, including only user-configured warm-up and repeats.
- Server startup duration for each attempt that reached readiness checking.

`vtune export --run RUN --trial ID` prints the stored vLLM launch command. It
does not execute the command. Structured arrays in `manifest.json` remain the
source of truth; shell rendering is for display and manual use.

## 16. CLI requirements

### `vtune --config FILE`

- This is the primary and only required user workflow.
- Performs validation automatically before launching any process.
- Creates a new immutable run under the named experiment.
- Runs the configured baseline and trials.
- Executes trials until the budget is complete or the user interrupts.
- Writes results incrementally rather than waiting for study completion.
- Generates CSV, JSON, and HTML outputs after the experiment completes.
- Prints the experiment directory so optional management commands can use it.
- Supports `-c` as the short alias for `--config`.
- Supports the `--verbose` override.

Configuration errors must explain the invalid field and exit before launching
vLLM. A separate validation command is never a prerequisite.

### `vtune validate --config FILE` (optional)

- Parses and validates configuration without launching vLLM.
- Prints the resolved finite grid size when calculable.
- Shows the benchmark scenario count and expected minimum run duration.
- Warns about a missing baseline required by normalization.
- Verifies required executables and Python packages are available.
- Does not require a GPU for schema-only validation; an optional environment
  check may inspect hardware.

### `vtune status --run RUN` (optional)

- Shows current or last-known state, completed/failed counts, elapsed time, and
  the current best feasible trial.
- Works while an experiment is running and after it has stopped.

### `vtune report --run RUN` (optional)

- Regenerates JSON, CSV, and HTML outputs entirely from persisted data.
- Does not require vLLM, a GPU, or the original benchmark datasets.

### `vtune export --run RUN --trial ID`

- Shows the selected trial's safe POSIX-shell vLLM command.
- Warns through `<redacted>` placeholders about values that must be supplied.
- Never starts a process.

### `vtune reproduce --run RUN --trial ID` (optional)

- Shows the resolved configuration and safe shell commands.
- Warns about redacted values that must be supplied.
- Requires `--execute` before executing anything.

### `vtune retry --run RUN --trial ID` (optional)

- Creates a new validation run linked to the selected source trial.
- Reuses the exact stored server configuration and benchmark scenarios.
- Never modifies the source run or its attempts.

### `vtune compare --base RUN --candidate RUN` (optional)

- Compares matching scenarios and normalized metrics.
- Reports absolute and percentage differences.
- Warns about differences in models, datasets, backends, software, or hardware.
- Refuses metric comparisons whose definitions or scenario identities differ.

## 17. Terminal experience

Default output is concise:

```text
Study: qwen-h100
Sampler: TPE (seed 42)
Trials: 50 | Scenarios: 3 | Repeats: 3

Baseline  Starting vLLM...
Baseline  Ready after 48.3s
Baseline  Running 3 scenarios...
Baseline  Completed

[01/50] Starting vLLM...
[01/50] elapsed=01:42 process=alive endpoint=not-ready
[01/50] status="Loading model weights..."
[01/50] Ready after 108.7s
[01/50] chat-low-load   throughput=621 tok/s  p99_ttft=81 ms
[01/50] chat-high-load  throughput=4,281 tok/s  p99_ttft=381 ms
[01/50] code-high-load  throughput=3,912 tok/s  p99_ttft=442 ms
[01/50] Completed score=1.14x baseline

[02/50] Failed: server_oom
```

Raw process output is written to files. `--verbose` also streams it with clear
server and benchmark prefixes.

## 18. Result analysis and report

The report must answer:

1. What is the best feasible configuration for the primary target?
2. What is the best evaluated configuration for each scenario?
3. What is the best evaluated configuration for each dataset?
4. How does each winner compare with the baseline?
5. Which parameters appear to have the largest effect?
6. Which trials failed, and why?

### Required report elements

- Experiment metadata and reproducibility summary.
- Primary winner with resolved parameters and all scenario metrics.
- Top feasible configurations table.
- Per-scenario winners.
- Per-dataset winners when datasets are configured.
- Baseline comparisons.
- Throughput-versus-latency scatter plot.
- Trial history plot.
- Parameter-importance chart when statistically defensible.
- Failed-trial counts grouped by category.
- Links to local trial artifacts.
- Attempt counts and retry failure details.

Parameter importance must be omitted or clearly marked low-confidence when
there are too few successful trials. The implementation should define and
document a minimum threshold rather than presenting misleading percentages.

Secondary rankings must state that their winners are the best among evaluated
trials. Only the primary target guided TPE sampling.

## 19. Internal component boundaries

```text
Configuration loader and validator
               ↓
       Application builder
               ↓
        Main run orchestrator
       ┌───────┼────────┐
       ↓       ↓        ↓
 SearchManager │   ResultsManager
               ↓
        TrialScheduler
               ↓
        TrialManager 1..N
               ↓
 configuration → vLLM → readiness → benchmark → verification → result workers
               ↓
        external adapters
```

Required separation rules:

- The vLLM runner must not depend directly on Optuna.
- Benchmark adapters must not write directly to SQLite.
- Reports must be generated solely from persisted domain records.
- Scoring must be rerunnable without executing benchmarks.
- Commands must remain structured argument arrays until display/export.
- Domain records must not expose Optuna-specific types to other components.
- A `TrialManager` owns one attempt and coordinates its workers and cleanup.
- Workers perform focused operations and report `completed`, `failed`, or
  `interrupted` outcomes.
- The run orchestrator, not a worker, decides whether to retry an attempt.
- The results manager is the single authoritative path for persistence,
  scoring, ranking, and comparison.

## 20. Suggested domain records

At minimum:

```text
Experiment
Run
SearchParameter
Scenario
Trial
TrialParameter
Attempt
ScenarioRepeat
ScenarioEvaluation
Metric
ConstraintResult
RankingResult
Artifact
ProcessRecord
```

Trial and scenario result storage should support a long-form metric model:

```text
trial_id | scenario_id | repeat | metric_name | value | unit
```

This allows new metrics without immediate database migrations while stable
summary columns can still be materialized for common reports.

## 21. Security and safety requirements

- Never execute user configuration through `shell=True` or an equivalent shell
  interpolation path.
- Redact configured secrets in terminal output, reports, logs, and exports.
- Do not capture the complete inherited environment.
- Only terminate processes created and tracked by the active vTune run.
- Treat benchmark datasets and model identifiers as untrusted input when
  building paths or commands.
- Prevent trial artifact paths from escaping the experiment directory.
- Do not expose the vLLM endpoint beyond the configured bind address.

## 22. MVP acceptance criteria

The MVP is complete only when all of the following are demonstrated.

### Configuration

- A test experiment combines fixed and tunable CLI arguments and environment
  variables.
- Invalid ranges and conflicting parameters fail before server launch.
- A previously unknown vLLM passthrough flag can be represented without code
  changes to vTune.

### Execution

- One configuration is evaluated across at least three named scenarios without
  restarting vLLM between those scenarios.
- A new trial receives a fresh vLLM process.
- Readiness is determined without a fixed startup sleep.
- Startup, benchmark, and cleanup timeouts are individually enforced.
- Ctrl+C leaves no vTune-owned server or benchmark process running.

### Fault tolerance

- A simulated OOM fails one trial and the next trial runs.
- An invalid vLLM argument is classified and does not crash the study.
- A benchmark timeout is scoped to its active trial and scenario.
- An unexpected internal persistence error stops safely and remains diagnosable.

### Measurement

- Warm-up and three repeats are supported.
- Raw repeat data and median aggregated scenario data are both persisted.
- Weighted and single-scenario scores produce deterministic results.
- Per-scenario and per-dataset winners can be recomputed without rerunning the
  experiment.

### Retry and immutable runs

- A transient failure creates a second attempt for the same trial.
- Deterministic failures do not retry automatically.
- An interrupted run remains unchanged and reportable.
- Starting the same configuration again creates a separate run.

### Comparison

- Two compatible runs can be compared by matching scenario and metric.
- Differences in relevant environment metadata produce clear warnings.
- Incompatible scenario or metric definitions are not silently compared.

### Reproducibility

- A completed trial exports its structured arguments, explicit environment,
  software versions, hardware metadata, scenarios, and metrics.
- The displayed reproduction command matches the stored argument array.
- Secret-like values are redacted by default.

### Reporting

- JSON, CSV, and static HTML outputs can be regenerated offline.
- The report identifies the primary winner, scenario winners, dataset winners,
  baseline comparison, and grouped failures.
- Secondary TPE-derived rankings contain the appropriate sampling caveat.

## 23. Recommended implementation order

1. Configuration schema, normalization, validation, and fingerprints.
2. SQLite domain storage and artifact layout.
3. Owned-process lifecycle management and health detection.
4. GuideLLM adapter and normalized metric contract.
5. A deterministic single-configuration execution path.
6. Scenario repeats, aggregation, constraints, and scoring.
7. Grid and random planners.
8. Optuna TPE integration.
9. Retry attempts and immutable run linking.
10. Basic run comparison.
11. Exports, reproduction manifests, and terminal summaries.
12. Static HTML report and parameter importance.
13. End-to-end fault-injection and interruption testing.

This ordering intentionally proves the reliable experiment runner before
adding optimizer complexity.

## 24. Definition of done

The first MVP is done when a user can start a multi-hour local experiment,
experience invalid configurations, OOM failures, benchmark failures, and a
manual interruption, then inspect the immutable partial run, retry selected
work in a linked run, and compare trustworthy results without manually cleaning
up processes or repairing experiment state.
