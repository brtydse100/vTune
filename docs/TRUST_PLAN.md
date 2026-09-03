# Trust plan

Status for `0.1.0a13`: **software-side alpha complete; hardware validation pending**.

## Software gates completed

- Incomplete GuideLLM and vLLM request-count runs are ineligible for ranking.
- Explicit benchmark timeouts remain authoritative; duration-based limits are derived conservatively.
- Server drain evidence is required and persisted before a trial completes.
- Public synthetic tests cover configuration, execution, scheduling, retry, process ownership,
  crash finalization, redaction, scoring, reporting, and offline workflows.
- The failure percentage is an eligibility gate. The configured maximize metric is the primary
  objective everywhere; request failure rate and count are deterministic tie-breakers.
- Trusted defaults use one warm-up and three measured repeats. Reports use Student's t intervals,
  label fewer than three measurements exploratory, and state when drift cannot be evaluated.
- Coordinator failures atomically finalize recoverable runs as `failed`; keyboard interruption
  finalizes them as `interrupted`.
- Credentials are recursively redacted from terminal output, manifests, run results, CSV, and HTML.
- CI owns Ruff, formatting, type, coverage, strict documentation, wheel installation, dependency
  audit, SBOM, package metadata, and tag/version gates on Python 3.11 and 3.12.

## Hardware validation pending

No native-Linux, GPU, or real-backend result is claimed by this release. The following evidence
must be produced on rented hardware before promotion beyond the software alpha:

- Native-Linux vLLM 0.28 end-to-end execution.
- L40 and H100 runs, including tensor parallel and at least one multi-GPU run.
- Real long-generation timeout and interruption cleanup.
- Raw GuideLLM versus `vllm bench serve` comparison evidence using identical requests.
- Execution of the repository GPU smoke workflow.

Record GPU, driver, CUDA, Python, vLLM, GuideLLM, model, configuration, raw artifacts, and dated
pass/fail outcomes in `compatibility.md`. Until those checks succeed, the project remains explicitly
**hardware validation pending**.
