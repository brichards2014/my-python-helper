import pytest

from coach.retriever import Document, Retriever
from debug_coach import guardrails
from debug_coach.agent import Attempt, coach_submission, reveal_solution
from debug_coach.exercises import list_exercises, load_exercise

EXERCISES = list_exercises()


def run_n(exercise, source, times):
    history, results = [], []
    for _ in range(times):
        g = coach_submission(exercise, source, history)
        history.append(g.attempt)
        results.append(g)
    return results


def test_hints_escalate_to_level_three_and_stay_there():
    e = load_exercise("medium_1_add_item")
    results = run_n(e, e.starter, 4)
    assert [g.level for g in results] == [1, 2, 3, 3]
    assert len({g.hint for g in results[:3]}) == 3


def test_a_new_kind_of_failure_restarts_at_level_one():
    e = load_exercise("easy_1_count_vowels")
    first, second = run_n(e, e.starter, 2)
    changed = coach_submission(e, e.solution.replace('"aeiou"', '"aeio"'), [first.attempt, second.attempt])
    assert changed.tag == "wrong_value" and changed.level == 1


def test_a_new_function_with_the_same_tag_restarts_at_level_one():
    e = load_exercise("hard_2_game_logic")
    fix_check = e.starter.replace('"Go HIGHER!"\n    return "Too Low", "Go LOWER!"', '"Go LOWER!"\n    return "Too Low", "Go HIGHER!"')
    fix_ranges = fix_check.replace("return 1, 100\n    if difficulty == \"Hard\":\n        return 1, 50", "return 1, 50\n    if difficulty == \"Hard\":\n        return 1, 100")
    a = coach_submission(e, fix_check, [])
    b = coach_submission(e, fix_ranges, [a.attempt])
    assert (a.diagnosis.function, b.diagnosis.function) == ("get_range_for_difficulty", "update_score")
    assert b.level == 1


def test_solved_message_includes_the_lesson_and_full_confidence():
    e = load_exercise("medium_1_add_item")
    g = coach_submission(e, e.solution, [])
    assert g.solved and g.confidence == 1.0
    assert "None as the default" in g.hint


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_no_hint_contains_a_line_of_the_solution(exercise):
    for g in run_n(exercise, exercise.starter, 3):
        text = g.hint + " ".join(r["title"] for r in g.references)
        assert guardrails.leaked_lines(text, exercise.solution, exercise.starter) == []
        assert g.checks["no_solution_leak"]


def test_the_leak_check_can_fail():
    e = load_exercise("medium_1_add_item")
    assert guardrails.leaked_lines("Try: if items is None:", e.solution, e.starter)
    assert guardrails.leaked_lines("  items.append(item)  ", e.solution, e.starter) == []  # already in the starter


def test_references_appear_from_level_two():
    e = load_exercise("medium_1_add_item")
    first, second, _third = run_n(e, e.starter, 3)
    assert first.references == []
    urls = {r["url"] for r in second.references}
    assert "https://docs.python.org/3/tutorial/controlflow.html" in urls


def test_exercises_without_a_public_reference_show_none():
    e = load_exercise("easy_1_count_vowels")
    assert run_n(e, e.starter, 3)[-1].references == []


def test_bad_hint_template_falls_back_to_a_safe_hint():
    e = load_exercise("easy_1_count_vowels")
    broken = Retriever([Document("x#b", "knowledge", "Letter case", "case sensitivity uppercase lowercase letters compare",
                                 fields={"pattern": "case_sensitivity", "hint1": "See {nope}.", "hint2": "", "hint3": ""})])
    g = coach_submission(e, e.starter, [], retriever=broken)
    assert g.revised and "expected 5" in g.hint and g.confidence < 0.7
    assert any(step["step"] == "revise" for step in g.trace)


def test_note_that_does_not_match_the_diagnosis_is_not_used():
    e = load_exercise("easy_1_count_vowels")
    other = Retriever([Document("x#o", "knowledge", "Off by one", "uppercase lowercase letters compare case",
                                fields={"pattern": "off_by_one", "hint1": "Count loop passes.", "hint2": "a", "hint3": "b"})])
    g = coach_submission(e, e.starter, [], retriever=other)
    assert g.revised and "loop passes" not in g.hint


def test_empty_knowledge_base_still_gives_a_hint():
    e = load_exercise("easy_1_count_vowels")
    g = coach_submission(e, e.starter, [], retriever=Retriever([]))
    assert g.revised and g.hint


@pytest.mark.parametrize("source", ["", "   \n", None, 42])
def test_empty_or_non_text_submission_is_refused(source):
    g = coach_submission(load_exercise("easy_1_count_vowels"), source, [])
    assert g.tag == "invalid_input" and g.confidence == 0.0


def test_oversized_submission_is_refused():
    g = coach_submission(load_exercise("easy_1_count_vowels"), "x = 1\n" * 10_000, [])
    assert g.tag == "invalid_input"


def test_progress_and_regression_are_reported():
    e = load_exercise("easy_1_count_vowels")
    assert coach_submission(e, e.solution, [Attempt(3, 6, "case_sensitivity", "count_vowels")]).progress.startswith("Progress")
    assert coach_submission(e, e.starter, [Attempt(5, 6, "wrong_value", "count_vowels")]).progress.startswith("Regression")
    assert coach_submission(e, e.starter, []).progress == ""


def test_reveal_needs_three_real_failed_attempts():
    e = load_exercise("easy_1_count_vowels")
    failed = Attempt(3, 6, "case_sensitivity", "count_vowels")
    assert not reveal_solution(e, [failed, failed])[0]
    ok, text = reveal_solution(e, [failed] * 3)
    assert ok and text == e.solution
    assert not reveal_solution(e, [Attempt(0, 6, "invalid_input")] * 5)[0]


def test_trace_lists_each_stage_in_order():
    e = load_exercise("easy_1_count_vowels")
    steps = [s["step"] for s in coach_submission(e, e.starter, []).trace]
    assert steps == ["validate", "run", "diagnose", "plan", "retrieve", "compose", "check", "confidence"]


def test_hidden_test_failures_do_not_leak_their_input():
    e = load_exercise("easy_1_count_vowels")
    source = e.starter.replace('if ch in "aeiou"', 'if ch in "aeiouAEIOU" and ch != "Y"')
    g = coach_submission(e, source, [])
    assert "PYTHON IS FUN" not in g.hint
