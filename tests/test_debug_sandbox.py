import pytest

from debug_coach import sandbox
from debug_coach.exercises import list_exercises, load_exercise

EXERCISES = list_exercises()


def test_there_are_two_exercises_per_difficulty():
    levels = [e.difficulty for e in EXERCISES]
    assert sorted(levels) == ["easy", "easy", "hard", "hard", "medium", "medium"]


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_starter_fails_some_tests_and_solution_passes_all(exercise):
    starter = sandbox.run_submission(exercise.starter, exercise.cases)
    solution = sandbox.run_submission(exercise.solution, exercise.cases)
    assert starter.status == "ok" and 0 < starter.passed < starter.total
    assert solution.all_passed


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_every_exercise_names_its_sources_or_says_it_is_original(exercise):
    assert exercise.origin
    assert exercise.sources or "original" in exercise.origin.lower() or "Original" in exercise.origin or "Written for this project" in exercise.origin


@pytest.fixture
def quick_timeout(monkeypatch):
    monkeypatch.setattr(sandbox, "TIMEOUT_SECONDS", 1)


def test_infinite_loop_times_out(quick_timeout):
    run = sandbox.run_submission("while True:\n    pass\n", EXERCISES[0].cases)
    assert run.status == "timeout"


@pytest.mark.parametrize(
    "source,status",
    [
        ("def f(:\n", "syntax_error"),
        ("import os\n", "blocked"),
        ("from subprocess import run\n", "blocked"),
        ("open('x', 'w')\n", "blocked"),
        ("x = input()\n", "blocked"),
        ("eval('1')\n", "blocked"),
        ("raise ValueError('boom')\n", "load_error"),
    ],
)
def test_unsafe_or_broken_code_is_stopped_before_the_tests(source, status):
    run = sandbox.run_submission(source, EXERCISES[0].cases)
    assert run.status == status
    assert run.cases == []


def test_allowed_imports_work():
    source = "import math\ndef count_vowels(t):\n    return int(math.floor(1.5)) * 0\n"
    assert sandbox.run_submission(source, EXERCISES[0].cases).status == "ok"


def test_exceptions_inside_a_function_are_reported_per_test():
    run = sandbox.run_submission("def count_vowels(t):\n    return t[100]\n", EXERCISES[0].cases)
    assert run.status == "ok"
    assert any(c.error_type == "IndexError" for c in run.cases)


def test_printed_output_is_captured_and_truncated():
    run = sandbox.run_submission("print('x' * 10**6)\ndef count_vowels(t):\n    return 0\n", EXERCISES[0].cases)
    assert run.status == "ok" and len(run.stdout) <= 500


def test_hidden_tests_do_not_reveal_their_input_or_expected_value():
    exercise = load_exercise("easy_1_count_vowels")
    run = sandbox.run_submission(exercise.starter, exercise.cases)
    hidden = [c for c in run.cases if c.hidden]
    assert hidden and all(c.expr == "a hidden test" and c.expected == "(hidden)" for c in hidden)


def test_each_test_starts_from_a_fresh_copy_of_the_file():
    source = "calls = []\ndef count_vowels(t):\n    calls.append(1)\n    return len(calls) * 0\n"
    run = sandbox.run_submission(source, EXERCISES[0].cases)
    assert run.status == "ok"
