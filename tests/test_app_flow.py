"""Runs app.py against a small stand-in for Streamlit, so the app wiring is tested without a browser."""
import runpy
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class _Session(dict):
    __getattr__ = dict.__getitem__

    def __setattr__(self, key, value):
        self[key] = value


class _Stop(Exception):
    pass


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _Slot:
    def __init__(self, log):
        self._log = log

    def info(self, message):
        self._log.append(("attempts_box", message))


class FakeApp:
    """Each run() is one Streamlit rerun with the given widget values."""

    def __init__(self, monkeypatch):
        self.session = _Session()
        self.log = []
        self.monkeypatch = monkeypatch
        monkeypatch.setattr("coach.log.append_trace", lambda *a, **k: None)

    def messages(self, kind):
        return [m for k, m in self.log if k == kind]

    def run(self, difficulty="Normal", guess="", submit=False, new=False):
        self.log = []
        log = self.log
        st = types.ModuleType("streamlit")
        st.session_state = self.session
        st.set_page_config = lambda **k: None
        for name in ("title", "caption", "subheader", "write", "json", "divider", "balloons"):
            setattr(st, name, lambda *a, **k: None)
        for name in ("info", "warning", "success", "error"):
            setattr(st, name, (lambda n: lambda m, *a, **k: log.append((n, m)))(name))
        st.sidebar = _Ctx()
        st.sidebar.selectbox = lambda *a, **k: difficulty
        st.empty = lambda: _Slot(log)
        st.expander = lambda *a, **k: _Ctx()
        st.text_input = lambda *a, **k: guess
        st.columns = lambda n: [_Ctx() for _ in range(n)]
        st.form = lambda *a, **k: _Ctx()
        st.form_submit_button = lambda label, **k: submit
        st.button = lambda label, **k: new

        def _stop():
            raise _Stop()

        st.checkbox = lambda *a, **k: True
        st.stop = _stop
        st.rerun = lambda: None
        self.monkeypatch.setitem(sys.modules, "streamlit", st)
        self.monkeypatch.syspath_prepend(str(ROOT))
        try:
            runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
        except _Stop:
            pass
        return self


@pytest.fixture
def app(monkeypatch):
    return FakeApp(monkeypatch)


def test_first_load_shows_opening_advice(app):
    app.run()
    assert app.session["attempts"] == 0
    assert any("Start with 25" in m for m in app.messages("info"))


@pytest.mark.parametrize("guess,error", [("500", "Enter a number from 1 to 50."), ("abc", "That is not a number."), ("", "Enter a guess.")])
def test_bad_input_is_rejected_and_costs_no_attempt(app, guess, error):
    app.run()
    app.run(guess=guess, submit=True)
    assert error in app.messages("error")
    assert app.session["attempts"] == 0
    assert app.session["guesses"] == []


def test_valid_guess_updates_attempts_box_and_coach(app):
    app.run()
    secret = app.session["secret"]
    guess = 25 if secret != 25 else 26
    app.run(guess=str(guess), submit=True)
    assert app.session["attempts"] == 1
    assert "Attempts left: 7" in app.messages("attempts_box")[-1]
    assert any("Guess" in m for m in app.messages("info"))


def test_win_then_new_game_resets_state(app):
    app.run()
    app.run(guess=str(app.session["secret"]), submit=True)
    assert app.session["status"] == "won"
    app.run()
    assert any("already won" in m for m in app.messages("success"))
    app.run(new=True)
    assert app.session["status"] == "playing"
    assert app.session["guesses"] == []


def test_changing_difficulty_starts_a_new_game_with_the_right_range(app):
    app.run()
    app.run(difficulty="Hard")
    assert app.session["difficulty"] == "Hard"
    assert 1 <= app.session["secret"] <= 100
    assert "Attempts left: 5" in app.messages("attempts_box")[-1]


def test_running_out_of_attempts_ends_the_game(app):
    app.run(difficulty="Hard")
    secret = app.session["secret"]
    wrong = [n for n in range(1, 101) if n != secret][:5]
    for n in wrong:
        app.run(difficulty="Hard", guess=str(n), submit=True)
    assert app.session["status"] == "lost"
    assert any("Out of attempts" in m for m in app.messages("error"))
