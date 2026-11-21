import demo


def test_scripted_demo_runs_and_shows_each_behavior(capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "You won in 6 attempts." in out          # coach-guided win
    assert "already ruled out" in out               # wasted guess detected
    assert "Rejected: Enter a number from 1 to 20." in out  # range guardrail
    assert "The hints contradict each other" in out  # corrupted history refused


def test_rejected_input_does_not_use_an_attempt(capsys):
    demo.play("t", "Easy", 7, ["", "abc", "500", "7"], demo.argparse.Namespace(trace=False, save_traces=False))
    out = capsys.readouterr().out
    assert "Attempt 1/6: Win" in out
