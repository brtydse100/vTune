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

The selected-trial table shows available throughput, TTFT, end-to-end latency,
and total-time measurements with only the average, median, or P99 values the
backend actually supplied. Chart axes
are labelled. Parameter importance is exploratory: it groups observed scores
by each setting value and normalizes the between-group score differences; it
does not establish causation.

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
vtune report --run runs/NAME/RUN_ID
```

The report uses reproduction manifests from the source run while writing all
new output to a separate directory. Required structured data (the run and
trial results and manifests) is validated and stops regeneration when invalid.
Missing or changed optional logs and raw artifacts generate visible integrity
warnings. a5/a6 reports may have no execution assignment; a7 recomputes their
derived summaries from normalized trial data without changing the source run.
