# Distributed execution and reporting

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
