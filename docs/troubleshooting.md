# Troubleshooting

## vLLM exits during startup

Open the trial's `vllm.log`. CUDA OOM, invalid flags, backend incompatibility,
and unexpected exits are classified on the trial while the study continues.
Reduce memory pressure or remove the incompatible setting, then create a linked
retry run.

## Startup never becomes ready

vTune polls process and endpoint health rather than sleeping for a fixed time.
Increase `timeouts.startup` only if logs show useful model-loading progress.

## Benchmark times out

Use `timeouts.benchmark: auto` unless a custom limit is necessary. Inspect
`benchmark.log` for request or dataset failures.

## TPE trials are fewer than requested

The requested trial count cannot exceed the finite number of unique resolved
configurations. Increase the search space or reduce `optimization.trials`.

## A retry source folder was deleted

Retry validation fails with a clear integrity error. vTune will not guess or
silently reconstruct a missing source trial because that would break the audit
link to the original run.
