# Benchmark configuration

Set `benchmark.engine` to `guidellm` (the default) or `vllm`. Each run invokes
the selected engine against the same vLLM trial. vLLM Config Tuner saves raw
JSON and `benchmark.log`, then normalizes the result for scoring and reporting.

Both adapters expose the same canonical fields: requests/s, output and total
tokens/s, TTFT, TPOT, ITL, end-to-end latency, and successful/errored/incomplete
request totals. Statistical metrics use `average`, `median`, and `p99`. Values
remain absent when the backend did not supply them; vLLM Config Tuner never
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

The `vtune` CLI automatically uses `--backend vllm` and also owns `model`, `host`,
`port`, `base-url`, `save-result`, `append-result`, `result-dir`, and
`result-filename`; do not put them under `args`. Underscores
and hyphens are both accepted in keys. `true` adds a flag and `false` omits it.
A list repeats its flag for every item. Other scalar values are passed as
strings, so new vLLM options do not require a vLLM Config Tuner release.

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

## GuideLLM

A GuideLLM run accepts `name`, `request_format`, `profile`, `constraints`, and
exactly one `data` item.

## Profiles

Use one profile per named run:

```yaml
profile: {kind: synchronous}
```

```yaml
profile: {kind: throughput, max_concurrency: 32, rampup_duration: 10}
```

```yaml
profile: {kind: concurrent, streams: [1, 8, 32], max_concurrency: 32}
```

```yaml
profile: {kind: constant, rate: 10}
```

```yaml
profile: {kind: poisson, rate: 10}
```

```yaml
profile: {kind: sweep, sweep_size: 10, strategy_type: constant}
```

```yaml
profile: {kind: replay, time_scale: 1.0}
```

GuideLLM may add profiles without requiring a vLLM Config Tuner release because profile
fields are passed through. Consult its
[benchmark guide](https://github.com/vllm-project/guidellm/blob/main/docs/getting-started/benchmark.md)
for version-specific fields.

## Constraints

Stop after a request count:

```yaml
constraints:
  - kind: max_requests
    count: 1000
```

Stop after a duration for each profile strategy:

```yaml
constraints:
  - kind: max_duration
    seconds: 2m
```

Constraints can be combined and are passed through to GuideLLM.

`max_requests` is a stopping condition, not a request-serialization setting.
Throughput, constant, and poisson profiles may issue requests concurrently;
GuideLLM drains in-flight requests before it finishes. Use
`profile: {kind: synchronous}` when each request must wait for the previous
response, or set `max_concurrency: 1` where the selected profile supports it.
The `vtune` CLI preserves GuideLLM's normal console and request-draining lifecycle.

## Request formats

Choose the vLLM-compatible route required by the dataset and model:

```yaml
request_format: /v1/completions
```

```yaml
request_format: /v1/chat/completions
```

```yaml
request_format: /v1/responses
```

```yaml
request_format: /v1/embeddings
```

The default is `/v1/completions`.

## Synthetic data

```yaml
data:
  - kind: synthetic_text
    prompt_tokens: 256
    prompt_tokens_stdev: 32
    prompt_tokens_min: 128
    prompt_tokens_max: 384
    output_tokens: 128
    output_tokens_stdev: 16
    output_tokens_min: 64
    output_tokens_max: 192
    turns: 1
```

GuideLLM also exposes `synthetic_image` and `synthetic_video`; use their
version-specific fields from its dataset guide.

## Hugging Face data

```yaml
data:
  - kind: huggingface
    source: garage-bAInd/Open-Platypus
    load_kwargs:
      split: train
```

`kind: hf` is an alias. `source` may also be a local dataset directory.

## Local files

JSON and JSONL use the same kind:

```yaml
data: [{kind: json_file, path: /data/prompts.jsonl}]
```

Other supported file loaders follow the same shape:

```yaml
data: [{kind: csv_file, path: /data/prompts.csv}]
```

```yaml
data: [{kind: text_file, path: /data/prompts.txt}]
```

```yaml
data: [{kind: parquet_file, path: /data/prompts.parquet}]
```

```yaml
data: [{kind: arrow_file, path: /data/prompts.arrow}]
```

```yaml
data: [{kind: hdf5_file, path: /data/prompts.hdf5}]
```

```yaml
data: [{kind: db_file, path: /data/prompts.db}]
```

```yaml
data: [{kind: tar_file, path: /data/prompts.tar}]
```

Files must use columns GuideLLM recognizes automatically. vLLM Config Tuner does not yet
expose GuideLLM's custom column-mapper option.

## Trace replay

```yaml
profile: {kind: replay, time_scale: 1.0}
data:
  - kind: trace_synthetic
    path: /data/trace.jsonl
    timestamp_column: timestamp
    prompt_tokens_column: input_length
    output_tokens_column: output_length
```

`mooncake` and `weka` are alternative GuideLLM trace kinds with their own
default column names.

## Repeats and errors

```yaml
benchmark:
  repeats: 3
```

The `vtune` CLI takes the median score across repeats. It records successful, errored,
and incomplete request counts. A workload with more than 50% errored or
incomplete requests is excluded; a trial with no eligible workload is not
ranked. Remaining trials are ordered by lowest error percentage, lowest error
count, then highest configured metric.

See the official
[GuideLLM dataset guide](https://github.com/vllm-project/guidellm/blob/main/docs/guides/datasets.md)
for file schemas and fields that vary by GuideLLM release.
