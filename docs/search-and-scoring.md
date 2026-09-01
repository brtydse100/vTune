# Search and scoring

Choose `grid` for exhaustive small spaces, `random` for a bounded sample, or
`tpe` for guided exploration. Random and TPE searches do not execute the same
resolved configuration twice.

```yaml
optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 20
  seed: 42
```

`maximize` names the metric used to rank trials. Direction is inferred: the
declared metric is always maximized. For each named benchmark, the `vtune` CLI averages
the eligible workload metric values, takes the median when it was repeated,
then averages named benchmark scores into the trial score. A workload with
more than half of requests errored or incomplete is excluded; a trial without
an eligible workload is not ranked.

Grid evaluates every unique configuration and is best for small spaces. TPE
uses completed trial results to choose promising configurations, so it is the
better default for larger spaces where exhaustive Grid search is impractical.

The fixed `server` configuration runs first as the baseline. The report
shows the best observed configuration and its difference from that baseline.

TPE state is persisted in the run's SQLite study. Runs themselves remain
immutable: a retry creates a new linked run instead of rewriting history.
