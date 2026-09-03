import json
from pathlib import Path

import pytest

from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.lifecycle.integrity import artifact_warnings, describe_artifacts, load_retry_source
from vllm_optimizer.lifecycle.retry import load_retry_plan
from vllm_optimizer.reproduction.display import reproduce_trial
from vllm_optimizer.reproduction.export import export_vllm_command
from vllm_optimizer.reproduction.manifest import ManifestWriter
from vllm_optimizer.reproduction.models import CommandRecord, StartupRecord
from vllm_optimizer.search.grid import TrialParameters
from vllm_optimizer.workers.base import TrialContext


def _source(tmp_path: Path) -> tuple[Path, Path]:
    run = tmp_path / "experiment" / "run-1"
    model = tmp_path / "model"
    model.mkdir()
    artifact = run / "trials" / "trial-1" / "benchmark.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("evidence", encoding="utf-8")
    config = VTuneConfig(
        1,
        ExperimentConfig("experiment", str(tmp_path)),
        {"model": str(model), "dtype": "float16"},
        env={"API_KEY": "sentinel", "SAFE": "yes"},
        benchmark={
            "repeats": 1,
            "min_repeats": 1,
            "warmup_repeats": 0,
            "runs": [{"name": "requests", "profile": {}, "constraints": [], "data": [{}]}],
        },
        optimization={"maximize": "requests_per_second"},
    )
    context = TrialContext("trial-1", artifacts={"benchmark": str(artifact)})
    context.commands.append(
        CommandRecord("vllm", ("vllm", "serve", "--api-key", "sentinel"), 1, {"API_KEY": "sentinel", "SAFE": "yes"})
    )
    context.startups.append(StartupRecord(1, 1.25))
    manifest = artifact.parent / "manifest.json"
    ManifestWriter({"python_version": "3.12", "software": {}, "gpus": []}).write(
        manifest, config, TrialParameters("trial-1", {"max-num-seqs": 2}, {}), context, "completed"
    )
    (run / "result.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-1",
                "status": "completed",
                "maximize": "requests_per_second",
                "trials": [{"trial_id": "trial-1"}],
            }
        ),
        encoding="utf-8",
    )
    return run, artifact


def test_manifest_reproduction_retry_and_integrity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, artifact = _source(tmp_path)

    manifest = json.loads((artifact.parent / "manifest.json").read_text(encoding="utf-8"))
    serialized = json.dumps(manifest)
    assert "sentinel" not in serialized
    assert describe_artifacts({"artifact": artifact})["artifact"]["exists"]
    assert artifact_warnings(manifest, "trial-1") == []
    assert "vllm serve" in export_vllm_command(run, "trial-1")
    reproduction = reproduce_trial(run, "trial-1")
    assert "display only" in reproduction and "<redacted>" in reproduction

    monkeypatch.setenv("API_KEY", "replacement")
    plan = load_retry_plan(run, ["trial-1"])
    assert plan.source_run_id == "run-1"
    assert plan.config.env["API_KEY"] == "replacement"
    assert plan.trials[0].server_args == {"max-num-seqs": 2}

    artifact.write_text("changed", encoding="utf-8")
    assert "checksum does not match" in artifact_warnings(manifest, "trial-1")[0]
    artifact.unlink()
    assert "is missing" in artifact_warnings(manifest, "trial-1")[0]


def test_retry_integrity_rejects_corrupt_or_mismatched_sources(tmp_path: Path) -> None:
    run, _ = _source(tmp_path)
    with pytest.raises(ValueError, match="unique"):
        load_retry_plan(run, ["trial-1", "trial-1"])
    with pytest.raises(ValueError, match="not listed"):
        load_retry_source(run, ["missing"])

    (run / "result.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        load_retry_source(run, ["trial-1"])
