# Quick start

You need Linux, an NVIDIA GPU, a local model directory, and working `vllm` and
`guidellm` commands.

## 1. Install

```bash
pip install vtune
```

## 2. Create `experiment.yaml`

```yaml
schema_version: 1
experiment:
  name: first-run
server:
  model: /models/opt-125m
  gpu-memory-utilization: 0.8
tune:
  max-num-seqs:
    values: [8, 16]
  enforce-eager:
    values: [true, false]
  max-num-batched-tokens:
    min: 4096
    max: 8192
    step: 4096
env:
  CUDA_VISIBLE_DEVICES: "0"
tune_env:
  VLLM_USE_FLASHINFER_SAMPLER:
    values: ["0", "1"]
benchmark:
  runs:
    - name: throughput
      profile:
        kind: throughput
        max_concurrency: 16
      constraints:
        - kind: max_requests
          count: 10
      data:
        - kind: synthetic_text
          prompt_tokens: 32
          output_tokens: 16
optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 2
```

## 3. Run

```bash
vtune --config experiment.yaml
```

Open `report.html` in the printed run directory when the run completes. Add
`--verbose` to stream server and benchmark logs while trials execute.

`values` accepts categorical strings, numbers, or booleans. Numeric parameters
can instead use inclusive `min`, `max`, and `step` ranges. The same two forms
work under `tune_env`; selected environment values are converted to strings.

Next, learn how [configuration](configuration.md) maps to vLLM and GuideLLM.
