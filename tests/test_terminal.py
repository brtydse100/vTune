from vllm_optimizer.terminal import TerminalLogger


def test_terminal_reports_all_non_tty_progress(capsys) -> None:
    terminal = TerminalLogger("DEBUG")
    terminal.debug("debug")
    terminal.info("info")
    terminal.warning("warning")
    terminal.experiment({"Experiment": "synthetic", "Trials": 2})
    terminal.baseline()
    terminal.trial(1, 2, "trial-1", {"max-num-seqs": 1}, "worker")
    terminal.stage("starting", "configuration_builder", "trial-1")
    terminal.benchmark_progress("configuration_builder", 1, 1, 2, "trial-1")
    terminal.stage("completed", "configuration_builder", "trial-1")
    terminal.benchmark_score("requests", 1, None, 1)
    terminal.benchmark_score("requests", 2, None, 0)
    terminal.benchmark_score("requests", 3, 4.5, 1)
    terminal.benchmark_aggregate("requests", 4.0)
    elapsed = terminal.close()
    terminal.session_complete(elapsed)

    output = capsys.readouterr().out
    for expected in (
        "debug",
        "info",
        "warning",
        "synthetic",
        "Baseline",
        "trial-1",
        "Building configuration",
        "waiting for the required",
        "no eligible score",
        "score=4.5000",
        "repeated score=4.0000",
        "Session duration",
    ):
        assert expected in output


def test_terminal_ignores_progress_for_unknown_stage(capsys) -> None:
    terminal = TerminalLogger("WARNING")
    terminal.benchmark_progress("missing", None, 1, 2)
    terminal.info("hidden")
    terminal.warning("visible")
    terminal.close()
    output = capsys.readouterr().out
    assert "hidden" not in output and "visible" in output
