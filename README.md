# vTune

vTune is a local-first experimentation and optimization tool for vLLM serving
configurations. Users define the parameters and workloads they care about;
vTune manages the server lifecycle, runs repeatable benchmarks, explores the
search space, and reports which configurations performed best.

## Quick start

```bash
vtune --config experiment.yaml
```

The short form is `vtune -c experiment.yaml`. The command validates the file,
runs the experiment, persists results, and generates its exports and report.

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

## Product documents

- [First MVP specification](docs/MVP_SPEC.md)
- [Future implementation roadmap](docs/ROADMAP.md)
- [Architecture overview and early sketch](docs/ARCHITECTURE.md)
- [Editable Draw.io architecture diagram](docs/vtune-architecture.drawio)

The MVP specification defines the first releasable version and its acceptance
criteria. The roadmap describes capabilities that should be designed for now
but implemented after the core experiment loop is reliable.
