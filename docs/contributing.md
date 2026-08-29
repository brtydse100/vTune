# Contributing

vTune favors small, typed modules with explicit ownership boundaries. Start by
reading the [architecture](ARCHITECTURE.md) and the repository's
[`CONTRIBUTING.md`](https://github.com/brtydse100/vTune/blob/main/CONTRIBUTING.md).

Common extension points are separated by responsibility:

- workers own one external operation;
- managers coordinate related workers;
- search sessions propose unique configurations;
- reporting code converts stored results into human-readable exports.

Keep implementations simple, update user-facing documentation, and follow the
project's private-test policy. Public pull requests must not add tests, fixtures,
snapshots, or expected-result files to the repository.
