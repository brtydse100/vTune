# Reports

Every completed run writes a self-contained `report.html` alongside machine-
readable `result.json` and `results.csv` exports. `results.json` is reserved
for raw benchmark output where a backend writes one.

The report is designed to answer, at a glance:

1. Which observed configuration ranked best?
2. How did it compare with the baseline?
3. Which changed parameters were associated with the largest score changes?
4. What throughput and latency tradeoffs appeared across trials?

Top-configuration tables show only settings that varied in the experiment and
remove duplicate configurations. Failed and interrupted trials remain visible
without being ranked as successful results.

The selected-trial summary shows available throughput, TTFT, TPOT, ITL,
end-to-end latency, and total-time measurements. A detailed table shows every
named benchmark execution and workload, including its backend, repeat, `vllm-opt`
wall-clock elapsed time, throughput, median latency, and P99 latency. Only
statistics the backend actually supplied are displayed. Chart axes
are labelled. Parameter importance is exploratory: it groups observed scores
by each setting value and normalizes the between-group score differences; it
does not establish causation.

## Metric calculations

- **Requests/s** is completed requests divided by benchmark measurement time.
- **Output tokens/s** is generated tokens divided by measurement time; total
  tokens/s includes prompt and output tokens.
- **TTFT** measures request start to first generated token.
- **TPOT** measures average time per output token after the first token.
- **ITL** measures delay between consecutive streamed tokens.
- **End-to-end latency** measures request start through complete response.
- **Median** is P50; **P99** means 99% of observations are at or below the value.
- **Elapsed** is measured by the `vllm-opt` CLI from benchmark subprocess launch through
  JSON parsing and excludes vLLM server startup.

Backends calculate request distributions and percentiles. vLLM Optimizer normalizes
names and units but does not derive missing percentiles. Eligible workloads are
averaged within an execution, repeated executions use the median score, and
named benchmark scores are averaged into the trial score.

When a finalist's sequential repeat means drift beyond `analysis.drift_threshold`
(5% by default), the top two affected finalists are rerun sequentially before
the recommendation is finalized. Their validation artifacts are kept under
`validation-001`; a failed validation removes that candidate from the ranking.

If `analysis.llm_summary` is configured, the report also includes a short
OpenAI-compatible summary. Its API key is read only from the named environment
variable and is never persisted. It requires HTTPS except for loopback HTTP.
Name-based redaction reduces accidental disclosure but cannot guarantee that
arbitrary user-provided values contain no secrets. An unavailable endpoint
becomes a report warning and never invalidates the experiment.

Each trial directory also contains its resolved configuration, normalized
result, reproduction manifest, `vllm.log`, and `benchmark.log`. Persistent
values are secret-redacted.

## Offline regeneration

Regenerate `report.html`, `results.csv`, and a validated copy of `result.json`
from stored artifacts alone:

```bash
vllm-opt report --run runs/NAME/RUN_ID
```

The report uses reproduction manifests from the source run while writing all
new output to a separate directory. Required structured data (the run and
trial results and manifests) is validated and stops regeneration when invalid.

To apply a different request-failure policy without starting vLLM or GuideLLM:

```bash
vllm-opt reclassify --run runs/RUN --max-failure-percentage 5
vllm-opt reclassify --run runs/RUN --accept-any-request-failures
```

This reads the stored benchmark measurements, evaluates request failures only
after each stored repeat is complete, recalculates eligibility and rankings, and
writes a new `result.json`, `results.csv`, and `report.html` below the source
run's `reclassified` directory (or `--output`). The source run is not modified.
Missing or changed optional logs and raw artifacts generate visible integrity
warnings. a5/a6 reports may have no execution assignment; a7 recomputes their
derived summaries from normalized trial data without changing the source run.
