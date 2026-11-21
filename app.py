import random

import streamlit as st

from coach import CoachState, get_advice
from coach.llm import make_client_from_env
from coach.log import append_trace
from logic_utils import (
    check_guess,
    get_attempt_limit,
    get_range_for_difficulty,
    parse_guess,
    update_score,
    validate_range,
)


st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("A guessing game with a retrieval-backed coach.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit = get_attempt_limit(difficulty)
low, high = get_range_for_difficulty(difficulty)


def reset_game():
    st.session_state.secret = random.randint(low, high)
    st.session_state.attempts = 0
    st.session_state.score = 0
    st.session_state.status = "playing"
    st.session_state.history = []
    st.session_state.guesses = []  # (guess, outcome) pairs the coach reads
    st.session_state.coach_cache = {}
    st.session_state.traced = None


# The secret must match the selected difficulty, so a difficulty change starts a new game.
if st.session_state.get("difficulty") != difficulty:
    st.session_state.difficulty = difficulty
    reset_game()

if "llm_client" not in st.session_state:
    # None unless ANTHROPIC_API_KEY is set. The coach works without it.
    st.session_state.llm_client = make_client_from_env()

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")

st.subheader("Make a guess")

info_slot = st.empty()  # filled after the guess is processed so the count is current


def render_info():
    info_slot.info(
        f"Guess a number between {low} and {high}. "
        f"Attempts left: {attempt_limit - st.session_state.attempts}"
    )


with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("History:", st.session_state.history)

# A form lets the Enter key submit the guess, and clears the box after each guess.
with st.form(f"guess_form_{difficulty}", clear_on_submit=True):
    raw_guess = st.text_input(
        "Enter your guess:",
        key=f"guess_input_{difficulty}"
    )
    submit = st.form_submit_button("Submit Guess 🚀")

col1, col2, col3 = st.columns(3)
with col1:
    new_game = st.button("New Game 🔁")
with col2:
    show_hint = st.checkbox("Show hint", value=True)
with col3:
    show_coach = st.checkbox("Show coach", value=True)

if new_game:
    reset_game()
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    render_info()
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    ok, guess_int, err = parse_guess(raw_guess)
    if ok:
        ok, err = validate_range(guess_int, low, high)

    if not ok:
        # Guardrail: bad input is rejected and does not use an attempt.
        st.error(err)
    else:
        st.session_state.attempts += 1
        st.session_state.history.append(guess_int)

        outcome, message = check_guess(guess_int, st.session_state.secret)
        st.session_state.guesses.append((guess_int, outcome))

        if show_hint:
            st.warning(message)

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=st.session_state.attempts,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        else:
            if st.session_state.attempts >= attempt_limit:
                st.session_state.status = "lost"
                st.error(
                    f"Out of attempts! "
                    f"The secret was {st.session_state.secret}. "
                    f"Score: {st.session_state.score}"
                )

render_info()

if show_coach and st.session_state.status == "playing":
    coach_state = CoachState(
        difficulty=difficulty,
        low=low,
        high=high,
        attempt_limit=attempt_limit,
        guesses=tuple(st.session_state.guesses),
    )
    # The coach never receives the secret. Results are cached so a rerun does not repeat a model call.
    if coach_state not in st.session_state.coach_cache:
        st.session_state.coach_cache = {
            coach_state: get_advice(coach_state, llm_client=st.session_state.llm_client)
        }
    result = st.session_state.coach_cache[coach_state]

    if st.session_state.traced != coach_state:
        append_trace({"difficulty": difficulty, "guess_count": len(coach_state.guesses), **result.to_dict()})
        st.session_state.traced = coach_state

    st.subheader("Glitch Coach")
    st.info(result.advice)
    if result.low_confidence:
        st.warning(f"Low confidence ({result.confidence}). Treat this advice with care.")
    with st.expander("Why this advice?"):
        st.write(f"Situation: {result.situation}")
        st.write(f"Confidence: {result.confidence}")
        st.write("Sources:", ", ".join(result.sources) or "none")
        if result.context:
            st.caption(result.context)
        st.json(result.trace)

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
