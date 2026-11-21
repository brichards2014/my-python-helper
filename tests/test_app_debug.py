"""Runs app_debug.py against a small stand-in for Streamlit, so the page wiring is tested without a browser."""
import runpy
import sys
import types
from pathlib import Path

import pytest

from debug_coach.exercises import load_exercise

ROOT = Path(__file__).resolve().parent.parent


class _Session(dict):
    __getattr__ = dict.__getitem__

    def __setattr__(self, key, value):
        self[key] = value


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        return lambda *a, **k: None


class FakePage:
    def __init__(self, monkeypatch):
        self.session = _Session()
        self.monkeypatch = monkeypatch
        self.log = []
        monkeypatch.setattr("coach.log.append_trace", lambda *a, **k: None)

    def messages(self, kind):
        return [m for k, m in self.log if k == kind]

    def run(self, exercise_id="easy_1_count_vowels", code=None, clicks=()):
        log = self.log = []
        session = self.session
        st = types.ModuleType("streamlit")
        st.session_state = session
        st.set_page_config = lambda **k: None
        for name in ("title", "caption", "subheader", "write", "json", "code", "balloons"):
            setattr(st, name, (lambda n: lambda *a, **k: log.append((n, a[0] if a else None)))(name))
        for name in ("info", "warning", "success", "error", "markdown"):
            setattr(st, name, (lambda n: lambda m, *a, **k: log.append((n, m)))(name))
        st.sidebar = _Ctx()
        st.sidebar.selectbox = lambda *a, **k: exercise_id
        st.expander = lambda *a, **k: _Ctx()
        st.columns = lambda n: [_Ctx() for _ in range(n)]

        def text_area(label, key=None, **k):
            if code is not None:
                session[key] = code
            return session[key]

        def button(label, on_click=None, **k):
            clicked = label in clicks
            if clicked and on_click:
                on_click()
            return clicked and on_click is None

        st.text_area, st.button = text_area, button
        st.form = lambda *a, **k: _Ctx()
        st.form_submit_button = lambda label, **k: label in clicks
        components = types.ModuleType("streamlit.components.v1")
        components.html = lambda *a, **k: None
        st.components = types.ModuleType("streamlit.components")
        st.components.v1 = components
        self.monkeypatch.setitem(sys.modules, "streamlit.components", st.components)
        self.monkeypatch.setitem(sys.modules, "streamlit.components.v1", components)
        self.monkeypatch.setitem(sys.modules, "streamlit", st)
        self.monkeypatch.syspath_prepend(str(ROOT))
        runpy.run_path(str(ROOT / "app_debug.py"), run_name="__main__")
        return self


@pytest.fixture
def page(monkeypatch):
    return FakePage(monkeypatch)


def test_first_load_shows_the_starter_code_and_no_results(page):
    page.run()
    assert page.session["editor_easy_1_count_vowels"] == load_exercise("easy_1_count_vowels").starter
    assert page.messages("info") == []


def test_running_buggy_code_shows_failures_and_a_hint(page):
    page.run(clicks=["Run my fix"])
    assert any("FAIL" in m for m in page.messages("markdown"))
    assert any("Hint level 1 of 3" in m for m in page.messages("info"))


def test_running_the_same_code_again_escalates_the_hint(page):
    page.run(clicks=["Run my fix"])
    page.run(clicks=["Run my fix"])
    assert any("Hint level 2 of 3" in m for m in page.messages("info"))


def test_correct_code_is_marked_solved(page):
    page.run(code=load_exercise("easy_1_count_vowels").solution, clicks=["Run my fix"])
    assert any("All 6 tests pass" in m for m in page.messages("success"))


def test_solution_is_refused_before_three_attempts_and_shown_after(page):
    page.run(clicks=["Show solution"])
    assert page.messages("warning")
    assert not [m for m in page.messages("code") if "ch.lower()" in str(m)]
    for _ in range(3):
        page.run(clicks=["Run my fix"])
    page.run(clicks=["Show solution"])
    assert any("ch.lower()" in str(m) for m in page.messages("code"))


def test_page_shows_the_code_with_line_numbers_and_the_attempt_count(page):
    page.run()
    assert any(str(m).startswith("1 | def count_vowels") for m in page.messages("code"))
    assert any("The solution unlocks after 3" in m for m in page.messages("caption"))


def test_reset_restores_the_starter_code(page):
    page.run(code="# my edit\n")
    page.run(clicks=["Reset to starter"])
    assert page.session["editor_easy_1_count_vowels"] == load_exercise("easy_1_count_vowels").starter


def test_each_exercise_keeps_its_own_attempts(page):
    page.run(clicks=["Run my fix"])
    page.run(exercise_id="medium_1_add_item", clicks=["Run my fix"])
    assert any("Hint level 1 of 3" in m for m in page.messages("info"))


def test_blocked_code_shows_a_warning_instead_of_crashing(page):
    page.run(code="import os\n", clicks=["Run my fix"])
    assert any("could not run" in m for m in page.messages("warning"))
