from pathlib import Path

from vtune.benchmarks.configuration import (
    configured_min_repeats, configured_runs, configured_warmup_repeats,
)
from vtune.benchmarks.timing import timeout_for_run
from vtune.config.loader import load_config


def _config_text(timeout: str | None = "20m") -> str:
    timeout_section = f"timeouts:\n  benchmark: {timeout}\n" if timeout else ""
    return f"""experiment:
  name: public-test
server:
  model: model
benchmark:
  runs:
    - name: requests
      profile: {{kind: synchronous}}
      constraints: [{{kind: max_requests, count: 2}}]
      data: [{{kind: synthetic_text, prompt_tokens: 4, output_tokens: 2}}]
optimization:
  maximize: output_tokens_per_second
{timeout_section}"""


def test_load_config_resolves_model_path_and_run(tmp_path: Path) -> None:
    (tmp_path / "model").mkdir()
    source = tmp_path / "experiment.yaml"
    source.write_text(_config_text(), encoding="utf-8")

    config = load_config(source)

    assert config.server["model"] == str((tmp_path / "model").resolve())
    assert configured_runs(config)[0]["name"] == "requests"


def test_request_count_run_uses_conservative_timeout_cap(tmp_path: Path) -> None:
    (tmp_path / "model").mkdir()
    source = tmp_path / "experiment.yaml"
    source.write_text(_config_text(None), encoding="utf-8")

    config = load_config(source)

    assert timeout_for_run(config.benchmark["runs"][0]) == 3600.0


def test_measurement_policy_accepts_warmups_and_minimum_repeats(tmp_path: Path) -> None:
    (tmp_path / "model").mkdir()
    source = tmp_path / "experiment.yaml"
    source.write_text(_config_text().replace(
        "benchmark:\n", "benchmark:\n  repeats: 3\n  min_repeats: 2\n  warmup_repeats: 1\n", 1,
    ), encoding="utf-8")

    config = load_config(source)

    assert configured_min_repeats(config) == 2
    assert configured_warmup_repeats(config) == 1
