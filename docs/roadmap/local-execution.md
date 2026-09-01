# Faster local execution

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

Status: the first explicit local implementation is available on `main`.
It supports exclusive declared GPU workers, deterministic ports, bounded
concurrency, coordinator-owned persistence, failure isolation, cancellation,
and resolved assignment metadata. Automatic allocation, sharing,
heterogeneous comparison, and sequential finalist validation remain future
work.

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
vllm-opt --config experiment.yaml --parallel 2
vllm-opt status --run runs/qwen-h100 --watch
```

The CLI override changes only the maximum concurrency; worker and GPU safety
rules still come from the validated execution configuration.

Acceptance criteria for this feature:

- Two trials can run simultaneously on disjoint GPU sets and distinct ports.
- A failure or timeout in one instance does not interrupt the other.
- Ctrl+C removes every `vllm-opt`-owned server and benchmark process without
  terminating unrelated processes.
- The scheduler never executes the same trial concurrently on two workers.
- Overlapping GPUs are rejected by default.
- Reports identify which results were measured concurrently.
- An optional sequential validation pass can rerun and rerank the top `N`
  configurations.
