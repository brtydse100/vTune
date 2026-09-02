# Release notes

## Unreleased

_No changes yet._

## v0.1.0a12 — Live benchmark observability and failure policy

_September 2, 2026_

- Stream subprocess output into benchmark logs while commands are running and
  show live request counters or duration timers with clearer trial headings.
- Add configurable request-failure tolerance, an accept-any policy, and
  separate failed-request artifacts for GuideLLM and vLLM Bench Serve.
- Persist successful, failed, errored, and incomplete request counts plus the
  failure percentage for every benchmark repeat in JSON, CSV, and HTML.
- Add offline reclassification of immutable run data under a new request-error
  policy without relaunching vLLM or GuideLLM.
- Fix repeated benchmark drain paths, fast-benchmark final counters, and
  repeat score messaging; verify canonical normalization for both backends.

## v0.1.0a11 — vLLM Optimizer rebrand

_September 2, 2026_

- Renamed the project and distribution to **vLLM Optimizer** and
  `vllm-optimizer`.
- Added the `vllm_optimizer` import namespace and `vllm-opt` CLI.
- Retained deprecated `vtune` import and CLI compatibility aliases for one
  release cycle.

## v0.1.0a10 — Benchmark trust and release safeguards

_September 2, 2026_

- Reject incomplete GuideLLM request-count and vLLM Bench Serve results before
  they can enter scoring, and require clean normalized request totals.
- Increased the default request-count timeout to one hour and added a vLLM
  drain gate with persisted evidence after warmups and measured repeats.
- Added warmups, minimum-repeat enforcement, uncertainty summaries, drift
  detection, and sequential finalist validation.
- Added public behavioral tests, dependency review, SBOM generation, immutable
  provenance action pinning, and built-wheel tests in the publish workflow.

## v0.1.0a9 — Comparable benchmark evidence

_September 1, 2026_

- Renamed the public product to **vLLM Config Tuner** while preserving the
  `vtune` package, import namespace, and CLI command.
- Added ANSI terminal colors with `NO_COLOR` support and always pass the
  validated server port to vLLM.
- Validate complete YAML-derived commands before creating a run or launching a
  process.
- Normalize GuideLLM and vLLM throughput, request totals, and latency statistics
  into one schema without inventing missing percentiles.
- Persist benchmark repeat and wall-clock elapsed time and show per-benchmark
  average, median, and P99 evidence with metric definitions in HTML.
- Documented the GuideLLM request-count timeout and completion-integrity risk;
  long-generation workloads remain an alpha limitation until strict request
  completion and server-drain checks are implemented.

## v0.1.0a8 — Python 3.11 compatibility

- Fixed `TrialReport.execution` to use a dataclass default factory, restoring
  Python 3.11 package imports. The public Python 3.11 and 3.12 package checks
  now pass.

## v0.1.0a7 — Correctness and trust

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

Earlier entries are preserved in the [changelog archive](docs/releases/CHANGELOG_ARCHIVE.md).
