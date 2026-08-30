# Complete YAML example

This file shows every vTune-controlled setting. vLLM flags and GuideLLM
registry fields remain open-ended, so their tools may support additional keys.

```yaml
schema_version: 1

experiment:
  name: qwen-production
  output_dir: runs
  seed: 42

server:
  model: /models/Qwen3-32B
  tensor-parallel-size: 4
  dtype: bfloat16
  gpu-memory-utilization: 0.90
  max-model-len: 32768
  enforce-eager: false

tune:
  max-num-seqs:
    values: [64, 128, 256]
  max_num_batched_tokens:  # underscores are also accepted
    min: 4096
    max: 16384
    step: 4096
  attention-backend:
    values: [FLASH_ATTN, FLASHINFER]
  enable-prefix-caching:
    values: [true, false]

env:
  CUDA_VISIBLE_DEVICES: "0,1,2,3"
  VLLM_LOG_STATS_INTERVAL: "5"

tune_env:
  VLLM_USE_FLASHINFER_SAMPLER:
    values: ["0", "1"]

benchmark:
  repeats: 3
  runs:
    - name: throughput
      request_format: /v1/completions
      profile:
        kind: throughput
        max_concurrency: 32
      constraints:
        - kind: max_requests
          count: 500
      data:
        - kind: synthetic_text
          prompt_tokens: 512
          output_tokens: 128

    - name: chat-concurrency
      request_format: /v1/chat/completions
      profile:
        kind: concurrent
        streams: [4, 16, 32]
      constraints:
        - kind: max_duration
          seconds: 2m
      data:
        - kind: json_file
          path: /benchmarks/chat.jsonl

baseline:
  enabled: true

optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 20

timeouts:
  startup: 15m
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

`timeouts.benchmark` may be omitted; vTune then derives it from the benchmark
constraints plus a safety margin. The literal value `auto` is not accepted.

See [configuration](configuration.md) for vTune fields and
[benchmarking](benchmarking.md) for every benchmark form with examples.
