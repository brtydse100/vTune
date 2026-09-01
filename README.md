# vLLM Config Tuner

vLLM Config Tuner is a local-first benchmarking and optimization tool for vLLM
serving configurations. Users define the parameters and workloads they care
about; the `vtune` CLI manages the server lifecycle, runs repeatable benchmarks,
explores the search space, and reports which configurations performed best.

vLLM Config Tuner is alpha software targeting Linux with NVIDIA GPUs and
Python 3.11–3.12. The Python distribution, import namespace, and CLI command
remain `vtune`.

**[Documentation](https://brtydse100.github.io/vllm-config-tuner/)** ·
**[Quick start](https://brtydse100.github.io/vllm-config-tuner/getting-started/)** ·
**[PyPI](https://pypi.org/project/vtune/)**

The current code is verified with vLLM 0.28.0 and GuideLLM 0.7.3 on WSL2
with an RTX 3080. That host required
  `VLLM_USE_V2_MODEL_RUNNER: "0"` because UVA was unavailable and
  `VLLM_USE_FLASHINFER_SAMPLER: "0"` because the CUDA compiler toolkit was
  not installed. Native Linux systems may not require these settings.

Other combinations may work but are not yet verified.

Each new trial stores a typed `execution` assignment in its trial result and
manifest. a5/a6 runs may lack it. Reports show only statistics supplied by the
benchmark backend; a7 offline regeneration corrects derived a6 summaries in a
new destination without changing the source run.

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
the machine. See the [installation guide](https://brtydse100.github.io/vllm-config-tuner/installation/)
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
experiment:
  name: first-run
server:
  model: /models/opt-125m
  gpu-memory-utilization: 0.8
tune:
  max-num-seqs:
    values: [8, 16]
benchmark:
  engine: guidellm  # Default. Use vllm for `vllm bench serve`.
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
The `vtune` CLI binds vLLM to `127.0.0.1` by default. Set `server.host` explicitly
only when the benchmark server must be reachable from another host.

Fixed vLLM flags go directly under `server`; tunable flags use top-level
`tune`. Fixed and tunable environment variables use `env` and `tune_env`.
See the [configuration guide](https://brtydse100.github.io/vllm-config-tuner/configuration/)
for categorical, boolean, integer-range, float-range, list, and environment
examples. The [complete YAML](https://brtydse100.github.io/vllm-config-tuner/full-example/)
and [benchmark guide](https://brtydse100.github.io/vllm-config-tuner/benchmarking/) show
every supported control with copyable examples.

To use vLLM's native benchmark, set `benchmark.engine: vllm`. Its `args`
map directly to `vllm bench serve` flags; the `vtune` CLI supplies the model, server
address, and JSON output path:

```yaml
benchmark:
  engine: vllm
  runs:
    - name: throughput
      args:
        dataset-name: random
        random-input-len: 32
        random-output-len: 16
        num-prompts: 100
        request-rate: inf
        max-concurrency: 16
```

Interactive terminal output uses color and remains concise by default. Set the
standard `NO_COLOR` environment variable to disable color. To stream server and
benchmark logs:

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
dashboard with the best observed configuration, per-benchmark elapsed time,
average/median/P99 latency, baseline comparison, score history,
throughput/latency tradeoff, metric definitions, and observed parameter effects.

Random and TPE runs never execute the same resolved configuration twice. If
`optimization.trials` exceeds the unique search space, the `vtune` CLI warns and runs
every unique configuration once.

Multiple independent trials can run on explicitly assigned, non-overlapping
GPU sets and ports. A sequential or tensor-parallel server receives port 8000
unless `server.port` overrides it; local-parallel trials use their configured
port range. Sequential execution remains the default. See
[parallel trials](https://brtydse100.github.io/vllm-config-tuner/parallel-trials/) for the
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

vLLM Config Tuner is available under the [MIT License](LICENSE).
