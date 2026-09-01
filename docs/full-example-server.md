# Experiment, server, and tuning

```yaml
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

```
