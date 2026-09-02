"""Extract backend request failures into a focused JSON artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


def save_failed_requests(source: Path, backend: str, destination: Path) -> bool:
    """Write failures from *source* and return whether any were found."""
    try:
        document = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    failures = (_guidellm_failures(document) if backend == "guidellm"
                else _vllm_failures(document))
    if not failures:
        return False
    output = {
        "schema_version": 1,
        "backend": backend,
        "source": str(source),
        "failed_request_count": len(failures),
        "requests": failures,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return True


def _guidellm_failures(document: object) -> list[dict[str, object]]:
    if not isinstance(document, Mapping):
        return []
    benchmarks = document.get("benchmarks", [])
    if not isinstance(benchmarks, list):
        return []
    failures: list[dict[str, object]] = []
    for workload, benchmark in enumerate(benchmarks):
        requests = benchmark.get("requests", {}) if isinstance(benchmark, Mapping) else {}
        if not isinstance(requests, Mapping):
            continue
        for status in ("errored", "incomplete"):
            entries = requests.get(status, [])
            if isinstance(entries, list):
                failures.extend({"workload": workload, "status": status, "request": entry}
                                for entry in entries)
    return failures


def _vllm_failures(document: object) -> list[dict[str, object]]:
    if not isinstance(document, Mapping):
        return []
    errors = document.get("errors", [])
    if not isinstance(errors, list):
        return []
    input_lens = document.get("input_lens", [])
    output_lens = document.get("output_lens", [])
    failures = []
    for index, error in enumerate(errors):
        if not error:
            continue
        item: dict[str, object] = {"index": index, "status": "errored", "error": error}
        if isinstance(input_lens, list) and index < len(input_lens):
            item["input_length"] = input_lens[index]
        if isinstance(output_lens, list) and index < len(output_lens):
            item["output_length"] = output_lens[index]
        failures.append(item)
    return failures
