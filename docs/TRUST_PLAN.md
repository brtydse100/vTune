# Trust plan

Follow these tasks in order. Finish and verify one task before starting the
next. Keep every change small; do not redesign unrelated code.

## 1. Reject incomplete GuideLLM runs

Goal: never rank a request-count benchmark unless every expected request
finished successfully.

1. Read the `max_requests` count from the selected benchmark run.
2. In `workers/benchmark.py`, compare it with the normalized successful,
   errored, and incomplete totals after parsing `results.json`.
3. Fail the worker when the expected total is missing, any request failed, or
   the successful count differs from the expected count.
4. Put private fixtures and tests outside the repository.
5. Test an exact success, one error, one incomplete request, and a missing total.

Done when an incomplete result cannot enter scoring or ranking.

## 2. Fix benchmark timeout policy

Goal: do not kill a valid long-generation workload after three minutes.

1. Change `benchmarks/timing.py` so `max_requests` without `max_duration` does
   not receive the current 180-second guess.
2. Require an explicit `timeouts.benchmark`, or choose a documented conservative
   limit that cannot be mistaken for a workload-duration estimate.
3. Keep explicit user timeouts unchanged.
4. Add private tests for request-count, duration, and explicit-timeout runs.

Done when a 20-minute configured benchmark can run longer than three minutes.

## 3. Confirm the server drained

Goal: accept results only after vLLM has no queued or running requests.

1. Add a small worker that checks vLLM's supported runtime metrics after the
   benchmark process exits.
2. Poll for zero running and waiting requests with a short configured grace.
3. Fail the trial if the server stays busy or the evidence cannot be read.
4. Save the final drain evidence with the trial artifacts.
5. Test zero, delayed-zero, timeout, and unavailable-metrics cases privately.

Done when vLLM cannot still be generating after a trial is marked complete.

## 4. Make behavioral tests public

Goal: let contributors verify observable behavior before opening a pull request.

1. Revisit the private-test-only project rule with the maintainer.
2. Publish tests that contain no models, secrets, GPU data, or private fixtures.
3. Cover configuration, command rendering, result parsing, scoring, and reports.
4. Run them in `.github/workflows/package-check.yml` on Python 3.11 and 3.12.

Done when a pull request cannot pass CI with a known behavioral regression.

## 5. Prove backend comparability

Goal: demonstrate what GuideLLM and `vllm bench serve` agree on.

1. Define one small fixed dataset and identical request settings.
2. Record concurrency, sampling, EOS behavior, prompt length, and output length.
3. Run both backends and preserve their raw JSON.
4. Compare canonical units, request totals, throughput, and latency definitions.
5. Document expected differences instead of hiding them through normalization.

Done when a user can reproduce the comparison from a published procedure.

## 6. Publish a GPU validation matrix

Goal: state exactly where the product has been exercised.

Test native Linux on L40 and H100 with single GPU, tensor parallel, explicit
ports, interruption cleanup, long generation, and at least one multi-GPU run.
Record GPU, driver, CUDA, Python, vLLM, GuideLLM, model, and pass/fail outcome in
`compatibility.md`.

Done when every supported combination has dated evidence and known limitations.

## 7. Add measurement and release safeguards

Goal: make rankings statistically and operationally defensible.

1. Add warm-up policy, minimum repeats, variance, and confidence intervals.
2. Detect drift and sequentially rerun finalists before recommending a winner.
3. Add `SECURITY.md`, dependency scanning, artifact attestations, and an SBOM.
4. Require public CI, private regression tests, a real-GPU smoke test, and clean
   artifact checks before tagging a release.

Done when the report communicates uncertainty and every release has auditable
test and supply-chain evidence.
