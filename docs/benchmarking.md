# Benchmark configuration

Set `benchmark.engine` to `guidellm` (the default) or `vllm`. Each run invokes
the selected engine against the same vLLM trial. vLLM Optimizer saves raw
JSON and `benchmark.log`, then normalizes the result for scoring and reporting.

Use `benchmark.warmup_repeats` for measured-but-discarded requests before each
benchmark repeat. Set `benchmark.repeats` to at least `benchmark.min_repeats`
for a ranking with the configured confidence policy; the default minimum is 1
for compatibility. Reports show sample variance, an approximate 95% confidence
interval, and flag sequential drift above `analysis.drift_threshold` (5% by
default). The top two flagged finalists are automatically rerun sequentially
before a winner is recommended; validation artifacts are stored under
`validation-001`.

Both adapters expose the same canonical fields: requests/s, output and total
tokens/s, TTFT, TPOT, ITL, end-to-end latency, and successful/errored/incomplete
request totals. Statistical metrics use `average`, `median`, and `p99`. Values
remain absent when the backend did not supply them; vLLM Optimizer never
relabels an average as a percentile. GuideLLM request latency is converted from
seconds to milliseconds. The raw backend JSON remains available unchanged.

## vLLM Bench Serve

Use `args` exactly as flags following `vllm bench serve`:

```yaml
benchmark:
  engine: vllm
  repeats: 2
  runs:
    - name: random-throughput
      args:
        dataset-name: random
        random-input-len: 512
        random-output-len: 128
        random-prefix-len: 0
        num-prompts: 1000
        request-rate: inf
        max-concurrency: 32
        percentile-metrics: ttft,tpot,itl,e2el
        metric-percentiles: 50,90,95,99
        ignore-eos: true
```

The `vllm-opt` CLI automatically uses `--backend vllm` and also owns `model`, `host`,
`port`, `base-url`, `save-result`, `append-result`, `result-dir`, and
`result-filename`; do not put them under `args`. Underscores
and hyphens are both accepted in keys. `true` adds a flag and `false` omits it.
A list repeats its flag for every item. Other scalar values are passed as
strings, so new vLLM options do not require a vLLM Optimizer release.

Common dataset forms:

```yaml
# ShareGPT JSON
args:
  dataset-name: sharegpt
  dataset-path: /benchmarks/ShareGPT_V3.json
  num-prompts: 500

# Hugging Face dataset
args:
  dataset-name: hf
  dataset-path: organization/dataset
  hf-split: test
  num-prompts: 500

# Custom JSON or JSONL supported by the installed vLLM
args:
  dataset-name: custom
  dataset-path: /benchmarks/requests.jsonl
  custom-output-len: 128
  num-prompts: 500

# Prefix-repetition workload
args:
  dataset-name: prefix_repetition
  prefix-repetition-prefix-len: 1024
  prefix-repetition-suffix-len: 128
  prefix-repetition-num-prefixes: 16
  prefix-repetition-output-len: 64
  num-prompts: 512
```

Other upstream datasets include `burstgpt`, `sonnet`, `random-mm`,
`random-rerank`, `custom_audio`, `custom_image`, `spec_bench`, `speed_bench`,
and `timed_trace`. Their arguments can change with vLLM; use the
[official reference](https://docs.vllm.ai/en/latest/cli/bench/serve/) and place
its flags under `args`.

The adapter maps `output_throughput`, `request_throughput`, and
`total_token_throughput` to `output_tokens_per_second`,
`requests_per_second`, and `total_tokens_per_second`. Flat mean, median, and
P99 latency fields are combined into the canonical statistical objects.
Completed, failed, and missing requests use the same error-aware ranking as
GuideLLM.

## More benchmark options

- [GuideLLM profiles, constraints, and request formats](benchmark-guidellm.md)
- [Synthetic, Hugging Face, local-file, and trace datasets](benchmark-data.md)
- [Repeats and error handling](benchmark-repeats.md)
