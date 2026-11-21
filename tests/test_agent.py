import inspect
import random

import pytest

from coach import CoachState, get_advice
from coach import agent as agent_module
from coach.agent import feasible_range, observe, plan
from coach.guardrails import check_advice, numbers_are_grounded, validate_state
from coach.retriever import Document, Retriever


def state(guesses=(), difficulty="Normal", low=1, high=50, limit=8):
    return CoachState(difficulty, low, high, limit, tuple(guesses))


def test_feasible_range_uses_the_tightest_bounds():
    assert feasible_range(1, 50, [(25, "Too Low"), (40, "Too High"), (30, "Too Low")]) == (31, 39)


def test_opening_advice_suggests_the_midpoint():
    result = get_advice(state())
    assert result.situation == "opening"
    assert result.suggested_guess == 25
    assert "25" in result.advice
    assert "opening_moves#opening-guess" in result.sources


def test_narrow_advice_uses_the_updated_range():
    result = get_advice(state([(25, "Too Low")]))
    assert result.situation == "narrow"
    assert result.suggested_guess == 38
    assert "binary_search#midpoint-strategy" in result.sources


def test_wasted_guess_is_detected_and_explained():
    result = get_advice(state([(25, "Too Low"), (10, "Too Low")]))
    assert result.situation == "wasted_guess"
    assert "10" in result.advice and "ruled out" in result.advice


def test_repeated_guess_counts_as_wasted():
    assert observe(state([(25, "Too Low"), (25, "Too Low")]))["wasted_last_guess"] is True


def test_endgame_says_a_win_is_not_guaranteed():
    result = get_advice(state([(50, "Too Low"), (75, "Too High"), (60, "Too Low")], "Hard", 1, 100, 5))
    assert result.situation == "endgame"
    assert "cannot be guaranteed" in result.advice


def test_last_number_is_named_directly():
    result = get_advice(state([(10, "Too Low"), (15, "Too High"), (12, "Too Low"), (13, "Too Low")], "Easy", 1, 20, 6))
    assert result.situation == "last_number"
    assert result.suggested_guess == 14


def test_every_suggestion_is_inside_the_feasible_range():
    for secret in range(1, 51):
        guesses = []
        for _ in range(8):
            result = get_advice(state(guesses))
            lo, hi = feasible_range(1, 50, guesses)
            assert lo <= result.suggested_guess <= hi
            if result.suggested_guess == secret:
                break
            guesses.append((result.suggested_guess, "Too High" if result.suggested_guess > secret else "Too Low"))


def test_coach_is_never_given_the_secret():
    assert "secret" not in inspect.signature(get_advice).parameters
    assert "secret" not in CoachState.__dataclass_fields__


def test_contradictory_hints_give_a_safe_refusal():
    result = get_advice(state([(10, "Too Low"), (5, "Too High")]))
    assert result.situation == "contradiction"
    assert result.suggested_guess is None
    assert result.low_confidence


@pytest.mark.parametrize(
    "guesses",
    [
        [(999, "Too Low")],
        [(-3, "Too High")],
        [("abc", "Too Low")],
        [(10, "Maybe")],
        ["not a pair"],
        [(True, "Too Low")],
    ],
)
def test_malformed_history_is_rejected_without_raising(guesses):
    result = get_advice(state(guesses))
    assert result.situation == "invalid_input"
    assert result.suggested_guess is None
    assert result.confidence == 0.0


def test_invalid_settings_are_rejected():
    assert validate_state(50, 1, 8, []) != []
    assert validate_state(1, 50, 0, []) != []


def test_finished_game_gets_no_suggestion():
    result = get_advice(state([(25, "Win")]))
    assert result.situation == "finished"
    assert result.suggested_guess is None


def test_unknown_difficulty_still_works_without_a_history_note():
    result = get_advice(state(difficulty="Impossible"))
    assert result.suggested_guess == 25
    assert result.context is None


def test_history_note_matches_the_difficulty():
    assert "On Hard" in get_advice(state(difficulty="Hard", high=100, limit=5)).context


def test_bad_template_triggers_revision_and_low_confidence():
    broken = Retriever([
        Document("x#broken", "knowledge", "Opening guess", "opening first guess start midpoint binary search", advice="Start with {nonexistent}."),
    ])
    result = get_advice(state(), retriever=broken)
    assert result.revised is True
    assert result.sources == ["fallback"]
    assert "25" in result.advice
    assert result.low_confidence
    assert any(step["step"] == "revise" for step in result.trace)


def test_empty_knowledge_falls_back_safely():
    result = get_advice(state(), retriever=Retriever([]))
    assert result.revised is True
    assert result.suggested_guess == 25


def test_trace_lists_each_stage_in_order():
    steps = [s["step"] for s in get_advice(state([(25, "Too Low")])).trace]
    assert steps[:5] == ["validate", "observe", "plan", "retrieve", "compose"]
    assert steps[-1] == "confidence"


def test_plan_rules_pick_expected_situations():
    assert plan(observe(state()))[0] == "opening"
    assert plan(observe(state([(25, "Too Low")])))[0] == "narrow"


def test_check_advice_flags_each_failure():
    checks = check_advice("Guess 99 {oops}", suggested=99, lo=1, hi=50)
    assert checks["guess_in_range"] is False
    assert checks["no_unfilled_template"] is False
    assert check_advice("Pick one.", 5, 1, 10)["mentions_guess"] is False
    assert check_advice("word " * 60, 5, 1, 10)["within_word_limit"] is False


# Optional model rewrite, tested with stand-in clients so no network or key is needed


class _Reply:
    def __init__(self, text):
        self.content = [type("Block", (), {"text": text})()]


class _StubClient:
    def __init__(self, text=None, error=None):
        self._text, self._error = text, error
        self.messages = self

    def create(self, **kwargs):
        if self._error:
            raise self._error
        return _Reply(self._text)


def test_llm_rewrite_is_accepted_when_it_passes_the_checks():
    client = _StubClient("Try 25 first. It halves the range from 1 to 50.")
    result = get_advice(state(), llm_client=client)
    assert result.used_llm is True
    assert result.advice.startswith("Try 25")


def test_llm_rewrite_with_a_new_number_is_rejected():
    client = _StubClient("Try 25 first. The secret is probably 31.")
    result = get_advice(state(), llm_client=client)
    assert result.used_llm is False
    assert "Start with 25" in result.advice


def test_llm_rewrite_without_the_suggested_guess_is_rejected():
    result = get_advice(state(), llm_client=_StubClient("Pick the middle number."))
    assert result.used_llm is False


def test_llm_failure_keeps_the_template_advice():
    result = get_advice(state(), llm_client=_StubClient(error=RuntimeError("down")))
    assert result.used_llm is False
    assert result.suggested_guess == 25


def test_numbers_are_grounded():
    assert numbers_are_grounded("Try 25 of 50", "Start with 25 from 1 to 50")
    assert not numbers_are_grounded("Try 26", "Start with 25")
