"""Failure classification and concise log excerpts for managed processes."""

from __future__ import annotations

from pathlib import Path

from vllm_optimizer.domain.results import Failure

_PATTERNS = (
    (("uva is not available",), "uva_unavailable", False),
    (("cuda out of memory", "torch.outofmemoryerror", "cuda oom"), "cuda_oom", False),
    (("no such option", "unrecognized arguments", "invalid value for"), "invalid_argument", False),
    (("unsupported", "not supported", "incompatible"), "unsupported_configuration", False),
    (("connection refused", "connection reset", "service unavailable"), "connection_failed", True),
)


def classified_failure(log_path: Path, default_code: str, message: str, retryable: bool = False) -> Failure:
    excerpt = log_excerpt(log_path)
    lowered = excerpt.lower()
    code = default_code
    for patterns, classified, transient in _PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            code, retryable = classified, transient
            break
    detail = f"{message}\nLatest log output:\n{excerpt}" if excerpt else message
    return Failure(code, detail, retryable)


def log_excerpt(path: Path, lines: int = 8) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    useful = [line.strip() for line in content if line.strip()]
    important = [line for line in useful if _looks_like_cause(line)]
    selected = [*important[-4:], *useful[-lines:]]
    return "\n".join(dict.fromkeys(selected))


def _looks_like_cause(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered for marker in ("runtimeerror:", "valueerror:", "outofmemoryerror:", "error:", "exception:")
    )
