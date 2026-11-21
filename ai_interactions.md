# AI Interactions

## Advanced Edge-Case Testing

### Prompt

I asked Claude to add more pytest cases for the extra credit after my two bug fixes were done and passing. My message was: "Lets do the additional pytests for the extra cred." Claude had the project files and the grading rubric in context, so it targeted the stretch requirement of three or more edge-case tests.

### What Claude Generated

Claude extended `tests/test_game_logic.py` with edge-case tests for `parse_guess`, `check_guess`, `update_score`, and `get_range_for_difficulty`. It kept my four original tests and used `pytest.mark.parametrize` to cover several inputs with one test function.

### Edge Cases and Rationale

| Edge case | Function | Why it was chosen |
|---|---|---|
| Empty string and `None` | `parse_guess` | The text box starts empty, so this is the most common bad input |
| `"abc"`, `"12abc"`, `"1e3"`, `"nan"`, `"--5"`, spaces only | `parse_guess` | Players can type anything. The game must show an error instead of crashing |
| `"-5"` | `parse_guess` | Confirms negative numbers parse correctly |
| `"7.9"` | `parse_guess` | The code truncates decimals to 7. The test documents that behavior |
| `" 42 "` | `parse_guess` | Confirms spaces around a number are ignored |
| Guess of -5 against a secret of 10 | `check_guess` | Confirms the comparison still gives the right hint for negative values |
| Win on attempt 1 and attempt 20 | `update_score` | The points formula goes negative on late attempts without the 10-point floor |
| Unknown difficulty name | `get_range_for_difficulty` | Confirms the fallback range of 1 to 50 |

### Verification

I ran `py -m pytest` from the project root. The terminal output is pasted in the Test Results section of `README.md`.

### Limitation Found

The edge-case tests showed that `parse_guess` accepts numbers outside the game range. A guess of `-5` or `500` is accepted and counts as an attempt. The tests document this current behavior. I did not fix it in this project.

## Final Project, Iteration 1: Glitch Coach (Game)

### Prompt

I gave Claude the Module 5 assignment and the Module 1 starter code and said: "Final assignment, lets also do the optional stretch features. I am using Module 1." The new repository was https://github.com/brichards2014/ai-game-system.

### What Claude Generated

Claude built the Glitch Coach on top of the Module 1 game: a BM25 retriever over two sources, a rule-based planning agent with output checks and a fallback, an optional model rewrite, a simulator, an evaluation harness, a command-line demo, a Streamlit coach panel, tests, an architecture diagram, and the documentation. It also fixed a scoring bug that Module 1 left in place and added the range check that my edge-case tests had flagged as a limitation.

### Verification

`python -m pytest` (81 passed) and `python eval_harness.py` (43 of 43 checks passed) were run during the build. The README holds the pasted output. The Streamlit app was tested against a stand-in for the Streamlit API. A manual play-through in a real browser with `python -m streamlit run app.py` is still needed.

### Limitation Found

Hard difficulty allows a maximum win rate of about 31%, because 5 guesses cover at most 31 numbers. This is a property of the Module 1 settings, not of the coach.

### Agent Reasoning Traces for the Glitch Coach (Stretch: Agentic Workflow Enhancement)

Every coach call records its steps: validate, observe, plan, retrieve, compose, check, optionally revise, and score confidence. The traces below come from `python demo.py --save-traces` (Scenario 2, Hard, secret 88). All 12 traces from the three scripted games are in [logs/sample_traces.jsonl](logs/sample_traces.jsonl). A trace is also visible to the player in the app under "Why this advice?".

### Trace A: the player ignores a hint (guesses so far: 50 Too Low, 20 Too Low)

The planner sees that guess 20 sits below the range already ruled out by the hint on 50. It switches from the default "narrow" situation to "wasted_guess" and retrieves the matching note.

```
validate   {"problems": []}
observe    {"lo": 51, "hi": 100, "size": 50, "attempts_left": 3, "last_guess": 20, "wasted_last_guess": true}
plan       {"situation": "wasted_guess", "query": "guess outside range already ruled out ignored hint repeat wasted attempt"}
retrieve   {"knowledge": [["hint_discipline#wasted-guess", 20.7784, 0.4874], ["endgame#running-out-of-attempts", 4.1911, 0.0983], ["hint_discipline#trust-the-hints", 1.7709, 0.0415]], "history": [["past_games#hard", 12.5043]]}
compose    {"used": "hint_discipline#wasted-guess", "advice": "Your last guess 20 was already ruled out by an earlier hint. The secret is between 51 and 100. Guess 75."}
check      {"checks": {"guess_in_range": true, "mentions_guess": true, "no_unfilled_template": true, "within_word_limit": true}}
context    {"used": "past_games#hard"}
confidence {"checks_passed": 1.0, "relevance": 0.4874, "margin": 0.8, "confidence": 1.0}
RESULT     Your last guess 20 was already ruled out by an earlier hint. The secret is between 51 and 100. Guess 75.
```

### Trace B: the endgame (guess so far: 50 Too Low)

With 4 attempts left and 50 numbers, a win needs 6 more guesses. The planner picks the "endgame" situation, so the advice says a win cannot be guaranteed.

```
validate   {"problems": []}
observe    {"lo": 51, "hi": 100, "size": 50, "attempts_left": 4, "last_guess": 50, "wasted_last_guess": false}
plan       {"situation": "endgame", "query": "attempts running out few attempts left cannot guarantee win endgame limit"}
retrieve   {"knowledge": [["endgame#running-out-of-attempts", 20.6092, 0.491], ["endgame#few-candidates-left", 6.6228, 0.1578], ["hint_discipline#wasted-guess", 6.4137, 0.1528]], "history": [["past_games#hard", 12.5043]]}
compose    {"used": "endgame#running-out-of-attempts", "advice": "4 attempts left and 50 numbers remain, so a win cannot be guaranteed. Guess 75 for the best chance."}
check      {"checks": {"guess_in_range": true, "mentions_guess": true, "no_unfilled_template": true, "within_word_limit": true}}
context    {"used": "past_games#hard"}
confidence {"checks_passed": 1.0, "relevance": 0.491, "margin": 0.68, "confidence": 1.0}
RESULT     4 attempts left and 50 numbers remain, so a win cannot be guaranteed. Guess 75 for the best chance.
```

### Failure path

The revise step does not appear in the sample traces because the sample notes are valid. The tests exercise it by giving the agent a note with a broken template. The trace then contains a `revise` step, the advice becomes a plain midpoint hint, and confidence drops to 0.4. See `test_bad_template_triggers_revision_and_low_confidence` in `tests/test_agent.py`.

## Final Project, Iteration 2: Debug Coach

### Prompt

After testing the Glitch Coach, I said the game was too weak as a real-world task and asked: "How about a coding coach, it provides codes from available public reports or existing exercises on the internet, then has the user try different fixes and provides guidance based on the submission. Due to the scope of this, we only need a few quick examples you can grab to make easy, medium hard. The language should be python."

### What Claude Generated

- A restricted code runner (`debug_coach/sandbox.py`) with a static blocklist, a 5 second limit, and hidden tests.
- A diagnosis step (`debug_coach/diagnose.py`) that uses the `ast` module and the failing tests.
- A planning agent (`debug_coach/agent.py`) with tiered hints, two retrieval sources, output checks, a fallback, a confidence score, and a recorded trace.
- Six exercises (two each for easy, medium, hard), 12 bug-pattern notes, and 5 cited public references.
- A command-line tool, a Streamlit page, an evaluation harness, 19 scripted student attempts, 96 new tests, a Mermaid diagram, and the README and model card.

The network was unavailable, so Claude wrote original exercises and cited public sources instead of copying exercise text. It read each cited page before including it.

### Verification

- `python -m pytest`: 177 passed.
- `python eval_debug.py`: 70 of 70 checks passed.
- `python debug_cli.py demo --brief`: four scripted scenarios. The output is pasted in the README.
- The Streamlit page was tested against a stand-in for the Streamlit API. A manual run with `python -m streamlit run app_debug.py` is still needed.

### Problems Found and Fixed During the Build

| Problem | How it was found | Fix |
|---|---|---|
| Infinite loop reported as a crash | Sandbox test | Raised the CPU limit above the 5 second timeout |
| Letter-case rule fired on the game exercise | Scripted attempts | Rule now needs uppercase text to separate failing from passing tests |
| "Numbers differ by 1" rule mislabeled a forgotten vowel | Scripted attempts | Replaced with a static `range(... - 1)` and slice check |
| Empty submissions unlocked the solution | Reveal test | Empty and invalid input no longer count |
| Hint level carried over to a new function | Hard exercise attempts | Attempt history now includes the function |
| Won't-fix issue ranked first for the default-argument pattern | Retrieval test | Show up to two references and describe the issue accurately |

### Limitation Found

The scripted attempts are mine, so 19 of 19 overstates how the coach would do on real student code. Constant and condition bugs get the generic `wrong_value` hint. No real student has used the tool.

## Agent Reasoning Traces for the Debug Coach (Stretch: Agentic Workflow Enhancement)

Every submission records its steps: validate, run, diagnose, plan, retrieve, compose, check, optionally revise, and score confidence. The traces below come from `python debug_cli.py demo --save-traces`, scenario `medium_1_add_item`. All 8 records are in [logs/debug_sample_traces.jsonl](logs/debug_sample_traces.jsonl). The student sees the same trace under "Why this advice?".

### Trace A: first attempt (starter code, level 1)

```
validate    ok, unchanged starter
run         status ok, 4 of 6 tests passed
diagnose    mutable_default, confidence 0.9, line 1 (pattern found by ast)
plan        level 1, query "default argument list shared between calls remembers earlier call"
retrieve    knowledge: patterns#mutable-default-argument (18.59, relevance 0.61)
            references found: ref#cpython-26842, ref#python-tutorial-default-arguments
compose     used patterns#mutable-default-argument
check       has_text, within_word_limit, no_unfilled_template, no_solution_leak,
            retrieval_matches_diagnosis: all true
confidence  checks 1.0, relevance 0.61, diagnosis 0.9 -> 0.96
RESULT      Look at `add_item('b')`: expected ["b"], got ["a", "b"]. Something from an
            earlier call is still there. Where could a value be stored between calls?
```

References are not shown at level 1.

### Trace B: same code again (level 2)

The diagnosis, retrieval, and checks are the same. The plan step raises the level from 1 to 2 because the attempt history holds a failed attempt with the same tag. The hint now names the cause and the line, and two references are shown.

```
plan        level 2
RESULT      The default value at line 1 is created once, when the function is defined,
            and every call shares it. A list or dictionary used as a default keeps its changes.
references  CPython issue 26842: tutorial should explain default parameter lifetime
            Python tutorial, 4.9.1 Default Argument Values
```

### Trace C: same code a third time (level 3)

```
plan        level 3
RESULT      Use None as the default value. Inside the function, create a new list only
            when the argument is None, then work with that list.
```

Level 3 names the technique. It does not contain a line from `solution.py`, and the `no_solution_leak` check confirms it. After this attempt the student has made three failed attempts, so `reveal` is allowed.

### Failure path

The revise step does not appear in the sample traces because the sample notes are valid. The tests give the agent a note with a broken template or a note that contains a solution line. The trace then shows a failed check, the hint becomes a plain fallback, and confidence drops. See the fallback and leak tests in `tests/test_debug_agent.py`.
