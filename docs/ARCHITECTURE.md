# vLLM Optimizer architecture

## Early design sketch

![Early vLLM Optimizer architecture sketch](assets/architecture-early-sketch.png)

The sketch is preserved as the project's original manager-and-worker concept.
The editable early diagram is [vllm-optimizer-architecture.drawio](vllm-optimizer-architecture.drawio).
Some boxes are aspirations rather than current classes.

## Implemented flow

```text
CLI → YAML loader → Orchestrator → SearchSession
                         │
                         └→ TrialManager
                              ├→ ConfigurationBuilderWorker
                              ├→ VLLMRunnerWorker
                              ├→ ReadinessWorker
                              └→ BenchmarkWorker(s)
                                      │
                                      └→ GuideLLM or vLLM Bench JSON

Trial results → RunAccumulator → result.json / CSV / HTML / Optuna SQLite

The run-level `result.json` stores the effective repeat, warmup, drift, and
request-failure policy. Offline regeneration and reclassification reuse that
policy; legacy results derive compatible defaults from the trial manifest.
```

## Ownership

- `cli.py` selects one user workflow and converts failures to exit codes.
- `config/` loads typed configuration and validates runtime policy.
- `search/` owns Grid, Random, and TPE suggestions. The orchestrator sees only
  the `SearchSession` protocol.
- `Orchestrator` composes a run. `orchestrator_search.py` owns trial scheduling,
  while `RunFinalizer` owns terminal cleanup and atomic terminal run states.
- `TrialManager` owns worker ordering, attempts, reverse cleanup, and transient
  retry decisions for one trial.
- Workers own one external action. They communicate through `TrialContext` and
  return structured statuses instead of controlling the run.
- `ProcessRunner` launches argument arrays without a shell, creates an owned
  process group, captures logs, and optionally mirrors DEBUG output.
- `managers/` scores and persists domain results; run-document serialization is
  separate from run finalization.
- `reporting/` converts completed run data into CSV and static HTML. Offline
  loading and reclassification scoring are isolated from report rendering.
- `reproduction/` records, validates, redacts, displays, and exports manifests.
- `lifecycle/` validates immutable source artifacts and builds manual retries.

## Dependency direction

Domain records do not depend on vLLM, GuideLLM, Optuna, the CLI, or HTML.
Workers depend on domain boundaries; managers coordinate domain records;
the orchestrator composes them. External formats are normalized at the edge.

## Extension points

- Add a worker by implementing the small `Worker` protocol in `workers/base.py`.
- Add a search strategy by implementing `SearchSession` and selecting it in
  `search/factory.py`.
- Benchmark engines keep command builders and parsers in `benchmarks/`, with
  lifecycle workers selected in `workers/factory.py`.
- Add report sections in `reporting/` without changing execution workers.
- Add orchestration managers only when they own policy shared by multiple
  workers; do not rename a composed trial worker to a manager solely because it
  calls other code.

## Current boundary

Sequential execution is the default. Local parallel execution requires
explicit non-overlapping GPU workers and deterministic ports. Automatic GPU
allocation, shared GPUs, and distributed workers remain roadmap work.
