# Complete commented YAML

This is the complete vTune configuration surface in one file. It is valid YAML
using the current schema; replace the model and dataset paths before running
it. Lines beginning with `#` are explanations or alternatives that can be
uncommented.

vTune passes arbitrary `server` keys to vLLM and the contents of GuideLLM
`profile`, `constraints`, and `data` objects to GuideLLM. New upstream options
therefore work without being added to a vTune allowlist.

```yaml
schema_version: 1  # Required. The only supported schema version is 1.

experiment:
  name: complete-example  # Letters, numbers, underscores, and hyphens only.
  output_dir: runs        # Default: runs. Relative to the current directory.
  seed: 42                # Optional. Makes Random and TPE repeatable.

# server.model is required and must be an existing local model directory.
# Every other key under server becomes a fixed `vllm serve` argument.
server:
  model: /models/Qwen3-32B
  port: 8000
  tensor-parallel-size: 4
  dtype: bfloat16
  gpu-memory-utilization: 0.90
  max-model-len: 32768
  enforce-eager: false          # false and null omit the flag.
  enable-prefix-caching: true   # true emits a presence-only flag.
  # served-model-name: qwen     # Scalars emit --flag value.
  # lora-modules:               # Lists repeat the flag for every item.
  #   - adapter-a=/models/a
  #   - adapter-b=/models/b

# Tunable vLLM arguments live here, never under server.
# Hyphens and underscores are both accepted in argument names.
tune:
  attention-backend:            # Categorical strings.
    values: [FLASH_ATTN, FLASHINFER]
  max-num-seqs:                 # Categorical integers.
    values: [64, 128, 256]
  enforce-eager:                # Categorical booleans.
    values: [true, false]
  max_num_batched_tokens:       # Inclusive integer range.
    min: 4096
    max: 16384
    step: 4096
  gpu-memory-utilization:       # Inclusive float range.
    min: 0.85
    max: 0.95
    step: 0.05
  # kv-cache-dtype:             # null may be tested to omit a flag.
  #   values: [auto, fp8, null]

# Fixed environment variables are inherited by every server trial.
env:
  CUDA_VISIBLE_DEVICES: "0,1,2,3"
  VLLM_LOG_STATS_INTERVAL: "5"
  # VLLM_USE_V1: "0"           # Quote numeric-looking environment values.

# Tunable environment variables use the same values or range syntax.
tune_env:
  VLLM_USE_FLASHINFER_SAMPLER:
    values: ["0", "1"]
  # WORKER_COUNT:
  #   min: 1
  #   max: 4
  #   step: 1

benchmark:
  repeats: 3  # Default: 1. vTune uses the median across repeated runs.
  runs:
    # Each named run is one GuideLLM invocation against the same server.
    # A run must contain exactly one data item.
    - name: concurrent-chat
      request_format: /v1/chat/completions  # Default: /v1/completions.
      profile:
        kind: concurrent
        streams: [4, 16, 32]
        max_concurrency: 32
      constraints:
        - kind: max_requests
          count: 500
        - kind: max_duration
          seconds: 2m  # Duration strings and numeric seconds are accepted.
      data:
        - kind: synthetic_text
          prompt_tokens: 512
          prompt_tokens_stdev: 32
          prompt_tokens_min: 128
          prompt_tokens_max: 1024
          output_tokens: 128
          output_tokens_stdev: 16
          output_tokens_min: 32
          output_tokens_max: 256
          turns: 1

    - name: maximum-throughput
      request_format: /v1/completions
      profile:
        kind: throughput
        max_concurrency: 32
        rampup_duration: 10
      constraints: [{kind: max_requests, count: 500}]
      data:
        - kind: json_file
          path: /benchmarks/prompts.jsonl  # JSON and JSONL use json_file.

    # Profile alternatives: copy one profile into a run; do not combine kinds.
    # - name: synchronous
    #   profile: {kind: synchronous}
    #   constraints: [{kind: max_requests, count: 100}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: constant-rate
    #   profile: {kind: constant, rate: 10}
    #   constraints: [{kind: max_duration, seconds: 2m}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: poisson-rate
    #   profile: {kind: poisson, rate: 10}
    #   constraints: [{kind: max_duration, seconds: 2m}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: sweep
    #   profile: {kind: sweep, sweep_size: 10, strategy_type: constant}
    #   constraints: [{kind: max_requests, count: 500}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: trace-replay
    #   profile: {kind: replay, time_scale: 1.0}
    #   constraints: [{kind: max_requests, count: 500}]
    #   data:
    #     - kind: trace_synthetic
    #       path: /benchmarks/trace.jsonl
    #       timestamp_column: timestamp
    #       prompt_tokens_column: input_length
    #       output_tokens_column: output_length

    # Other request routes supported by the model and GuideLLM:
    # request_format: /v1/completions
    # request_format: /v1/chat/completions
    # request_format: /v1/responses
    # request_format: /v1/embeddings

    # Dataset alternatives: every run must select exactly one data item.
    # data: [{kind: huggingface, source: garage-bAInd/Open-Platypus,
    #         load_kwargs: {split: train}}]
    # data: [{kind: hf, source: /local/dataset, load_kwargs: {split: train}}]
    # data: [{kind: csv_file, path: /benchmarks/prompts.csv}]
    # data: [{kind: text_file, path: /benchmarks/prompts.txt}]
    # data: [{kind: parquet_file, path: /benchmarks/prompts.parquet}]
    # data: [{kind: arrow_file, path: /benchmarks/prompts.arrow}]
    # data: [{kind: hdf5_file, path: /benchmarks/prompts.hdf5}]
    # data: [{kind: db_file, path: /benchmarks/prompts.db}]
    # data: [{kind: tar_file, path: /benchmarks/prompts.tar}]
    # GuideLLM also provides synthetic_image, synthetic_video, mooncake, and
    # weka data kinds. Their fields are version-specific and pass through.

baseline:
  enabled: true  # Default: true. Tests the fixed configuration first.

optimization:
  maximize: output_tokens_per_second  # Required GuideLLM result metric.
  sampler: tpe                        # grid, random, or tpe. Default: grid.
  trials: 20                          # Required for random/tpe; invalid for grid.
  # For exhaustive Grid search, replace the two lines above with:
  # sampler: grid
  # Do not set trials for Grid; it evaluates every unique combination.
  # For Random search, use sampler: random together with trials.

timeouts:
  startup: 15m    # Default: 15 minutes. Numeric seconds also work.
  # benchmark: 20m  # Optional explicit limit per GuideLLM invocation.
  # Omit benchmark to derive it from max_duration plus a safety margin.
  # The old literal value `auto` is intentionally invalid.

execution:
  host: 127.0.0.1       # Interface used by readiness and GuideLLM.
  health_path: /health  # vLLM readiness endpoint.
  shutdown_grace: 15    # Seconds allowed for owned processes to stop.
  retry:
    max_attempts: 2     # Default: 1. Only transient failures are retried.

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, or CRITICAL. Default: INFO.
```

## Important boundaries

- Only one dataset is allowed in each benchmark run. Use multiple named runs
  for several workloads; multi-dataset runs are a roadmap item.
- There is no separate warm-up switch in vTune. If the installed GuideLLM
  version exposes a warm-up field for a profile, place it inside that profile.
- `analysis` is reserved internally and currently has no user-facing options.
- Console progress is shown at the selected logging level. GuideLLM JSON and
  `benchmark.log` are always preserved for scoring and debugging.
- Random and TPE trial requests larger than the unique search space are capped
  with a warning. Duplicate resolved configurations are never executed.

See [benchmarking](benchmarking.md) for smaller examples and upstream links,
and [configuration](configuration.md) for rendering rules.
