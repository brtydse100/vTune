import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vllm_optimizer.benchmarks.guidellm import parse_result as parse_guidellm_result
from vllm_optimizer.benchmarks.vllm import parse_result as parse_vllm_result
from vllm_optimizer.managers.scoring import ScoringManager, TrialScore
from vllm_optimizer.measurement import drifted, summarize
from vllm_optimizer.workers.benchmark import _request_count_failure
from vllm_optimizer.workers.completion import reported_request_total


def test_guidellm_result_is_normalized_without_fabricating_percentiles(tmp_path: Path) -> None:
    path = tmp_path / "guidellm.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"guidellm_version": "0.7.3"},
                "benchmarks": [
                    {
                        "config": {"kind": "sync"},
                        "metrics": {
                            "requests_per_second": {"average": 4.0},
                            "request_totals": {"successful": 2, "errored": 0, "incomplete": 0, "total": 2},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = parse_guidellm_result(path, "requests")

    assert result.workloads[0].metrics["requests_per_second"] == {"average": 4.0}
    assert result.workloads[0].metrics["request_total"] == 2
    assert "p99" not in result.workloads[0].metrics["requests_per_second"]


def test_vllm_result_and_scoring_use_canonical_request_metrics(tmp_path: Path) -> None:
    path = tmp_path / "vllm.json"
    path.write_text(
        json.dumps(
            {"backend": "vllm", "model_id": "demo", "num_prompts": 2, "completed": 2, "request_throughput": 5.0}
        ),
        encoding="utf-8",
    )

    result = parse_vllm_result(path, "requests")
    score = ScoringManager("requests_per_second").score((result,))
    quality = ScoringManager("requests_per_second").quality((result,))

    assert score == 5.0
    assert (quality.successful, quality.errored, quality.incomplete) == (2, 0, 0)


def test_ranking_prefers_metric_before_eligible_request_quality() -> None:
    manager = ScoringManager("requests_per_second")
    ranking = manager.rank([_score("failed", 100.0, 9, 1), _score("complete", 10.0, 10, 0)])

    assert tuple(item.trial_id for item in ranking) == ("failed", "complete")


def _score(trial_id: str, value: float, successful: int, errored: int) -> TrialScore:
    return TrialScore(trial_id, value, {}, {}, successful, errored, 0)


def test_measurement_summary_reports_variance_and_confidence() -> None:
    summary = summarize([10, 12, 11], minimum_repeats=2)

    assert summary.minimum_repeats_met
    assert summary.variance == 1
    assert summary.confidence_low < summary.mean < summary.confidence_high
    assert drifted(100, 106)


def test_small_sample_confidence_uses_students_t() -> None:
    one = summarize([10], minimum_repeats=1)
    two = summarize([10, 12], minimum_repeats=2)
    three = summarize([10, 11, 12], minimum_repeats=3)

    assert one.confidence_low is None
    assert two.confidence_low == pytest.approx(-1.706, abs=0.001)
    assert two.confidence_high == pytest.approx(23.706, abs=0.001)
    assert three.confidence_low == pytest.approx(8.516, abs=0.001)
    assert three.confidence_high == pytest.approx(13.484, abs=0.001)
    many = summarize(range(32), minimum_repeats=3)
    normal_margin = 1.96 * (many.variance / many.count) ** 0.5
    assert many.confidence_high - many.mean > normal_margin


def test_empty_request_count_result_is_rejected() -> None:
    failure = _request_count_failure(SimpleNamespace(workloads=()), 2)

    assert failure is not None
    assert failure.code == "benchmark_request_total_missing"


def test_boolean_request_total_is_rejected() -> None:
    result = SimpleNamespace(
        workloads=(
            SimpleNamespace(
                metrics={"request_total": True, "request_totals": {"successful": 1, "errored": 0, "incomplete": 0}}
            ),
        )
    )

    failure = _request_count_failure(result, 1)

    assert failure is not None
    assert failure.code == "benchmark_request_total_missing"


def test_vllm_incomplete_requests_are_rejected() -> None:
    result = SimpleNamespace(
        workloads=(
            SimpleNamespace(
                metrics={"request_total": 2, "request_totals": {"successful": 1, "errored": 0, "incomplete": 1}}
            ),
        )
    )

    failure = _request_count_failure(result, reported_request_total(result), "vLLM")

    assert failure is not None
    assert failure.code == "benchmark_requests_incomplete"


def test_scoring_requires_clean_totals_and_minimum_repeats(tmp_path: Path) -> None:
    complete = _benchmark_result(tmp_path, "requests", 5.0, 2, 0)
    failed = _benchmark_result(tmp_path, "requests", 50.0, 1, 1)
    manager = ScoringManager("requests_per_second", 2, ("requests",))

    assert manager.score((complete, failed)) is None
    assert manager.score((complete, complete)) == 5.0


def test_scoring_requires_every_configured_benchmark(tmp_path: Path) -> None:
    result = _benchmark_result(tmp_path, "requests", 5.0, 2, 0)
    manager = ScoringManager("requests_per_second", 1, ("requests", "latency"))

    assert manager.score((result,)) is None


def test_scoring_rejects_missing_request_totals() -> None:
    result = SimpleNamespace(
        run_name="requests", workloads=(SimpleNamespace(metrics={"requests_per_second": {"average": 5.0}}),)
    )

    assert ScoringManager("requests_per_second").score((result,)) is None


def test_scoring_rejects_invalid_minimum_repeats() -> None:
    with pytest.raises(ValueError, match="minimum repeats"):
        ScoringManager("requests_per_second", True)


def _benchmark_result(tmp_path: Path, name: str, score: float, successful: int, errored: int):
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "backend": "vllm",
                "model_id": "demo",
                "num_prompts": successful + errored,
                "completed": successful,
                "failed": errored,
                "request_throughput": score,
            }
        ),
        encoding="utf-8",
    )
    return parse_vllm_result(path, name)


def test_metric_is_primary_ranking_objective() -> None:
    manager = ScoringManager("requests_per_second")
    slower_clean = _score("clean", 10.0, 100, 0)
    faster_eligible = _score("fast", 12.0, 99, 1)

    assert manager.rank([slower_clean, faster_eligible])[0].trial_id == "fast"


def test_equal_metric_uses_quality_then_id_tie_breakers() -> None:
    manager = ScoringManager("requests_per_second")
    scores = [_score("b", 10.0, 99, 1), _score("a", 10.0, 100, 0)]

    assert [item.trial_id for item in manager.rank(scores)] == ["a", "b"]
