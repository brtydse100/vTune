# Release checklist

A release is ready only after all of these checks have recorded artifacts:

- Required public package CI passes on Python 3.11 and 3.12, including the
  behavioral tests and clean wheel checks.
- The external private regression suite passes; its fixtures and output remain
  outside this repository.
- The manually dispatched [real GPU smoke workflow](https://github.com/brtydse100/vllm-config-tuner/actions/workflows/gpu-smoke.yml)
  passes on a native-Linux self-hosted GPU runner.
- The [compatibility matrix](compatibility.md) contains dated evidence for the
  target GPU, driver, CUDA, Python, vLLM, GuideLLM, model, ports, cleanup,
  long-generation, and tensor-parallel cases.
- `pip-audit`, the SBOM, package checks, and the build provenance attestation
  are retained with the release artifacts.
- The working tree contains no generated `dist/`, `build/`, `site/`, runtime
  output, credentials, or private benchmark artifacts.

The PyPI workflow builds and tests the checked-out immutable tag before
publishing. Configure branch protection and the `pypi` environment to require
the public checks and the recorded GPU/private gates before tagging.
