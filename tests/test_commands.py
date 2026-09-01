from pathlib import Path

from vllm_optimizer.benchmarks.guidellm import build_plan as build_guidellm_plan
from vllm_optimizer.benchmarks.vllm import build_plan as build_vllm_plan
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig


def _config() -> VTuneConfig:
    return VTuneConfig(1, ExperimentConfig("commands"), {"model": "/models/demo"})


def test_guidellm_command_renders_nested_options(tmp_path: Path) -> None:
    run = {
        "name": "throughput",
        "profile": {"kind": "throughput", "max_concurrency": 4},
        "constraints": [{"kind": "max_requests", "count": 2}],
        "data": [{"kind": "synthetic_text", "prompt_tokens": 4}],
    }

    plan = build_guidellm_plan(_config(), run, "http://127.0.0.1:8000", tmp_path)

    assert plan.argv[0:3] == ("guidellm", "run", "--backend")
    assert "kind=throughput,max_concurrency=4" in plan.argv
    assert "kind=max_requests,count=2" in plan.argv
    assert plan.json_path == tmp_path / "throughput" / "results.json"


def test_vllm_command_normalizes_flags_and_supplies_endpoint(tmp_path: Path) -> None:
    run = {"name": "random", "args": {
        "dataset_name": "random", "num_prompts": 2,
        "max_concurrency": 4, "ignore_eos": True,
    }}

    plan = build_vllm_plan(_config(), run, "http://localhost:8123", tmp_path)

    assert "--host" in plan.argv and plan.argv[plan.argv.index("--host") + 1] == "localhost"
    assert "--port" in plan.argv and plan.argv[plan.argv.index("--port") + 1] == "8123"
    assert ("--dataset-name", "random") == tuple(plan.argv[plan.argv.index("--dataset-name"):plan.argv.index("--dataset-name") + 2])
    assert "--ignore-eos" in plan.argv
