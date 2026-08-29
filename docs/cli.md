# CLI reference

## Run an experiment

```bash
vtune --config experiment.yaml
vtune -c experiment.yaml --verbose
```

`--verbose` streams vLLM and GuideLLM output and overrides the YAML logging
level with `DEBUG` for that invocation.

## Retry selected trials

```bash
vtune retry --run runs/NAME/RUN_ID \
  --trial trial-0001 --trial trial-0004
```

The source run and trials are validated first. The command creates a new linked
run containing only the requested fixed configurations.

## Display reproduction commands

```bash
vtune reproduce --run runs/NAME/RUN_ID --trial trial-0001
```

This reads stored artifacts and prints the vLLM and benchmark commands. It does
not start a server or execute the commands.

Use `vtune --help` or a subcommand's `--help` for the complete option list.
