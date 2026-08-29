# vTune

vTune is a local-first experimentation and optimization tool for vLLM serving
configurations. Users define the parameters and workloads they care about;
vTune manages the server lifecycle, runs repeatable benchmarks, explores the
search space, and reports which configurations performed best.

## Quick start

Requirements: Linux, an NVIDIA GPU, a local model directory, and working
`vllm` and `guidellm` commands. Install this checkout with:

```bash
pip install -e .
```

Create `experiment.yaml`:

```yaml
schema_version: 1
experiment:
  name: first-run
model:
  path: /models/opt-125m
server:
  args:
    gpu-memory-utilization: 0.8
  tune:
    max-num-seqs:
      values: [8, 16]
benchmark:
  runs:
    - name: throughput
      profile:
        kind: throughput
      constraints:
        - kind: max_requests
          count: 10
      data:
        - kind: synthetic_text
          prompt_tokens: 32
          output_tokens: 16
optimization:
  maximize: output_tokens_per_second
  sampler: tpe
  trials: 2
```

Run it:

```bash
vtune --config experiment.yaml
```

The short form is `vtune -c experiment.yaml`. The command validates the file,
runs the experiment, persists results, and generates its exports and report.

Terminal output is concise by default. To stream vLLM and GuideLLM logs:

```bash
vtune --config experiment.yaml --verbose
```

The persistent equivalent uses GuideLLM's logging level names:

```yaml
logging:
  level: DEBUG
```

Supported levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
Full per-trial log files are always saved. `--verbose` overrides the configured
level with `DEBUG` for that invocation.

Retry one or more selected trials into a new immutable linked run:

```bash
vtune retry --run runs/EXPERIMENT/RUN_ID \
  --trial trial-0001 --trial trial-0004
```

The source run is never modified.

Display every stored vLLM and GuideLLM command for a trial without executing
anything:

```bash
vtune reproduce --run runs/EXPERIMENT/RUN_ID --trial trial-0001
```

Each completed run also contains a self-contained `report.html` decision
dashboard with the best observed configuration, baseline comparison, score
history, throughput/latency tradeoff, and observed parameter effects.

Random and TPE runs never execute the same resolved configuration twice.
`optimization.trials` cannot exceed the number of unique configurations in
the declared search space.

## Product documents

- [First MVP specification](docs/MVP_SPEC.md)
- [Future implementation roadmap](docs/ROADMAP.md)
- [Architecture overview and early sketch](docs/ARCHITECTURE.md)
- [Editable Draw.io architecture diagram](docs/vtune-architecture.drawio)

The MVP specification defines the first releasable version and its acceptance
criteria. The roadmap describes capabilities that should be designed for now
but implemented after the core experiment loop is reliable.
