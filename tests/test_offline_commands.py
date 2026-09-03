import json
from pathlib import Path

import pytest

from vllm_optimizer.reporting.offline import regenerate_report
from vllm_optimizer.reporting.offline_loading import _attempt, _failure, _status, read_object
from vllm_optimizer.reporting.reclassify import reclassify_run


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _run(tmp_path: Path) -> Path:
    run = tmp_path / "run-1"
    benchmark = {
        "name": "requests",
        "backend": "synthetic",
        "backend_version": "1",
        "raw_artifact": "raw.json",
        "repeat": None,
        "elapsed_seconds": 1.0,
        "workloads": [
            {
                "index": 0,
                "configuration": {},
                "metrics": {
                    "requests_per_second": {"average": 4.0},
                    "request_totals": {"successful": 9, "errored": 1, "incomplete": 0},
                },
            }
        ],
    }
    trial = {
        "schema_version": 1,
        "trial_id": "trial-1",
        "status": "completed",
        "benchmarks": [benchmark],
        "artifacts": {},
        "attempts": [],
        "execution": {"mode": "sequential"},
    }
    summary = {
        "trial_id": "trial-1",
        "status": "completed",
        "failure": None,
        "benchmark_count": 1,
        "metrics": {},
        "benchmarks": [benchmark],
        "execution": {"mode": "sequential"},
    }
    score = {
        "trial_id": "trial-1",
        "score": 4.0,
        "successful_requests": 9,
        "errored_requests": 1,
        "incomplete_requests": 0,
        "excluded_workloads": 0,
        "error_rate": 0.1,
        "server_args": {"max-num-seqs": 2},
        "server_env": {},
    }
    result = {
        "schema_version": 1,
        "run_id": "run-1",
        "maximize": "requests_per_second",
        "status": "completed",
        "started_at": None,
        "completed_at": None,
        "execution_mode": "sequential",
        "trials": [summary],
        "ranking": [score],
        "baseline": None,
        "best_by_benchmark": {"requests": score},
        "benchmark_order": ["requests"],
    }
    manifest = {
        "schema_version": 1,
        "trial_id": "trial-1",
        "commands": [],
        "execution": {"mode": "sequential"},
        "artifacts": {},
        "model_path": str(tmp_path),
        "parameters": {"fixed_args": {}, "selected_args": {"max-num-seqs": 2}, "fixed_env": {}, "selected_env": {}},
        "benchmark": {
            "repeats": 1,
            "min_repeats": 1,
            "warmup_repeats": 0,
            "max_failure_percentage": 10,
            "runs": [{"name": "requests", "profile": {}, "constraints": [], "data": [{}]}],
        },
        "policy": {"timeouts": {}, "execution": {}},
    }
    _write(run / "result.json", result)
    _write(run / "trials" / "trial-1" / "result.json", trial)
    _write(run / "trials" / "trial-1" / "manifest.json", manifest)
    return run


def test_offline_regeneration_and_reclassification_are_immutable(tmp_path: Path) -> None:
    run = _run(tmp_path)
    original = (run / "result.json").read_bytes()

    generated = regenerate_report(run, tmp_path / "regenerated")
    assert generated.html.exists() and generated.csv.exists()
    assert (run / "result.json").read_bytes() == original

    rejected = reclassify_run(run, 0, tmp_path / "reclassified")
    document = json.loads(rejected.result.read_text(encoding="utf-8"))
    assert document["ranking"] == []
    assert document["trials"][0]["status"] == "failed"
    assert (run / "result.json").read_bytes() == original

    accepted = reclassify_run(run, 10, tmp_path / "accepted")
    accepted_document = json.loads(accepted.result.read_text(encoding="utf-8"))
    assert accepted_document["ranking"][0]["trial_id"] == "trial-1"


def test_offline_regeneration_uses_persisted_effective_policy(tmp_path: Path) -> None:
    run = _run(tmp_path)
    result_path = run / "result.json"
    document = json.loads(result_path.read_text(encoding="utf-8"))
    document["benchmark_policy"] = {
        "repeats": 4,
        "minimum_repeats": 2,
        "warmup_repeats": 1,
        "drift_threshold": 0.17,
        "maximum_failure_percentage": 42.0,
    }
    _write(result_path, document)

    generated = regenerate_report(run, tmp_path / "policy-report")
    html = generated.html.read_text(encoding="utf-8")
    assert "At least 2 measured repeats" in html
    assert "more than 17%" in html
    assert "exceed\n42% of all requests" in html


def test_legacy_offline_policy_honors_accept_any_and_effective_minimum(tmp_path: Path) -> None:
    run = _run(tmp_path)
    manifest_path = run / "trials" / "trial-1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmark = manifest["benchmark"]
    benchmark.pop("min_repeats")
    benchmark.pop("max_failure_percentage")
    benchmark["repeats"] = 3
    benchmark["accept_any_request_failures"] = True
    _write(manifest_path, manifest)

    generated = regenerate_report(run, tmp_path / "legacy-report")
    html = generated.html.read_text(encoding="utf-8")
    assert "At least 3 measured repeats" in html
    assert "exceed\n100% of all requests" in html

    reclassified = reclassify_run(run, 100, tmp_path / "legacy-reclassified")
    result = json.loads(reclassified.result.read_text(encoding="utf-8"))
    assert result["ranking"] == []
    assert result["benchmark_policy"]["minimum_repeats"] == 3


def test_offline_rejects_identity_and_execution_mismatches(tmp_path: Path) -> None:
    run = _run(tmp_path)
    document = json.loads((run / "result.json").read_text(encoding="utf-8"))
    document["run_id"] = "wrong"
    _write(run / "result.json", document)
    with pytest.raises(ValueError, match="ID does not match"):
        regenerate_report(run, tmp_path / "bad")

    run = _run(tmp_path / "again")
    manifest_path = run / "trials" / "trial-1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution"] = {"mode": "local_parallel", "worker": "w", "devices": [0], "port": 8100}
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="execution mismatch"):
        regenerate_report(run, tmp_path / "mismatch")


def test_offline_loading_rejects_malformed_documents(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Cannot read"):
        read_object(tmp_path / "missing.json", "result")
    _write(tmp_path / "list.json", [])
    with pytest.raises(ValueError, match="JSON object"):
        read_object(tmp_path / "list.json", "result")
    with pytest.raises(ValueError, match="stored failure"):
        _failure("invalid")
    with pytest.raises(ValueError, match="invalid status"):
        _status("unknown", "trial")
    with pytest.raises(ValueError, match="invalid index"):
        _attempt({"index": "one"})
