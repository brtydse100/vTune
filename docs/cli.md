# CLI reference

## Run an experiment

```bash
vllm-opt --config experiment.yaml
vllm-opt -c experiment.yaml --verbose
```

`--verbose` streams vLLM server and selected benchmark output and overrides the YAML logging
level with `DEBUG` for that invocation.

## Retry selected trials

```bash
vllm-opt retry --run runs/NAME/RUN_ID \
  --trial trial-0001 --trial trial-0004
```

The source run and trials are validated first. The command creates a new linked
run containing only the requested fixed configurations.

## Display reproduction commands

```bash
vllm-opt reproduce --run runs/NAME/RUN_ID --trial trial-0001
```

This reads stored artifacts and prints the vLLM and benchmark commands. It does
not start a server or execute the commands.

## Regenerate a report offline

```bash
vllm-opt report --run runs/NAME/RUN_ID
vllm-opt report --run runs/NAME/RUN_ID --output /tmp/vllm-opt-report
```

The command reads the immutable run and trial results without loading a model
or invoking vLLM or GuideLLM. By default it creates a timestamped directory
under `RUN_ID/regenerated/`; an existing destination is never overwritten.

Use `vllm-opt --help` or a subcommand's `--help` for the complete option list.
