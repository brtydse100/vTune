# Configuration

vLLM Config Tuner keeps server settings separate from benchmark workloads so every server
configuration can be compared under the same demand.

## Model and server

`server.model` is required and must point to an existing local model directory.
Every other `server` entry is a fixed vLLM argument. Top-level `tune` defines
the vLLM argument search space.

```yaml
server:
  model: /models/qwen
  tensor-parallel-size: 2
  enforce-eager: true
tune:
  max-num-seqs:
    values: [64, 128, 256]
  gpu-memory-utilization:
    min: 0.85
    max: 0.95
    step: 0.05
env:
  CUDA_VISIBLE_DEVICES: "0,1"
```

Unknown vLLM flags are intentionally allowed. The `vtune` CLI renders keys as CLI flags,
which keeps new vLLM options usable without a vLLM Config Tuner release.

The complete configuration is validated before a run directory or process is
created. This includes nested benchmark options, search values, ports, GPU
assignments, timeouts, and the rendered vLLM and benchmark commands.

### Fixed value rendering

Fixed `server` values map directly to vLLM flags:

```yaml
server:
  model: /models/qwen
  enforce-eager: true       # emits --enforce-eager
  disable-log-requests: false  # omitted
  lora-modules: [a=/a, b=/b]   # repeats --lora-modules
```

`null` and `false` omit a flag. `true` emits a presence flag. Scalars emit a
flag/value pair, and lists repeat the flag once for each item.

### Tunable vLLM arguments

Categorical values can contain strings, numbers, or booleans:

```yaml
tune:
  attention-backend:
    values: [FLASH_ATTN, FLASHINFER]
  max-num-seqs:
    values: [64, 128, 256]
  enforce-eager:
    values: [true, false]
```

Integer and float ranges are inclusive when the step reaches the maximum:

```yaml
tune:
  max-num-batched-tokens:
    min: 4096
    max: 16384
    step: 4096
  gpu-memory-utilization:
    min: 0.85
    max: 0.95
    step: 0.05
```

### Environment variables

Fixed environment values belong in `env`; tunable ones use `tune_env`:

```yaml
env:
  CUDA_VISIBLE_DEVICES: "0,1"
  VLLM_LOG_STATS_INTERVAL: 5
tune_env:
  VLLM_USE_FLASHINFER_SAMPLER:
    values: ["0", "1"]
  WORKER_COUNT:
    min: 1
    max: 4
    step: 1
```

Environment values are converted to strings before process launch. Quoting
values such as `"0"` and `"1"` avoids YAML treating them as numbers.

## Parallel local trials

Sequential execution is the default. To run separate vLLM instances at the
same time, configure explicit GPU workers and a port range:

```yaml
execution:
  mode: local_parallel
  max_parallel_trials: 2
  gpu_allocation:
    workers:
      - name: worker-0
        devices: [0, 1]
      - name: worker-1
        devices: [2, 3]
  ports:
    min: 8100
    max: 8199
```

GPU sets must not overlap. The `vtune` CLI assigns `CUDA_VISIBLE_DEVICES` and one stable
port to each worker, so do not configure either yourself in parallel mode.
`max_parallel_trials` must equal the declared worker count, and every trial's
`tensor-parallel-size` must fit at least one worker. The baseline runs alone
first; tuned trials then run concurrently. See
[parallel trials](parallel-trials.md) for scheduling and measurement rules.

For sequential execution, including one vLLM server using tensor parallelism
across several GPUs, the `vtune` CLI always passes a concrete port. It defaults to 8000;
set `server.port` only when another port is required.

## Benchmark runs

`benchmark.engine` selects `guidellm` (default) or `vllm`. A single trial may
contain several benchmark runs, but they all evaluate the same running server
configuration. GuideLLM runs use `profile`, `constraints`, and `data`; vLLM
Bench Serve runs use `args`. The `vtune` CLI preserves raw JSON and `benchmark.log`, then
exposes normalized metrics to scoring and reports.

Set `benchmark.warmup_repeats` to discard initial measurements and
`benchmark.min_repeats` to require enough measured repeats for ranking. The
default minimum is 1 for backward compatibility; use 2 or more for confidence
intervals. Set `analysis.drift_threshold` to change the sequential finalist
rerun threshold (default 0.05).

Every supported profile, constraint, request format, and dataset form has a
copyable examples in [benchmark configuration](benchmarking.md). See the
[complete YAML](full-example.md) for all configuration sections together.

## Logging and timeouts

```yaml
logging:
  level: INFO
timeouts:
  startup: 15m
  benchmark: 20m
```

Logging levels match GuideLLM: `DEBUG`, `INFO`, `WARNING`, `ERROR`, and
`CRITICAL`. Both timeouts accept seconds or values such as `30s`, `15m`, and
`1h`. For GuideLLM, omitting `timeouts.benchmark` derives it from the duration
constraint plus a safety margin. A run constrained only by `max_requests` uses
a documented one-hour hard cap when no explicit timeout is provided; set
`timeouts.benchmark` explicitly for longer workloads. vLLM Bench Serve uses a
180-second default when no explicit timeout is provided. The literal value
`auto` is not accepted.

After each benchmark, vTune polls vLLM's running and waiting request metrics.
`execution.drain_grace` controls this drain window and defaults to 15 seconds.
It must be positive. Missing metrics or a server that remains busy fails the trial.
