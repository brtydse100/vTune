# MVP configuration contract

## Configuration

```yaml
experiment:
  name: qwen-h100
  output_dir: runs
  seed: 42

server:
  model: /models/Qwen3-32B
  tensor-parallel-size: 4
  dtype: bfloat16

tune:
  max-num-seqs:
    values: [64, 128, 256]
  gpu-memory-utilization:
    min: 0.85
    max: 0.95
    step: 0.05

env:
  CUDA_VISIBLE_DEVICES: "0,1,2,3"

tune_env:
  VLLM_USE_V1:
    values: ["0", "1"]

benchmark:
  repeats: 3
  runs:
    - name: throughput
      request_format: /v1/completions
      profile:
        kind: throughput
        max_concurrency: 16
      constraints:
        - kind: max_duration
          seconds: 2m
      data:
        - kind: synthetic_text
          prompt_tokens: 256
          output_tokens: 128

baseline:
  enabled: true

optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 18

timeouts:
  startup: 900
  benchmark: 20m

execution:
  host: 127.0.0.1
  health_path: /health
  shutdown_grace: 15
  retry:
    max_attempts: 2

logging:
  level: INFO
```

### Required sections

`experiment` and `server` are required. A runnable
experiment also requires at least one `benchmark.runs` entry and a non-empty
`optimization.maximize` metric.

`server.model` must be an existing local directory. Relative paths are resolved
from the YAML file. The `vllm-opt` CLI never downloads a model.

### Server values

Entries under `server` other than `model` are fixed vLLM arguments. Top-level
`tune` and `tune_env` accept either:

```yaml
values: [a, b, c]
```

or an inclusive stepped range:

```yaml
min: 1
max: 8
step: 1
```

vLLM flags are rendered deterministically. `true` emits a presence flag;
`false` and `null` omit it; a fixed list repeats the flag for each item. All
processes are launched with argument arrays, never interpolated shell text.
Fixed environment variables use top-level `env`. Unless `server.host` is set
explicitly, the `vllm-opt` CLI supplies
`--host 127.0.0.1`. `execution.host` selects the address used for health checks
and defaults to the same loopback address.

### Benchmark runs

Each run requires a unique filesystem-safe `name`, one `profile` mapping, and
exactly one item in `data`. `constraints` may contain any GuideLLM constraint
mapping. Nested GuideLLM values are flattened to GuideLLM's CLI format.

GuideLLM always writes `results.json`; its console output is preserved in
`benchmark.log`. Profiles such as `throughput`, `concurrent`, and `sweep` are
passed through without a vLLM Optimizer allowlist.

### Search

- `grid` evaluates the complete Cartesian product and rejects `trials`.
- `random` and `tpe` require a positive `trials` value.
- Requested trials are capped with a warning at the number of unique
  configurations.
- A repeated Optuna suggestion is marked skipped and replaced before any
  vLLM process starts.
- `experiment.seed` controls Random and TPE sampling when supplied.

### Scoring

`optimization.maximize` names one GuideLLM metric. For each benchmark repeat,
the `vllm-opt` CLI averages that metric across the workloads returned by the profile. It
then takes the median across repeats for each named benchmark run and the
arithmetic mean across benchmark runs for the overall trial score.

Only completed tuned trials enter the ranking. The baseline is reported
separately and can still be the best observed recommendation in HTML.

### Timeouts and retries

`timeouts.startup` is a positive number of seconds. `timeouts.benchmark` is a
positive duration. Durations accept seconds or strings such as
`30s`, `2m`, and `1h`.

When `timeouts.benchmark` is omitted, the `vllm-opt` CLI uses the GuideLLM duration
constraint, workload strategy count, and a safety margin. A GuideLLM run
constrained only by `max_requests` uses a one-hour hard cap when no explicit
timeout is provided; set `timeouts.benchmark` for longer workloads. vLLM Bench
Serve retains its 180-second default. The literal value `auto` is invalid.

`execution.retry.max_attempts` defaults to one. Only failures marked retryable
are attempted again. Startup and benchmark timeouts and recognized connection
failures are transient; CUDA OOM, invalid arguments, and unsupported
configurations are not.

### Logging

`logging.level` accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` and
defaults to `INFO`. `DEBUG` streams labeled server and benchmark output while
still writing complete log files. `--verbose` overrides the YAML level with
`DEBUG` for one invocation.
