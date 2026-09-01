# Optimization and rankings

## Phase 3: Richer optimization and rankings

### Multiple optimization targets

Support several named targets that share the same evaluation cache:

```yaml
optimization:
  targets:
    - name: overall
      trial_share: 0.50
    - name: chat-high-load
      trial_share: 0.25
    - name: code-high-load
      trial_share: 0.25
```

The scheduler allocates trials to targets while deduplicating identical server
configurations. Reports distinguish which target proposed each trial.

### Multi-objective optimization

- Throughput/latency Pareto optimization.
- Performance/cost Pareto optimization.
- Quality/performance tradeoffs.
- NSGA-II sampler support.
- Pareto frontier reporting and interactive filtering.
- Explicit dominance behavior when metrics are missing or constraints fail.

### Additional samplers

- CMA-ES for suitable continuous spaces.
- Gaussian-process optimization for expensive, smaller spaces.
- Quasi-random sampling.
- User-provided Optuna sampler integration.

Each sampler must declare supported parameter types and conditional-space
behavior. The `vllm-opt` CLI should reject incompatible configurations during validation.

### Feasibility-aware search

Repeated OOM or incompatible regions should provide useful information:

- Model feasibility separately from objective quality.
- Avoid repeatedly sampling known-invalid exact combinations.
- Visualize failure regions by parameter.
- Optionally use constrained or feasibility-aware sampling.
- Never convert arbitrary infrastructure failures into evidence that a
  parameter region is inherently invalid.

### Pruning and early stopping

- Stop obviously poor trials after selected scenarios.
- Stop a study after convergence or a no-improvement window.
- Respect scenarios designated as mandatory before pruning.
- Record partial results without presenting them as complete comparisons.
- Account for server startup cost before applying aggressive pruning.

### Advanced ranking policies

- Lexicographic rankings.
- Percentile and trimmed-mean aggregation.
- Custom mathematical score expressions with a safe expression language.
- Scenario tags and boolean filters.
- Minimum-regret and worst-case policies.
- Cost-aware scores.
- User-selected reference configuration normalization.
