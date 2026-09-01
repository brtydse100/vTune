# vLLM Optimizer Future Implementation Roadmap

This roadmap lists capabilities that follow the first MVP described in
[MVP_SPEC.md](MVP_SPEC.md). It is organized by dependency and product value,
not by promised release dates.

## Guiding rules

Future work should preserve these invariants:

- Raw measurements remain separate from ranking and optimization policy.
- A trial is one server configuration; a scenario evaluation is one workload
  result within that trial.
- Reports remain regenerable from persisted data without GPUs or benchmarks.
- Benchmark and server integrations use adapters.
- Local execution remains the simplest default even after distributed support
  exists.
- New features must not weaken owned-process cleanup, immutable-run integrity,
  or secret handling.
- Any result labeled â€œbestâ€ must state the population and scoring policy from
  which it was selected.

## Detailed phases

- [Experiment engine and benchmark coverage](roadmap/engine.md)
- [Optimization and rankings](roadmap/optimization.md)
- [Faster local execution](roadmap/local-execution.md)
- [Distributed execution and reporting](roadmap/distributed.md)
- [Automation, APIs, cost, and capacity](roadmap/integrations.md)
- [Cross-cutting requirements](roadmap/requirements.md)

## Suggested release sequence

The roadmap can be grouped into practical releases:

| Release | Theme | Main outcome |
|---|---|---|
| MVP | Reliable local loop | Trustworthy unattended single-host experiments |
| 0.2 | Measurement confidence | Advanced retries, drift detection, statistics, richer comparisons |
| 0.3 | Benchmark breadth | vLLM Bench Serve, datasets, quality gates |
| 0.4 | Optimization depth | Multiple targets, Pareto search, pruning |
| 0.5 | Faster local runs | Cache reuse, controlled reuse, parallel GPU workers |
| 0.6 | Interactive analysis | Local UI, richer rankings and parameter analysis |
| 0.7 | Distributed execution | Remote workers and shared artifacts |
| 1.0 | Stable platform | Versioned APIs, plugins, migrations, compatibility guarantees |

Version numbers are illustrative. Reliability gates should determine release
timing rather than the number of accumulated features.

## Prioritization test

Before adding a roadmap feature, ask:

1. Does it improve measurement trust, failure recovery, or reproducibility?
2. Does it help users answer a decision they cannot answer from raw results?
3. Can it be implemented without weakening the local-first workflow?
4. Does its persisted data model remain useful if the implementation changes?
5. Is its complexity justified relative to model startup and benchmark cost?

Features that improve reliability and interpretability should normally precede
features that only add optimizer variety or visual polish.
