# vTune Future Implementation Roadmap

This roadmap lists capabilities that follow the first MVP described in
[MVP_SPEC.md](MVP_SPEC.md). It is organized by dependency and product value,
not by promised release dates.

## Guiding rules

Future work should preserve these invariants:

- Raw measurements remain separate from ranking and optimization policy.
- A trial is one server configuration; a scenario evaluation is one workload
  result within that trial.
- Reports can be regenerated from persisted data without GPUs or benchmarks.
- Benchmark and server integrations use adapters.
- Local execution remains the simplest default even after distributed support
  exists.
- New features must not weaken owned-process cleanup, immutable-run integrity,
  or secret handling.
- Any result labeled “best” must state the population and scoring policy from
  which it was selected.

## Phase 1: Harden the local experiment engine

These features should follow immediately after the first working release.

### Conditional search spaces

Allow parameters to be active only when another choice makes them valid:

```yaml
server:
  tune:
    attention-backend:
      values: [FLASH_ATTN, FLASHINFER]

    flashinfer-option:
      values: [a, b]
      when:
        attention-backend: FLASHINFER
```

Requirements:

- Deterministic normalization and fingerprinting.
- Clear validation of missing or cyclic dependencies.
- Compatible behavior across grid, random, and TPE.
- Reports distinguish inactive parameters from missing values.

### Advanced retry policies

Extend the MVP retry model with:

- Configurable exponential backoff and jitter.
- Backend-specific retry classification.
- Per-phase attempt limits.
- Retry budgets shared across a run.
- Retry statistics and policy recommendations.

Retries must remain part of one trial rather than inflating the study with
duplicate trials. OOM, invalid arguments, and deterministic incompatibilities
should not retry by default.

### Baseline scheduling and drift detection

- Periodically rerun the baseline during long experiments.
- Compare baseline measurements over time.
- Warn when performance drift exceeds a configured threshold.
- Optionally normalize candidates against the nearest baseline in time.
- Display time-correlated drift in the report.

### Statistical measurement controls

- Confidence intervals.
- Bootstrap comparisons.
- Outlier policies.
- Adaptive repeat counts when variance is high.
- Minimum meaningful improvement thresholds.
- Statistical tie handling instead of false precision.
- Host-noise metadata such as utilization and temperature sampling.

### Richer experiment comparison

- Compare two completed runs.
- Detect changes in vLLM, CUDA, drivers, model revisions, and benchmark versions.
- Show regressions and improvements by scenario.
- Export a machine-readable comparison artifact for CI.

### Experiment forking

Allow an existing immutable run to seed a changed experiment:

```bash
vtune fork runs/qwen-h100 --config revised.yaml
```

The fork records ancestry, reuses compatible cached evaluations, and clearly
separates the new experiment identity.

## Phase 2: Expand benchmark coverage

### vLLM Bench Serve adapter

Implement the same adapter contract as GuideLLM:

- Configuration validation.
- Command construction without shell interpolation.
- Expected-duration calculation.
- Raw output preservation.
- Metric normalization with explicit units.
- Backend version capture.
- Capability declaration for unsupported scenario features.

Reports must show backend provenance. Metrics from different backends should
not be treated as directly interchangeable unless their definitions and
measurement procedures are verified compatible.

### User-defined command adapter

Allow an advanced user to supply an external benchmark command that emits a
documented JSON result schema.

Safety and correctness requirements:

- Structured executable and argument fields rather than raw shell text.
- Explicit timeout and exit-code behavior.
- Version/provenance metadata.
- JSON Schema validation.
- No implicit trust of emitted file paths.
- Clear statement that vTune cannot guarantee comparability across arbitrary
  benchmark implementations.

### Dataset adapters

- Hugging Face dataset references with pinned revisions.
- Local JSONL and compatible benchmark formats.
- Synthetic prompt and output length distributions.
- Dataset sampling seeds.
- Dataset fingerprints stored in experiment metadata.
- Optional preprocessing cache.

### Correctness and quality gates

Performance alone is insufficient for settings that may affect output quality.
Add optional evaluators for:

- Response validity.
- Exact-match or task-specific correctness.
- Output truncation and completion length.
- Error-rate thresholds.
- User-provided evaluation commands.

Quality metrics may act as constraints or later as multi-objective targets.

## Phase 3: Richer optimization and rankings

### Multiple optimization targets

Support several named targets that share the same evaluation cache:

```yaml
optimization:
  targets:
    - name: overall
      trial_share: 0.50
    - name: chat-high-load
      trial_share: 0.25
    - name: code-high-load
      trial_share: 0.25
```

The scheduler allocates trials to targets while deduplicating identical server
configurations. Reports distinguish which target proposed each trial.

### Multi-objective optimization

- Throughput/latency Pareto optimization.
- Performance/cost Pareto optimization.
- Quality/performance tradeoffs.
- NSGA-II sampler support.
- Pareto frontier reporting and interactive filtering.
- Explicit dominance behavior when metrics are missing or constraints fail.

### Additional samplers

- CMA-ES for suitable continuous spaces.
- Gaussian-process optimization for expensive, smaller spaces.
- Quasi-random sampling.
- User-provided Optuna sampler integration.

Each sampler must declare supported parameter types and conditional-space
behavior. vTune should reject incompatible configurations during validation.

### Feasibility-aware search

Repeated OOM or incompatible regions should provide useful information:

- Model feasibility separately from objective quality.
- Avoid repeatedly sampling known-invalid exact combinations.
- Visualize failure regions by parameter.
- Optionally use constrained or feasibility-aware sampling.
- Never convert arbitrary infrastructure failures into evidence that a
  parameter region is inherently invalid.

### Pruning and early stopping

- Stop obviously poor trials after selected scenarios.
- Stop a study after convergence or a no-improvement window.
- Respect scenarios designated as mandatory before pruning.
- Record partial results without presenting them as complete comparisons.
- Account for server startup cost before applying aggressive pruning.

### Advanced ranking policies

- Lexicographic rankings.
- Percentile and trimmed-mean aggregation.
- Custom mathematical score expressions with a safe expression language.
- Scenario tags and boolean filters.
- Minimum-regret and worst-case policies.
- Cost-aware scores.
- User-selected reference configuration normalization.

## Phase 4: Faster local experimentation

### Safe duplicate-result reuse

Reuse completed evaluations when all identity-bearing inputs match:

- Server configuration fingerprint.
- Model and revision.
- Software and relevant hardware environment.
- Benchmark backend and version.
- Scenario and dataset fingerprints.
- Warm-up, repetition, and aggregation settings.

Cache reuse must be visible in logs and reports and must support an explicit
disable/refresh option.

### Controlled server reuse

Reuse a running vLLM server only when the next evaluation has an identical
server configuration fingerprint. The first use case is additional scenarios
or recovery after an interrupted benchmark, not reuse across different engine
settings.

Requirements:

- Recheck health before reuse.
- Detect state contamination where practical.
- Support a maximum server lifetime.
- Preserve restart-by-default as the reliability option.

### Scenario ordering optimization

- Run cheap or highly discriminative scenarios first.
- Order scenarios to support pruning.
- Randomize or counterbalance order when thermal or temporal drift matters.
- Preserve declared order as a selectable reproducibility mode.

### Model-loading improvements

- Document and expose vLLM-supported loading formats without hard-coding a
  permanent allowlist.
- Support sharded or accelerated loading strategies as ordinary parameters plus
  optional validation helpers.
- Measure loading time separately and include it in reports.
- Cache model and dataset preparation safely.

### Parallel local instances

Allow several independent vLLM instances and their benchmark processes to run
at the same time on one host. Each active instance executes a different trial;
this is separate from tensor parallelism inside one vLLM instance.

An intended configuration shape is:

```yaml
execution:
  mode: local_parallel
  max_parallel_trials: 2

  gpu_allocation:
    strategy: explicit       # explicit | automatic
    allow_sharing: false

    workers:
      - name: worker-0
        devices: [0, 1]

      - name: worker-1
        devices: [2, 3]

  ports:
    min: 8100
    max: 8199
```

`max_parallel_trials: 1` retains the original sequential behavior. Explicit
allocation is the safest initial implementation. Automatic allocation may use
a declared per-trial GPU requirement but must produce and persist the resolved
device assignment before launching a server.

Required scheduling behavior:

- Run no more than `max_parallel_trials` active trials.
- Give every worker a stable identity and an exclusive GPU set by default.
- Reject overlapping explicit device assignments unless `allow_sharing: true`
  is intentionally configured.
- Account for a trial's tensor-parallel requirement before assigning it.
- Keep a trial queued when no compatible worker is available.
- Allocate a unique port without a check-then-launch race.
- Launch each server and benchmark pair in independently owned process groups.
- Scope timeout, cancellation, failure, logs, and cleanup to the owning worker.
- Continue other workers when one trial fails.
- On experiment cancellation, stop and clean up every owned worker process.
- Prevent two workers from claiming the same pending trial.

Measurement and comparability requirements:

- Warn that simultaneous trials can contend for CPU, RAM, disk bandwidth,
  PCIe/NVLink fabric, network bandwidth, power, and cooling.
- Record worker identity, GPU identifiers, topology, and relevant host-load
  metadata with every trial.
- Do not compare results from materially different GPU models as if they were
  equivalent unless the user explicitly enables heterogeneous comparisons.
- Support a `sequential` measurement mode as the reference for high-confidence
  final validation.
- Optionally rerun the top configurations sequentially after the parallel
  search and use those validation measurements for the final ranking.
- Never silently combine parallel-search measurements with sequential
  validation measurements; label their execution mode in stored results and
  reports.

Persistence requirements:

- Use a coordinator as the single scheduler and authoritative owner of trial
  state transitions.
- Make concurrent artifact paths collision-free.
- Configure SQLite for safe concurrent readers and controlled writes, or route
  all writes through the coordinator.
- Persist worker leases so stale `running` trials can be identified, marked
  `interrupted`, and safely recovered after a crash.
- Preserve deterministic trial and server-configuration fingerprints regardless
  of which worker executes them.

Suggested CLI behavior:

```bash
vtune --config experiment.yaml --parallel 2
vtune status --run runs/qwen-h100 --watch
```

The CLI override changes only the maximum concurrency; worker and GPU safety
rules still come from the validated execution configuration.

Acceptance criteria for this feature:

- Two trials can run simultaneously on disjoint GPU sets and distinct ports.
- A failure or timeout in one instance does not interrupt the other.
- Ctrl+C removes every vTune-owned server and benchmark process without
  terminating unrelated processes.
- The scheduler never executes the same trial concurrently on two workers.
- Overlapping GPUs are rejected by default.
- Reports identify which results were measured concurrently.
- An optional sequential validation pass can rerun and rerank the top `N`
  configurations.

## Phase 5: Distributed execution

Distributed support should be optional and must not alter the local-first
workflow.

### Remote worker protocol

- Coordinator assigns immutable trial manifests.
- Workers advertise GPU, software, and backend capabilities.
- Workers stream state transitions and upload artifacts.
- Heartbeats identify lost workers.
- Leases prevent the same trial from being executed concurrently after a brief
  network interruption.
- Idempotent result submission.
- Secure authentication and transport.

### Shared artifact storage

- Pluggable local, object-store, and network-filesystem backends.
- Content-addressed artifacts.
- Checksums and integrity verification.
- Retention policies.
- Partial-upload recovery.
- Separation of metadata storage from large logs and benchmark outputs.

### Scheduler integrations

Potential optional integrations:

- SSH-managed workers.
- Slurm.
- Kubernetes Jobs.
- Ray, only if it materially simplifies execution rather than becoming a local
  requirement.

The core coordinator should operate through a small worker abstraction so no
single scheduler becomes the domain model.

### Heterogeneous hardware policy

- Filter workers by GPU model and memory.
- Prevent incomparable hardware from entering one ranking by default.
- Permit explicit cross-hardware experiments with normalized cost or efficiency
  metrics.
- Record topology and interconnect information.

## Phase 6: Reporting and user experience

### Interactive local report

- Filter trials by status, scenario, dataset, and parameter values.
- Inspect a trial and open its logs.
- Select ranking policies without rerunning benchmarks.
- Explore throughput/latency Pareto frontiers.
- Compare any two configurations.
- Display uncertainty and baseline drift.
- Remain buildable as a self-contained local artifact where practical.

### Optional local web UI

- Create and validate experiment configurations.
- Start and stop local runs.
- Stream concise status and selected logs.
- Browse prior experiments.
- Never become required for CLI usage.

### Better parameter analysis

- Importance with uncertainty and minimum-data warnings.
- Partial dependence views.
- Pairwise interaction analysis.
- Failure probability by parameter region.
- Clear distinction between correlation and causal claims.

### Recommendation export

- Export vLLM CLI snippets.
- Export environment files with secret placeholders.
- Export container arguments.
- Export Helm-value or deployment fragments through optional adapters.
- Attach provenance showing the experiment and ranking that selected the
  configuration.

## Phase 7: Automation and integration

### CI regression mode

```bash
vtune compare current-run reference-run \
  --fail-if "throughput_change < -5%" \
  --fail-if "ttft_p99_change > 10%"
```

Requirements:

- Machine-readable exit codes.
- Scenario-level thresholds.
- Statistical significance or uncertainty policies.
- Stable JSON output.
- Hardware and software comparability checks.

### Python API

Expose stable programmatic entry points for:

- Loading and validating experiments.
- Registering benchmark adapters.
- Launching and monitoring studies.
- Reading persisted results.
- Computing rankings.
- Generating exports.

The CLI should call the same application-layer API rather than owning separate
business logic.

### Plugin system

Possible extension points:

- Benchmark backends.
- Dataset loaders.
- Metric parsers.
- Quality evaluators.
- Samplers.
- Report panels.
- Artifact storage.
- Remote-worker transports.

Plugins require versioned contracts, capability negotiation, validation hooks,
and isolation of plugin failures from core experiment state.

### Notifications

Optional completion and failure notifications through pluggable sinks. No
external messaging service should be required, and secrets must use the same
redaction and persistence policy as server environment variables.

## Phase 8: Cost, energy, and capacity planning

### Cost-aware metrics

- Tokens per dollar.
- Requests per dollar.
- Cost per million output tokens.
- Startup-cost amortization.
- Configurable infrastructure price tables with provenance and effective dates.

### Energy and efficiency

- Power sampling where supported.
- Tokens per joule.
- Energy per request.
- Temperature and throttling indicators.
- Explicit sampling accuracy and hardware-support limitations.

### Capacity recommendations

- Estimate the configuration needed for a target service-level objective.
- Find maximum sustainable request rate under latency constraints.
- Model headroom policies.
- Export evidence and uncertainty rather than presenting an unsupported exact
  capacity guarantee.

## Cross-cutting future requirements

### Schema evolution

- Version every YAML and persisted result schema.
- Provide forward migrations for supported old versions.
- Never silently reinterpret an old score or metric definition.
- Preserve source and resolved configurations.

### Compatibility matrix

Track tested combinations of:

- vLLM versions.
- Benchmark backend versions.
- CUDA and driver versions.
- Python versions.
- GPU architectures.

Passthrough flags should remain allowed even when the combination is untested;
the matrix informs warnings rather than becoming an argument allowlist.

### Observability

- Structured internal logs with run and trial identifiers.
- Optional tracing of lifecycle phases.
- Storage-size and artifact-retention reporting.
- Diagnostic bundles that redact secrets.

### Testing strategy

- Unit tests for schemas, rendering, scoring, and fingerprinting.
- Fake vLLM and benchmark processes for deterministic lifecycle tests.
- Fault injection for hangs, partial output, OOM text, signals, and corrupt
  artifacts.
- Golden tests for reports and exports.
- Hardware integration tests on supported GPU configurations.
- Long-running soak tests.
- Schema-upgrade and interrupted-run recovery tests.

### Documentation

- Quick start with a small model.
- Complete configuration reference.
- Metric definitions and units.
- Benchmark comparability guidance.
- Troubleshooting by structured failure category.
- Reproducibility and security model.
- Adapter-development guide.

## Suggested release sequence

The roadmap can be grouped into practical releases:

| Release | Theme | Main outcome |
|---|---|---|
| MVP | Reliable local loop | Trustworthy unattended single-host experiments |
| 0.2 | Measurement confidence | Advanced retries, drift detection, statistics, richer comparisons |
| 0.3 | Benchmark breadth | vLLM Bench Serve, datasets, quality gates |
| 0.4 | Optimization depth | Multiple targets, Pareto search, pruning |
| 0.5 | Faster local runs | Cache reuse, controlled reuse, parallel GPU workers |
| 0.6 | Interactive analysis | Local UI, richer rankings and parameter analysis |
| 0.7 | Distributed execution | Remote workers and shared artifacts |
| 1.0 | Stable platform | Versioned APIs, plugins, migrations, compatibility guarantees |

Version numbers are illustrative. Reliability gates should determine release
timing rather than the number of accumulated features.

## Prioritization test

Before adding a roadmap feature, ask:

1. Does it improve measurement trust, failure recovery, or reproducibility?
2. Does it help users answer a decision they cannot answer from raw results?
3. Can it be implemented without weakening the local-first workflow?
4. Does its persisted data model remain useful if the implementation changes?
5. Is its complexity justified relative to model startup and benchmark cost?

Features that improve reliability and interpretability should normally precede
features that only add optimizer variety or visual polish.
