# vTune

vTune is a local-first experimentation and optimization tool for vLLM serving
configurations. Users define the parameters and workloads they care about;
vTune manages the server lifecycle, runs repeatable benchmarks, explores the
search space, and reports which configurations performed best.

vTune is alpha software targeting Linux with NVIDIA GPUs and Python 3.11–3.12.

**[Documentation](https://brtydse100.github.io/vTune/)** ·
**[Quick start](https://brtydse100.github.io/vTune/getting-started/)** ·
**[PyPI](https://pypi.org/project/vtune/)**

The current code is verified with vLLM 0.28.0 and GuideLLM 0.7.3 on WSL2
with an RTX 3080. That host required
  `VLLM_USE_V2_MODEL_RUNNER: "0"` because UVA was unavailable and
  `VLLM_USE_FLASHINFER_SAMPLER: "0"` because the CUDA compiler toolkit was
  not installed. Native Linux systems may not require these settings.

Other combinations may work but are not yet verified.

The published `py3-none-any` wheel installs on Linux and Windows. Configuration
validation and stored-result inspection work on Windows, but starting an
experiment is supported only on Linux because vLLM has no native Windows
runtime.

## Installation

Choose the installation that matches what you want to do:

| Goal | Command | Platform |
| --- | --- | --- |
| Run complete experiments | `pip install "vtune[runtime]"` | Linux/WSL with NVIDIA GPU |
| Read configs, results, and reports | `pip install vtune` | Linux, Windows, or macOS |

The core package intentionally does not install GPU frameworks. The `runtime`
extra adds vLLM and GuideLLM, which select large PyTorch/CUDA dependencies for
the machine. See the [installation guide](https://brtydse100.github.io/vTune/installation/)
for virtual environments, CUDA guidance, and verification commands.

## Quick start

Create and activate a Python 3.11 or 3.12 virtual environment on Linux or WSL,
then install the complete experiment runtime:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "vtune[runtime]"
vllm --help
guidellm --help
```

Create `experiment.yaml`:

```yaml
schema_version: 1
experiment:
  name: first-run
server:
  model: /models/opt-125m
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
vTune binds vLLM to `127.0.0.1` by default. Set `server.host` explicitly
only when the benchmark server must be reachable from another host.

Fixed vLLM flags go directly under `server`; tunable flags use top-level
`tune`. Fixed and tunable environment variables use `env` and `tune_env`.
See the [configuration guide](https://brtydse100.github.io/vTune/configuration/)
for categorical, boolean, integer-range, float-range, list, and environment
examples. The [complete YAML](https://brtydse100.github.io/vTune/full-example/)
and [benchmark guide](https://brtydse100.github.io/vTune/benchmarking/) show
every supported control with copyable examples.

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

Random and TPE runs never execute the same resolved configuration twice. If
`optimization.trials` exceeds the unique search space, vTune warns and runs
every unique configuration once.

Multiple independent trials can run on explicitly assigned, non-overlapping
GPU sets and ports. Sequential execution remains the default. See
[parallel trials](https://brtydse100.github.io/vTune/parallel-trials/) for the
YAML and measurement caveats.

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
