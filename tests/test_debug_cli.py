import pytest

import debug_cli
from debug_coach.exercises import load_exercise


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(debug_cli, "WORKSPACE", tmp_path)
    return tmp_path


def test_list_shows_all_exercises(capsys):
    assert debug_cli.main(["list"]) == 0
    levels = [line.split()[1] for line in capsys.readouterr().out.strip().splitlines()]
    assert sorted(levels) == ["easy", "easy", "hard", "hard", "medium", "medium"]


def test_start_creates_the_starter_file_without_overwriting_edits(workspace, capsys):
    debug_cli.main(["start", "easy_1_count_vowels"])
    path = workspace / "easy_1_count_vowels.py"
    assert path.read_text() == load_exercise("easy_1_count_vowels").starter
    path.write_text("# my edit\n")
    debug_cli.main(["start", "easy_1_count_vowels"])
    assert path.read_text() == "# my edit\n"


def test_check_gives_hints_remembers_attempts_and_ends_solved(workspace, capsys):
    debug_cli.main(["start", "medium_1_add_item"])
    assert debug_cli.main(["check", "medium_1_add_item"]) == 2
    assert "hint level 1 of 3" in capsys.readouterr().out
    assert debug_cli.main(["check", "medium_1_add_item"]) == 2
    assert "hint level 2 of 3" in capsys.readouterr().out
    (workspace / "medium_1_add_item.py").write_text(load_exercise("medium_1_add_item").solution)
    assert debug_cli.main(["check", "medium_1_add_item"]) == 0
    assert "Solved" in capsys.readouterr().out


def test_reveal_is_refused_until_three_failed_attempts(workspace, capsys):
    debug_cli.main(["start", "easy_2_sum_first_n"])
    for _ in range(2):
        debug_cli.main(["check", "easy_2_sum_first_n"])
    capsys.readouterr()
    assert debug_cli.main(["reveal", "easy_2_sum_first_n"]) == 1
    debug_cli.main(["check", "easy_2_sum_first_n"])
    capsys.readouterr()
    assert debug_cli.main(["reveal", "easy_2_sum_first_n"]) == 0
    assert "range(n)" in capsys.readouterr().out


def test_check_without_a_file_explains_what_to_do(workspace, capsys):
    assert debug_cli.main(["check", "easy_1_count_vowels"]) == 1
    assert "start" in capsys.readouterr().out


def test_unknown_exercise_is_reported(capsys):
    assert debug_cli.main(["start", "nope"]) == 1
    assert "Unknown exercise" in capsys.readouterr().out


def test_a_damaged_attempts_file_does_not_stop_the_coach(workspace, capsys):
    debug_cli.main(["start", "easy_1_count_vowels"])
    (workspace / "easy_1_count_vowels.attempts.json").write_text("not json")
    assert debug_cli.main(["check", "easy_1_count_vowels"]) == 2


def test_demo_runs_every_scenario(capsys):
    assert debug_cli.main(["demo"]) == 0
    out = capsys.readouterr().out
    for phrase in ["hint level 3 of 3", "Read more:", "Progress:", "Solved:",
                   "syntax_error", "blocked", "Try 2 more time(s)", "if items is None:"]:
        assert phrase in out
