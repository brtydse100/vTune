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

## Product documents

- [First MVP specification](docs/MVP_SPEC.md)
- [Future implementation roadmap](docs/ROADMAP.md)
- [Architecture overview and early sketch](docs/ARCHITECTURE.md)
- [Editable Draw.io architecture diagram](docs/vtune-architecture.drawio)

The MVP specification defines the first releasable version and its acceptance
criteria. The roadmap describes capabilities that should be designed for now
but implemented after the core experiment loop is reliable.
