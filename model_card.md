# Model Card: Debug Coach

## System Overview

**What it is.** The Debug Coach is a tutoring tool for Python debugging. It extends the Module 1 project, Game Glitch Investigator (Module 5 final project). A student edits a buggy function, the coach runs it against tests, names the most likely bug, and gives a hint that gets more specific on each attempt.

**What it uses.** A restricted code runner, static analysis with the `ast` module, rules over failing test results, and BM25 retrieval over two sources: 7 bug-pattern notes (plus 5 error notes) in `knowledge/debugging/`, and 5 cited public references in `data/public_references.json`. Hints are written ahead of time and filled in with the failing test, function, and line. No model is trained, fine-tuned, or called.

**Intended use.** Practice with six short Python exercises (two easy, two medium, two hard). It is a teaching and portfolio project.

**Not intended for.** Grading real coursework, running code written by someone else, or debugging programs outside the six exercises. The rules cover only the bug patterns listed below.

The earlier Glitch Coach, a hint agent inside the guessing game, is still in the repository. Its own limits are listed at the end of this card.

## Limitations and Biases

- **Six exercises and seven bug patterns.** The coach recognizes mutable defaults, changing a list while looping, late-binding closures, `range(... - 1)` and slice off-by-one, reversed results, letter case, and runtime errors. Any other bug is labeled `wrong_value` and gets a generic hint.
- **Constant and condition bugs get the weakest hints.** In `hard_2_game_logic`, a wrong range or score value produces the generic "work through it by hand" hint, because no rule can see which number is wrong.
- **The exercises are original, not copied.** The build environment had no internet access, so I wrote the exercises and cited public sources for the patterns. Easy exercises have no public source. The citations were checked, but they point to documentation, not to the exercise text.
- **Diagnosis is a heuristic.** Each diagnosis carries a confidence of 0.4 to 1.0. A student can fix the labeled bug, find a different bug, and receive advice that no longer fits until the next run.
- **Confidence is not a probability.** It combines output checks, how well the note matched, and the diagnosis confidence. On failing attempts it ranges from 0.79 to 0.96, so it separates little.
- **Retrieval matches words, not meaning.** BM25 over 17 short documents works because the planner uses fixed queries per bug pattern. A new pattern needs a new note and query.
- **English only, Python only.** I did not test the page with a screen reader or on small screens.
- **Limited testing.** The 19 scripted attempts were written by me while building the rules, so the 19 of 19 result overstates how the coach would do on real student code. No student has used it. The Streamlit page was tested against a stand-in for the Streamlit API and has not been run in a browser.

## Misuse and Prevention

**Running untrusted code.** The runner is the main risk. It blocks risky imports (`os`, `subprocess`, `socket` and others) and builtins (`open`, `eval`, `exec`, `input`), runs the code in a separate process with a 5 second limit and a CPU limit, and truncates output. This is a teaching aid. It is not a security boundary, and a determined user could find a way around a static blocklist. Run only code you wrote. A public deployment would need a container or similar isolation.

**Copying answers.** `solution.py` files are in the repository, so a student can read them. The reveal gate (three real failed attempts) and the leak check on hints stop the coach from giving the answer. They do not stop someone from opening the file. The coach is meant for self-study, not for graded work.

**Hint leaks.** Every hint is checked against the lines of the reference solution. A control test confirms the check can fail. A hint that contains a solution line is replaced by a plain fallback and confidence drops.

**Gaming the reveal gate.** Empty, invalid, and unchanged-starter submissions do not count toward the three attempts. A test covers this, after the harness showed that empty submissions had unlocked the solution.

**Bad edits to the notes.** If someone writes a wrong hint, the checks catch a missing placeholder, a hint that is too long, and a solution leak. They do not catch a false statement in the prose. Notes should be reviewed like code.

**Data collected.** Logs hold submitted code, hints, and traces. They hold no personal data. `logs/*.log` and `workspace/` are excluded from git.

## What Surprised Me While Testing

1. **My first letter-case rule fired on the wrong exercise.** Inputs like `'Normal'` in the game exercise contain a capital letter, so two attempts were misdiagnosed. I changed the rule to fire only when uppercase text separates failing tests from passing ones.
2. **A plausible "off by one" rule was wrong.** Checking whether the expected and actual numbers differ by 1 would have labeled a forgotten vowel as off-by-one. I replaced it with a static check for `range(... - 1)` and slice bounds.
3. **Empty submissions unlocked the solution.** The reveal count included empty and invalid input until a test showed it.
4. **One cited report did not say what I expected.** CPython issue 26842 asked for a longer tutorial explanation and was closed as "won't fix". The references file describes it as a public report and does not claim the docs changed.
5. **A correct fix can look different from mine.** `hard_1_make_multipliers` is also solved with a helper function. The tests check behavior, so the coach accepts it. A scripted attempt covers this.
6. **Hint level had to reset by function.** In the three-bug exercise, the level carried over when a different function started failing, so a new bug got a level 3 hint. I added the function to the attempt history.

## Collaboration with AI

I used Claude to build this project. I supplied the assignment and chose Module 1 as the base. I rejected the first version, the Glitch Coach, because helping a player guess a number is a weak real-world task. I asked for a Python coding coach with easy, medium, and hard exercises instead. Claude wrote most of the code, tests, and documentation, and I reviewed the results.

**A suggestion I accepted: tiered hints with a reveal gate.** Claude proposed three hint levels (a question, the location, the technique) and a solution that unlocks only after three real failed attempts. I accepted it because it keeps the tool a tutor and not an answer lookup. The harness checks that hints escalate and that the gate holds.

**A suggestion I changed: the letter-case rule.** Claude's first rule blamed letter case whenever the failing input had an uppercase letter. The harness showed it misdiagnosing two attempts on the game exercise. I asked for a narrower rule that fires only when uppercase text separates failing tests from passing ones and the code never changes case. The rule is still a heuristic and the README says so.

**A second change: original exercises.** The first plan copied exercises from public sites. The build environment had no network, and copied text raises licensing questions. We wrote original exercises and cited verified sources for the patterns.

**A decision left open: the Hard attempt limit in the game.** Claude pointed out that raising Hard to 7 attempts would make the game fair. I kept the Module 1 settings because the change alters the game I was asked to extend.

*Draft note: these paragraphs describe the work as it happened. Rewrite them in your own words before you submit, and replace the examples if different ones are closer to your experience.*

## Baseline vs Specialized Output

The baseline is what a student sees without the coach: the failing test count, and the first failing test with its expected and actual values. The specialized behavior is the tiered, Socratic hint style. Both were measured on the six exercise starters by `python eval_debug.py`. The measures come from the diagnosis, not from keywords in the hint.

| Output | Average words | Asks a question | Names the function or line | Quotes a test input |
|---|---|---|---|---|
| Plain test report (baseline) | 13.5 | 0% | 0% | 0% |
| Coach hint, level 1 | 25.3 | 100% | 100% | 100% |
| Coach hint, level 2 | 26.3 | 17% | 100% | 0% |
| Coach hint, level 3 | 30.8 | 0% | 0% | 0% |

Example for `medium_1_add_item`:

- **Baseline:** `add_item('b') expected ["b"], got ["a", "b"]`
- **Level 1:** Look at `add_item('b')`: expected ["b"], got ["a", "b"]. Something from an earlier call is still there. Where could a value be stored between calls?
- **Level 3:** Use None as the default value. Inside the function, create a new list only when the argument is None, then work with that list.

The baseline never points to a location or asks a question. Level 1 does both, and level 3 gives the technique without a line from the solution. The test sample is six exercises, and the style is fixed by the hint templates, so this shows the behavior difference and not learning outcomes. No student study was done.

## Future Improvements

- Test with real student submissions, and add rules for the bugs they actually make.
- Give constant and condition bugs a better hint, for example by comparing outputs for neighboring inputs.
- Run submissions in a container for real isolation.
- Add more exercises, including ones from a licensed public set.
- Optionally let a language model reword hints, with the same leak check, and compare it against the templates.

## Evaluation Summary

| Evidence | Result |
|---|---|
| `python -m pytest` | 177 passed |
| `python eval_debug.py` | 70 of 70 checks passed |
| Exercise data | All 6 starters fail some tests. All 6 solutions pass every test |
| Scripted student attempts | 19 of 19 diagnosed as expected, including wrong fixes and an alternative correct fix |
| Leak check | 2 of 2, including a control that proves the check can fail |
| Confidence on failing attempts | 0.79 to 0.96 |

Full output is in the [README](README.md) and `logs/debug_eval_report.txt`.

## Earlier Iteration: Glitch Coach (Game)

The Glitch Coach gives advice on the guessing game. It uses BM25 over 10 strategy notes and 3 simulated past-game summaries. Its limits:

- The past-game data comes from 500 seeded games per difficulty played by simple bots, not real players.
- Every note recommends halving the range. A player who wants to explore gets advice that does not fit.
- Hard difficulty allows a maximum win rate of about 31% with perfect play, because 5 guesses cover at most 31 numbers.
- The optional language model rewrite was tested only with stand-in clients, not a live API.

Evidence: 81 tests and 43 of 43 harness checks for the game coach. The code is in `app.py`, `coach/`, `demo.py`, and `eval_harness.py`.
