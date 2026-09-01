# Benchmark datasets

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

Files must use columns GuideLLM recognizes automatically. vLLM Optimizer does not yet
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
