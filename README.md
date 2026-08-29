# vTune

vTune is a local-first experimentation and optimization tool for vLLM serving
configurations. Users define the parameters and workloads they care about;
vTune manages the server lifecycle, runs repeatable benchmarks, explores the
search space, and reports which configurations performed best.

vTune is alpha software targeting Linux with NVIDIA GPUs and Python 3.11–3.12.

Tested integrations:

- vLLM 0.10.2 with GuideLLM 0.7.3 on WSL2 and an RTX 3080.
- vLLM 0.28.0 with GuideLLM 0.7.3 on the same system. WSL2 required
  `VLLM_USE_V2_MODEL_RUNNER: "0"` because UVA was unavailable and
  `VLLM_USE_FLASHINFER_SAMPLER: "0"` because the CUDA compiler toolkit was
  not installed. Native Linux systems may not require these settings.

Other combinations may work but are not yet verified.

The published `py3-none-any` wheel installs on Linux and Windows. Configuration
validation and stored-result inspection work on Windows, but starting an
experiment is supported only on Linux because vLLM has no native Windows
runtime.

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
        max_concurrency: 16
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
vTune binds vLLM to `127.0.0.1` by default. Set `server.args.host` explicitly
only when the benchmark server must be reachable from another host.

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
- [Contributor guide](CONTRIBUTING.md)
- [Release notes](CHANGELOG.md)

The MVP specification defines the first releasable version and its acceptance
criteria. The roadmap describes capabilities that should be designed for now
but implemented after the core experiment loop is reliable.

vTune is available under the [MIT License](LICENSE).
