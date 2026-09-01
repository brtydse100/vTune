# MVP runtime and acceptance contract

## CLI

```bash
# Run or validate
vllm-opt -c experiment.yaml
vllm-opt validate -c experiment.yaml

# Display stored commands without executing them
vllm-opt reproduce --run runs/NAME/RUN_ID --trial trial-0001

# Export only the stored vLLM command
vllm-opt export --run runs/NAME/RUN_ID --trial trial-0001

# Retry selected configurations in a new linked run
vllm-opt retry --run runs/NAME/RUN_ID --trial trial-0001 --trial trial-0004
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
â”œâ”€â”€ result.json
â”œâ”€â”€ results.csv
â”œâ”€â”€ report.html
â”œâ”€â”€ study.db                 # Random and TPE only
â””â”€â”€ trials/
    â””â”€â”€ trial-0001/
        â”œâ”€â”€ manifest.json
        â”œâ”€â”€ result.json
        â””â”€â”€ attempts/001/
            â”œâ”€â”€ vllm.log
            â””â”€â”€ repeats/001/BENCHMARK/
                â”œâ”€â”€ benchmark.log
                â””â”€â”€ results.json
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
per-benchmark elapsed time and latency statistics, metric definitions,
throughput/TTFT plot when available, exploratory parameter importance,
observed parameter effects, per-benchmark winners, distinct top
configurations, and failure summaries.

Effect and importance views are observational, not causal. Fewer than five
successful tuned trials are explicitly labeled low confidence.

## MVP acceptance

The MVP is accepted when private tests, wheel installation, CLI validation,
one real baseline/TPE experiment, one real verbose experiment, cleanup checks,
and artifact/report inspection all pass in the supported WSL/Linux playground.
