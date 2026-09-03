from pathlib import Path

from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.measurement import _metric as measurement_metric
from vllm_optimizer.reporting.reporter import Reporter


def test_reporter_writes_csv_and_html_for_a_completed_trial(tmp_path: Path) -> None:
    report = TrialReport(
        1,
        "trial-1",
        WorkerStatus.COMPLETED,
        (
            {
                "name": "throughput",
                "backend": "guidellm",
                "backend_version": "0.7.3",
                "raw_artifact": "results.json",
                "workloads": (
                    {
                        "index": 0,
                        "configuration": {},
                        "metrics": {
                            "output_tokens_per_second": {"average": 12.5},
                            "time_to_first_token_ms": {"average": 4.0},
                            "request_totals": {"successful": 2, "errored": 0, "incomplete": 0},
                        },
                    },
                ),
            },
        ),
        {},
        execution={"mode": "sequential"},
    )
    score = TrialScore("trial-1", 12.5, {"max-num-seqs": 8}, {})

    csv_path, html_path = Reporter(tmp_path).write("output_tokens_per_second", (report,), (score,), None)

    assert csv_path.read_text(encoding="utf-8").splitlines()[1].startswith("1,trial-1,12.5")
    html = html_path.read_text(encoding="utf-8")
    assert "vLLM Optimizer decision report" in html
    assert "trial-1" in html
    assert "0% of all requests" in html


def test_measurement_metric_accepts_direct_numeric_values() -> None:
    assert measurement_metric({"score": 2}, "score") == 2.0
