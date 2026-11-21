import pytest

from debug_coach.diagnose import _opposite, diagnose
from debug_coach.exercises import load_exercise
from debug_coach.sandbox import run_submission


def tag_for(exercise_id, source):
    exercise = load_exercise(exercise_id)
    return diagnose(source, run_submission(source, exercise.cases))


@pytest.mark.parametrize(
    "exercise_id,tag",
    [
        ("easy_1_count_vowels", "case_sensitivity"),
        ("easy_2_sum_first_n", "off_by_one"),
        ("medium_1_add_item", "mutable_default"),
        ("medium_2_remove_negatives", "modify_while_iterating"),
        ("hard_1_make_multipliers", "late_binding"),
        ("hard_2_game_logic", "inverted_condition"),
    ],
)
def test_each_starter_gets_its_intended_diagnosis(exercise_id, tag):
    exercise = load_exercise(exercise_id)
    assert tag_for(exercise_id, exercise.starter).tag == tag


def test_diagnosis_reports_the_line_of_the_pattern():
    exercise = load_exercise("medium_1_add_item")
    assert tag_for(exercise.id, exercise.starter).line == 1
    exercise = load_exercise("easy_2_sum_first_n")
    assert tag_for(exercise.id, exercise.starter).line == 4


def test_list_call_as_default_is_still_a_mutable_default():
    exercise = load_exercise("medium_1_add_item")
    assert tag_for(exercise.id, exercise.starter.replace("items=[]", "items=list()")).tag == "mutable_default"


def test_copying_the_list_before_looping_is_not_flagged():
    exercise = load_exercise("medium_2_remove_negatives")
    assert tag_for(exercise.id, exercise.solution).tag == "solved"


def test_default_parameter_and_helper_function_both_fix_late_binding():
    exercise = load_exercise("hard_1_make_multipliers")
    helper = "def make_multipliers(n):\n    def make(i):\n        return lambda x: x * i\n    return [make(i) for i in range(n)]\n"
    assert tag_for(exercise.id, exercise.solution).tag == "solved"
    assert tag_for(exercise.id, helper).tag == "solved"


def test_late_binding_in_a_list_comprehension_is_found():
    exercise = load_exercise("hard_1_make_multipliers")
    source = "def make_multipliers(n):\n    return [lambda x: x * i for i in range(n)]\n"
    assert tag_for(exercise.id, source).tag == "late_binding"


def test_letter_case_is_not_blamed_when_passing_tests_also_have_capitals():
    exercise = load_exercise("hard_2_game_logic")
    diagnosis = tag_for(exercise.id, exercise.starter.replace('"Go HIGHER!"\n    return "Too Low", "Go LOWER!"', '"Go LOWER!"\n    return "Too Low", "Go HIGHER!"'))
    assert diagnosis.tag == "wrong_value"
    assert diagnosis.function == "get_range_for_difficulty"


def test_all_failing_tests_raising_errors_is_a_runtime_error():
    exercise = load_exercise("medium_1_add_item")
    diagnosis = tag_for(exercise.id, exercise.starter.replace("items=[]", "items=None"))
    assert diagnosis.tag == "runtime_error"
    assert "AttributeError" in diagnosis.evidence


def test_status_based_diagnoses():
    exercise = load_exercise("easy_1_count_vowels")
    assert tag_for(exercise.id, "def f(:\n").tag == "syntax_error"
    assert tag_for(exercise.id, "import os\n").tag == "blocked_code"
    assert tag_for(exercise.id, "raise ValueError('x')\n").tag == "load_error"


@pytest.mark.parametrize(
    "expected,actual,result",
    [
        (True, False, True),
        (True, True, False),
        ("Go LOWER!", "Go HIGHER!", True),
        ("Too High", "Too Low", True),
        (["Too High", "Go LOWER!"], ["Too High", "Go HIGHER!"], True),
        ([1, 50], [1, 100], False),
        (5, 4, False),
        ("abc", "abd", False),
    ],
)
def test_opposite_detection(expected, actual, result):
    assert _opposite(expected, actual) is result
