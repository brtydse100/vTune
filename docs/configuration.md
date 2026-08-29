# Configuration

vTune keeps server settings separate from benchmark workloads so every server
configuration can be compared under the same demand.

## Model and server

`model.path` must point to an existing local model directory. Fixed values in
`server.args` are passed to every vLLM process. Values in `server.tune` define
the search space.

```yaml
model:
  path: /models/qwen
server:
  args:
    tensor-parallel-size: 2
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

Unknown vLLM flags are intentionally allowed. vTune renders keys as CLI flags,
which keeps new vLLM options usable without a vTune release.

## Benchmark runs

Each entry under `benchmark.runs` is a GuideLLM invocation. A single trial may
contain several benchmark runs, but they all evaluate the same running server
configuration. vTune always preserves normalized JSON and `benchmark.log`.

## Logging and timeouts

```yaml
logging:
  level: INFO
timeouts:
  startup: 15m
  benchmark: auto
```

Logging levels match GuideLLM: `DEBUG`, `INFO`, `WARNING`, `ERROR`, and
`CRITICAL`. Automatic benchmark timeouts use the configured GuideLLM duration
plus a safety margin.
