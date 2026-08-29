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
model:
  path: /models/opt-125m
server:
  args:
    gpu-memory-utilization: 0.8
  tune:
    max-num-seqs:
      values: [8, 16]
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

Next, learn how [configuration](configuration.md) maps to vLLM and GuideLLM.
