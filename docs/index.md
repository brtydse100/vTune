# Tune vLLM with evidence

vTune runs controlled vLLM experiments from one YAML file. You choose the
settings and workload; vTune handles process lifecycle, unique search trials,
failures, persistence, and a decision-focused report.

```bash
pip install "vtune[runtime]"
vtune --config experiment.yaml
```

Use plain `pip install vtune` for configuration and report inspection without
local vLLM execution. [Understand the two installation choices](installation.md).

## What vTune gives you

- A baseline and Grid, Random, or TPE exploration of your chosen settings.
- One or more GuideLLM or vLLM Bench Serve workloads per server configuration.
- Immutable trial artifacts, concise terminal progress, and detailed logs.
- A self-contained HTML report showing the best configuration and observed
  parameter effects.
- Exact, secret-redacted commands for reproducing completed trials.

## Start here

[Run your first experiment](getting-started.md){ .md-button .md-button--primary }
[Read the configuration guide](configuration.md){ .md-button }

!!! note "Alpha software"
    Experiment execution targets Linux with NVIDIA GPUs. The universal Python
    package can be installed elsewhere for configuration and result inspection.
