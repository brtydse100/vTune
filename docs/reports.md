# Reports

Every completed run writes a self-contained `report.html` alongside machine-
readable `results.json` and `results.csv` exports.

The report is designed to answer, at a glance:

1. Which observed configuration ranked best?
2. How did it compare with the baseline?
3. Which changed parameters were associated with the largest score changes?
4. What throughput and latency tradeoffs appeared across trials?

Top-configuration tables show only settings that varied in the experiment and
remove duplicate configurations. Failed and interrupted trials remain visible
without being ranked as successful results.

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
new output to a separate directory. Missing, corrupt, or mismatched artifacts
stop regeneration with a clear error instead of producing a partial report.
