# Contributing

vLLM Optimizer favors small, typed modules with explicit ownership boundaries. Start by
reading the [architecture](ARCHITECTURE.md) and the repository's
[`CONTRIBUTING.md`](https://github.com/brtydse100/vllm-optimizer/blob/main/CONTRIBUTING.md).

Common extension points are separated by responsibility:

- workers own one external operation;
- managers coordinate related workers;
- search sessions propose unique configurations;
- reporting code converts stored results into human-readable exports.

Keep implementations simple and update user-facing documentation. The public
behavioral suite under `tests/` uses only synthetic data and temporary files;
private regression tests may remain outside the checkout when they require
models, hardware, or private fixtures.
