# vLLM Optimizer MVP specification

- **Status:** Implemented development MVP
- **Platform:** Linux with NVIDIA GPUs
- **Server:** vLLM
- **Benchmark backends:** GuideLLM and vLLM Bench Serve

This document describes the behavior implemented today. Future capabilities
belong in [ROADMAP.md](ROADMAP.md).

## Product contract

vLLM Optimizer runs local experiments over vLLM server configurations. The user owns
the model, server parameters, benchmark workload, and metric. The `vllm-opt` CLI owns the
repeated process lifecycle:

```text
YAML â†’ search â†’ start vLLM â†’ wait for health â†’ run selected benchmark engine
     â†’ parse metrics â†’ stop owned processes â†’ rank â†’ report
```

The normal workflow is one command:

```bash
vllm-opt --config experiment.yaml
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
- **Run:** one `vllm-opt` invocation and its timestamped output directory.
- **Trial:** one resolved server configuration.
- **Attempt:** one execution attempt for a trial.
- **Benchmark run:** one named configuration for the selected benchmark engine.
- **Repeat:** one execution of a benchmark run for the same trial.
- **Baseline:** fixed server arguments evaluated before tuned trials.

## Detailed contracts

- [Configuration contract](mvp/configuration.md)
- [CLI, lifecycle, persistence, reports, and acceptance](mvp/runtime.md)
