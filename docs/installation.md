# Installation choices

vLLM Config Tuner has two intentionally different installations:

| Installation | Includes | Use it for |
| --- | --- | --- |
| `pip install vtune` | vLLM Config Tuner, Optuna, and PyYAML | Validate YAML, inspect saved runs, regenerate reports, and reproduce commands without executing them |
| `pip install "vtune[runtime]"` | Everything above, plus vLLM and GuideLLM | Start vLLM and run complete local experiments |

## Run experiments

Use Linux or WSL with an NVIDIA GPU. Create a virtual environment so Ubuntu's
system Python remains untouched:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "vtune[runtime]"
```

Verify all three commands come from the active environment:

```bash
which vtune
which vllm
which guidellm
vtune --help
vllm --help
vllm bench serve --help
guidellm --help
```

The runtime installation is larger because vLLM selects PyTorch, CUDA kernels,
and other GPU-specific packages. vLLM Config Tuner does not choose a CUDA version itself;
the correct combination depends on the vLLM release, GPU, NVIDIA driver, and
platform. See [compatibility](compatibility.md) before changing an existing
working vLLM environment.

## Inspect without running

Use the smaller core installation on Linux, Windows, or macOS:

```bash
python -m pip install vtune
```

This is useful for configuration validation and stored-result/report work. It
cannot run an experiment unless `vllm` and the selected benchmark executable
are already on `PATH`. GuideLLM is needed only for `engine: guidellm`; vLLM
Bench Serve is included with vLLM.

## Windows versus WSL

- Native Windows can install the core package and inspect saved work.
- Native Windows cannot launch vLLM experiments.
- WSL is Linux and can run experiments when NVIDIA GPU support is configured.
- Inside WSL, Windows files use paths such as `/mnt/c/Users/Ido/...`, not
  `C:\Users\Ido\...`.

If the `vtune` CLI cannot find a runtime command, it reports which command is missing and
suggests `pip install "vtune[runtime]"`.
