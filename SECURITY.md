# Security policy

Configuration and reports recursively redact conventionally named credentials,
including tokens, passwords, authorization headers, cookies, access keys, and
client secrets. Command redaction covers `--key value` and `--key=value` forms.
Redaction changes display and persistence only, never subprocess input. Arbitrary
secrets stored under non-sensitive names cannot be recognized reliably.

## Supported versions

Security fixes are applied to the latest published release. Alpha releases
are experimental and should not be used with untrusted configuration files or
model-serving endpoints.

## Reporting a vulnerability

Please report vulnerabilities privately through the repository's GitHub
security-advisory process. Do not include API keys, model credentials, or
benchmark data in a public issue. Include the affected version, a minimal
reproduction, and the impact when safe to do so.

Reports are acknowledged within five business days. We will coordinate a fix,
release, and disclosure timeline with the reporter.
