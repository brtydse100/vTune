# Release checklist

A release is ready only after all of these checks have recorded artifacts:

- Required public package CI passes on Python 3.11 and 3.12, including the
  behavioral tests and clean wheel checks.
- Repository and risk-focused coverage thresholds pass on the designated
  Python 3.12 coverage job; Python 3.11 still runs the complete test suite.
- The external private regression suite passes; its fixtures and output remain
  outside this repository.
- The manually dispatched [real GPU smoke workflow](https://github.com/brtydse100/vllm-optimizer/actions/workflows/gpu-smoke.yml)
  passes on a native-Linux self-hosted GPU runner.
- The [compatibility matrix](compatibility.md) contains dated evidence for the
  target GPU, driver, CUDA, Python, vLLM, GuideLLM, model, ports, cleanup,
  long-generation, and tensor-parallel cases.
- `pip-audit`, the SBOM, package checks, and the build provenance attestation
  are retained with the release artifacts.
- The working tree contains no generated `dist/`, `build/`, `site/`, runtime
  output, credentials, or private benchmark artifacts.

The PyPI workflow builds and tests the checked-out immutable tag before
publishing and verifies that `vX.Y.Z` equals both package and runtime versions.
Configure branch protection with an external required `private-regression`
status check and configure the `pypi` environment to require it. After that
check passes, set the protected environment variable `PRIVATE_REGRESSION_COMMIT`
to the exact release commit SHA. The repository-visible publish job verifies
that SHA before building, so missing or stale private evidence blocks release.
Hardware evidence remains an explicit manual, deferred gate and must not be
marked passed until it runs on the rented host.
