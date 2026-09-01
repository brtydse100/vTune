# Automation, APIs, cost, and capacity

## Phase 7: Automation and integration

### CI regression mode

```bash
vllm-opt compare current-run reference-run \
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
