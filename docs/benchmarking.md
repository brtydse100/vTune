# Benchmark configuration

Each `benchmark.runs` entry becomes one GuideLLM invocation against the same
vLLM trial. It accepts `name`, `request_format`, `profile`, `constraints`, and
exactly one `data` item. vTune always saves GuideLLM JSON and `benchmark.log`.

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

GuideLLM may add profiles without requiring a vTune release because profile
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

Files must use columns GuideLLM recognizes automatically. vTune does not yet
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

vTune takes the median score across repeats. It records successful, errored,
and incomplete request counts. A workload with more than 50% errored or
incomplete requests is excluded; a trial with no eligible workload is not
ranked. Remaining trials are ordered by lowest error percentage, lowest error
count, then highest configured metric.

See the official
[GuideLLM dataset guide](https://github.com/vllm-project/guidellm/blob/main/docs/guides/datasets.md)
for file schemas and fields that vary by GuideLLM release.
