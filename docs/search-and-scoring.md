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
declared metric is always maximized. If the experiment contains multiple
benchmark runs, vTune combines their normalized metric values into the trial
score while retaining per-run metrics in the artifacts.

The untuned `server.args` configuration runs first as the baseline. The report
shows the best observed configuration and its difference from that baseline.

TPE state is persisted in the run's SQLite study. Runs themselves remain
immutable: a retry creates a new linked run instead of rewriting history.
