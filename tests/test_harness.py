import eval_harness


def test_non_simulation_checks_all_pass():
    checks = (
        eval_harness.scenario_checks()
        + eval_harness.retrieval_checks()
        + eval_harness.guardrail_checks()
        + eval_harness.invariant_checks()
    )
    failed = [c.name for c in checks if not c.passed]
    assert failed == []


def test_report_lists_every_check_and_a_result_line():
    result = eval_harness.run_all(games=20)
    report = eval_harness.format_report(result)
    assert "RESULT:" in report
    assert report.count("PASS") + report.count("FAIL") >= len(result["checks"])


def test_main_returns_zero_when_checks_pass(tmp_path, capsys):
    assert eval_harness.main(["--games", "50", "--no-write"]) == 0
    assert "checks passed" in capsys.readouterr().out
