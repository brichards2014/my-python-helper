import streamlit as st
import streamlit.components.v1 as components

from coach.log import append_trace
from debug_coach.agent import coach_submission, reveal_solution
from debug_coach.editor import EDITOR_JS, number_lines
from debug_coach.guardrails import REVEAL_AFTER_FAILED_ATTEMPTS
from debug_coach.exercises import list_exercises

st.set_page_config(page_title="Debug Coach", page_icon="🐞")
st.title("🐞 Debug Coach")
st.caption("Fix the buggy Python function. The coach runs your code and gives hints, not answers.")

exercises = {e.id: e for e in list_exercises()}
state = st.session_state
state.setdefault("histories", {})
state.setdefault("results", {})


def label(i):
    done = state.results.get(i) is not None and state.results[i].solved
    return f"{'✓ ' if done else ''}[{exercises[i].difficulty}] {exercises[i].title}"


exercise_id = st.sidebar.selectbox("Exercise", list(exercises), format_func=label)
exercise = exercises[exercise_id]
solved_count = sum(1 for r in state.results.values() if r.solved)
st.sidebar.caption(f"Solved: {solved_count} of {len(exercises)}")
history = state.histories.setdefault(exercise_id, [])
editor_key = f"editor_{exercise_id}"


def reset_editor():
    state[editor_key] = exercise.starter


if editor_key not in state:
    reset_editor()

st.subheader(exercise.title)
st.write(exercise.description)
with st.expander("Where this exercise comes from"):
    st.write(exercise.origin)
    for source in exercise.sources:
        st.markdown(f"- [{source['title']}]({source['url']})")

components.html(EDITOR_JS, height=0)  # Tab indents and Enter keeps the indent in the code box
st.caption("Tab indents, Shift+Tab removes an indent. Press Ctrl+Enter (or Cmd+Enter) to run.")
with st.form(f"run_form_{exercise_id}"):
    code = st.text_area("Your code", key=editor_key, height=320)
    run_clicked = st.form_submit_button("Run my fix")
col1, col2 = st.columns(2)
with col1:
    st.button("Reset to starter", on_click=reset_editor)
with col2:
    reveal_clicked = st.button("Show solution")
failed = sum(1 for a in history if a.tag not in ("solved", "invalid_input"))
st.caption(f"Attempts so far: {len(history)}. The solution unlocks after {REVEAL_AFTER_FAILED_ATTEMPTS} real failed attempts (you have {failed}).")
with st.expander("Your code with line numbers (hints refer to these)", expanded=True):
    st.code(number_lines(code), language=None)

if run_clicked:
    guidance = coach_submission(exercise, code, history)
    history.append(guidance.attempt)
    state.results[exercise_id] = guidance
    append_trace({"exercise": exercise_id, "attempt": len(history), **guidance.to_dict()})

guidance = state.results.get(exercise_id)
if guidance is not None:
    st.subheader(f"Tests: {guidance.passed} of {guidance.total} pass")
    if guidance.run is not None:
        for case in guidance.run.cases:
            detail = ""
            if not case.passed and not case.hidden:
                detail = f" ({case.error_type}: {case.error_message})" if case.error_type else f" (expected {case.expected!r}, got {case.actual!r})"
            st.markdown(f"**{'PASS' if case.passed else 'FAIL'}** {case.name}{detail}")
        if not guidance.run.cases:
            st.warning(f"The tests could not run ({guidance.run.status}): {guidance.run.message}")
    if guidance.progress:
        st.caption(guidance.progress)
    if guidance.solved:
        st.balloons()
        st.success(guidance.hint)
    else:
        st.info(f"Hint level {guidance.level} of 3: {guidance.hint}")
        for reference in guidance.references:
            st.markdown(f"Read more: [{reference['title']}]({reference['url']})")
        if guidance.confidence < 0.6:
            st.warning(f"Low confidence ({guidance.confidence}). Treat this hint with care.")
    with st.expander("Why this advice?"):
        st.write(f"Likely pattern: {guidance.tag}")
        st.write(f"Confidence: {guidance.confidence}")
        st.write("Sources:", ", ".join(guidance.sources) or "none")
        st.json(guidance.trace)

if reveal_clicked:
    allowed, text = reveal_solution(exercise, history)
    if allowed:
        st.code(text, language="python")
    else:
        st.warning(text)
