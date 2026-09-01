# Benchmark repeats and errors


```yaml
benchmark:
  repeats: 3
```

The `vllm-opt` CLI takes the median score across repeats. It records successful, errored,
and incomplete request counts. A workload with more than 50% errored or
incomplete requests is excluded; a trial with no eligible workload is not
ranked. Remaining trials are ordered by lowest error percentage, lowest error
count, then highest configured metric.

See the official
[GuideLLM dataset guide](https://github.com/vllm-project/guidellm/blob/main/docs/guides/datasets.md)
for file schemas and fields that vary by GuideLLM release.
