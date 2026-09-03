import importlib.util
import json
from pathlib import Path


def _coverage_gate():
    path = Path(__file__).parents[1] / "scripts" / "check_coverage.py"
    spec = importlib.util.spec_from_file_location("coverage_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coverage_gate_normalizes_source_and_installed_paths(tmp_path: Path, monkeypatch) -> None:
    coverage_gate = _coverage_gate()
    assert coverage_gate.coverage_name("src\\vllm_optimizer\\measurement.py") == ("src/vllm_optimizer/measurement.py")
    installed = "C:/venv/Lib/site-packages/vllm_optimizer/measurement.py"
    assert coverage_gate.coverage_name(installed) == "src/vllm_optimizer/measurement.py"

    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"files": {installed: {"summary": {"percent_covered": 90}}}}), encoding="utf-8")
    monkeypatch.setattr(coverage_gate, "REPORT", report)
    monkeypatch.setattr(coverage_gate, "REQUIRED", {"src/vllm_optimizer/measurement.py": 85})
    coverage_gate.main()
