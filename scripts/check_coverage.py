"""Enforce repository and risk-focused module coverage thresholds."""

from __future__ import annotations

import json
from pathlib import Path

REPORT = Path("coverage.json")
REQUIRED = {
    "src/vllm_optimizer/managers/run_documents.py": 85,
    "src/vllm_optimizer/managers/run_finalization.py": 85,
    "src/vllm_optimizer/managers/run_results.py": 85,
    "src/vllm_optimizer/managers/run_session.py": 85,
    "src/vllm_optimizer/managers/scoring.py": 85,
    "src/vllm_optimizer/measurement.py": 85,
    "src/vllm_optimizer/orchestrator_messages.py": 85,
    "src/vllm_optimizer/orchestrator_search.py": 85,
    "src/vllm_optimizer/orchestrator_setup.py": 85,
    "src/vllm_optimizer/reporting/dashboard.py": 85,
    "src/vllm_optimizer/reporting/dashboard_selection.py": 85,
    "src/vllm_optimizer/reporting/measurement.py": 85,
    "src/vllm_optimizer/reporting/offline.py": 85,
    "src/vllm_optimizer/reporting/offline_loading.py": 85,
    "src/vllm_optimizer/reporting/reclassify.py": 85,
    "src/vllm_optimizer/reporting/reclassify_scores.py": 85,
    "src/vllm_optimizer/reproduction/manifest.py": 85,
    "src/vllm_optimizer/reproduction/redaction.py": 85,
    "src/vllm_optimizer/terminal.py": 85,
    "src/vllm_optimizer/workers/benchmark.py": 85,
    "src/vllm_optimizer/workers/benchmark_state.py": 85,
    "src/vllm_optimizer/workers/guidellm_completion.py": 85,
    "src/vllm_optimizer/workers/progress_policy.py": 85,
    "src/vllm_optimizer/orchestrator.py": 75,
    "src/vllm_optimizer/execution/scheduler.py": 75,
    "src/vllm_optimizer/execution/slots.py": 75,
    "src/vllm_optimizer/execution/trial_executor.py": 75,
    "src/vllm_optimizer/lifecycle/integrity.py": 75,
    "src/vllm_optimizer/lifecycle/retry.py": 75,
    "src/vllm_optimizer/search/optuna_session.py": 75,
    "src/vllm_optimizer/workers/drain.py": 75,
    "src/vllm_optimizer/workers/process.py": 75,
    "src/vllm_optimizer/workers/readiness.py": 75,
    "src/vllm_optimizer/workers/vllm_benchmark.py": 75,
}


def coverage_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    marker = "/vllm_optimizer/"
    return "src" + normalized[normalized.index(marker) :] if marker in normalized else normalized


def main() -> None:
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    files = {}
    for name, data in document["files"].items():
        files[coverage_name(name)] = data
    failures = []
    for name, minimum in REQUIRED.items():
        if name not in files:
            failures.append(f"{name}: missing from coverage data")
            continue
        actual = float(files[name]["summary"]["percent_covered"])
        if actual + 1e-9 < minimum:
            failures.append(f"{name}: {actual:.1f}% < {minimum}%")
    if failures:
        raise SystemExit("Coverage gates failed:\n" + "\n".join(failures))
    print(f"Per-module coverage gates passed for {len(REQUIRED)} modules")


if __name__ == "__main__":
    main()
