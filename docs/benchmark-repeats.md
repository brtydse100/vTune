# Benchmark repeats and errors

The trusted default is one discarded warmup followed by three measured repeats;
all three are required for ranking. Explicit lower values remain available for
smoke tests, but reports label fewer than three measurements exploratory.
Confidence intervals use Student's t distribution. Critical values through 30
degrees of freedom use a table; larger samples use a finite-degree Student's t
quantile expansion rather than switching to a normal interval. Drift detection requires at
least four sequential measurements and reports when it is unavailable.


```yaml
benchmark:
  repeats: 3
  max_failure_percentage: 2
```

The `vllm-opt` CLI takes the median score across repeats. It records successful,
errored, and incomplete request counts. `max_failure_percentage` accepts a
number from `0` through `100` and defaults to `0`. A workload at or below that
percentage is eligible when at least one request succeeded; a workload above it
is excluded. The decision is made after each benchmark finishes, using its
final request counts. Set `accept_any_request_failures: true` to ignore the
percentage while still requiring at least one successful request and a usable
metric. Request-count runs also require the expected total to be present. A
trial with no eligible workload is not ranked. Remaining trials are ordered by
lowest error percentage, lowest error count, then highest configured metric.

When failures occur, each benchmark artifact directory contains
`failed_requests.json` with the errored and incomplete details exposed by the
selected backend. Treat this file as workload data because it can contain
request arguments or outputs.

See the official
[GuideLLM dataset guide](https://github.com/vllm-project/guidellm/blob/main/docs/guides/datasets.md)
for file schemas and fields that vary by GuideLLM release.
