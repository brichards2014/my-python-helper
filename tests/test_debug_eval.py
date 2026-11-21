import eval_debug


def test_every_evaluation_check_passes():
    result = eval_debug.run_all()
    failed = [c.name for c in result["checks"] if not c.passed]
    assert failed == []


def test_report_has_a_result_line_and_a_baseline_table():
    report = eval_debug.format_report(eval_debug.run_all())
    assert "RESULT:" in report and "Plain test report" in report


def test_main_returns_zero(capsys):
    assert eval_debug.main(["--no-write"]) == 0
