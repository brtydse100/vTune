# Troubleshooting

## vLLM exits during startup

Open the trial's `vllm.log`. CUDA OOM, invalid flags, backend incompatibility,
and unexpected exits are classified on the trial while the study continues.
Reduce memory pressure or remove the incompatible setting, then create a linked
retry run.

## Startup never becomes ready

The `vllm-opt` CLI polls process and endpoint health rather than sleeping for a fixed time.
Increase `timeouts.startup` only if logs show useful model-loading progress.

The `vllm-opt` CLI always passes the same validated port to vLLM and its readiness probe.
Sequential tensor-parallel servers default to port 8000. Local-parallel mode
requires an `execution.ports` range because it starts several server instances.

## Configuration error appears after work starts

Current versions validate nested benchmark options and render every planned
command before creating a run directory. If an invalid YAML-derived value still
reaches a worker, report the YAML and the first error line as a bug.

## Benchmark times out

Set an explicit duration such as `30m` for GuideLLM runs constrained only by
`max_requests` when the one-hour hard cap is insufficient. Request count does
not provide a safe workload-duration estimate. Inspect the timeout message and
`benchmark.log` path it prints.

Request-count GuideLLM and vLLM Bench Serve runs are rejected unless their
normalized totals show every expected request completed successfully. vLLM
must also drain its running and waiting queues before the trial is accepted.
Inspect `results.json`, `drain.json`, `benchmark.log`, and `vllm.log` when that
gate fails. For long generations, still compare requested and observed output
tokens because request completion does not independently prove output length.

## TPE trials are fewer than requested

The `vllm-opt` CLI warns and caps the run to the finite number of unique resolved
configurations. Increase the search space if more distinct trials are needed.

## A retry source folder was deleted

Retry validation fails with a clear integrity error. The `vllm-opt` CLI will not guess or
silently reconstruct a missing source trial because that would break the audit
link to the original run.
