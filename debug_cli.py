"""Command-line Debug Coach.

    python debug_cli.py list                      show the exercises
    python debug_cli.py start easy_1_count_vowels create workspace/easy_1_count_vowels.py to edit
    python debug_cli.py check easy_1_count_vowels run your fix and get a hint
    python debug_cli.py reveal easy_1_count_vowels show the solution (after 3 failed attempts)
    python debug_cli.py demo                      run scripted student attempts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from coach.log import append_trace
from debug_coach.agent import Attempt, Guidance, coach_submission, reveal_solution
from debug_coach.exercises import ROOT, Exercise, list_exercises, load_exercise
from debug_coach.scripted import scripts_for

WORKSPACE = ROOT / "workspace"
SAMPLE_TRACE_PATH = ROOT / "logs" / "debug_sample_traces.jsonl"
DEMO_EXERCISES = ["easy_1_count_vowels", "medium_1_add_item", "hard_2_game_logic"]


def render(exercise: Exercise, guidance: Guidance, show_trace: bool = False, brief: bool = False) -> None:
    run = guidance.run
    print(f"Tests: {guidance.passed} of {guidance.total} pass")
    if run is not None and run.cases:
        for case in run.cases:
            if brief and case.passed:
                continue
            line = f"  {'PASS' if case.passed else 'FAIL'}  {case.name}"
            if not case.passed and not case.hidden:
                detail = f"{case.error_type}: {case.error_message}" if case.error_type else f"expected {case.expected!r}, got {case.actual!r}"
                line += f"  ({detail})"
            print(line)
    elif run is not None:
        print(f"  The tests could not run ({run.status}): {run.message}")
    if guidance.progress:
        print(guidance.progress)
    label = "Solved" if guidance.solved else f"Coach, hint level {guidance.level} of 3"
    print(f"{label}: {guidance.hint}")
    for reference in guidance.references:
        print(f"Read more: {reference['title']} ({reference['url']})")
    print(f"  [pattern={guidance.tag} confidence={guidance.confidence} sources={', '.join(guidance.sources) or 'none'}"
          f"{' revised' if guidance.revised else ''}]")
    if show_trace:
        for step in guidance.trace:
            print(f"    trace: {json.dumps(step, ensure_ascii=False)}")


def _history_path(exercise_id: str) -> Path:
    return WORKSPACE / f"{exercise_id}.attempts.json"


def _load_history(exercise_id: str) -> list[Attempt]:
    path = _history_path(exercise_id)
    if not path.exists():
        return []
    try:
        return [Attempt(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return []


def _save_history(exercise_id: str, history: list[Attempt]) -> None:
    WORKSPACE.mkdir(exist_ok=True)
    _history_path(exercise_id).write_text(json.dumps([a.__dict__ for a in history]), encoding="utf-8")


def cmd_list(_args) -> int:
    for e in list_exercises():
        print(f"{e.id:<28} {e.difficulty:<7} {e.title}")
    return 0


def cmd_start(args) -> int:
    exercise = load_exercise(args.exercise)
    WORKSPACE.mkdir(exist_ok=True)
    path = WORKSPACE / f"{exercise.id}.py"
    if not path.exists():
        path.write_text(exercise.starter, encoding="utf-8")
    print(f"{exercise.title} ({exercise.difficulty})\n{exercise.description}\n")
    print(f"Edit this file: {path}\nThen run: python debug_cli.py check {exercise.id}")
    return 0


def cmd_check(args) -> int:
    exercise = load_exercise(args.exercise)
    path = Path(args.file) if args.file else WORKSPACE / f"{exercise.id}.py"
    if not path.exists():
        print(f"No file at {path}. Run: python debug_cli.py start {exercise.id}")
        return 1
    history = _load_history(exercise.id)
    guidance = coach_submission(exercise, path.read_text(encoding="utf-8"), history)
    render(exercise, guidance, args.trace)
    history.append(guidance.attempt)
    _save_history(exercise.id, history)
    return 0 if guidance.solved else 2


def cmd_reveal(args) -> int:
    exercise = load_exercise(args.exercise)
    ok, text = reveal_solution(exercise, _load_history(exercise.id))
    print(text)
    return 0 if ok else 1


def demo(options) -> int:
    if options.save_traces and SAMPLE_TRACE_PATH.exists():
        SAMPLE_TRACE_PATH.unlink()
    for number, exercise_id in enumerate(DEMO_EXERCISES, start=1):
        exercise = load_exercise(exercise_id)
        print(f"\n=== Scenario {number}: {exercise.title} ({exercise.difficulty}) ===")
        print(exercise.description)
        history: list[Attempt] = []
        script = scripts_for(exercise)
        if exercise_id == "medium_1_add_item":  # a student who repeats the same mistake, to show hints escalate
            script = [("starter code", exercise.starter, ""), ("same code again", exercise.starter, ""),
                      ("same code a third time", exercise.starter, ""), ("correct fix", exercise.solution, "")]
        for attempt_number, (label, source, _expected) in enumerate(script, start=1):
            print(f"\n--- Attempt {attempt_number}: {label} ---")
            guidance = coach_submission(exercise, source, history)
            render(exercise, guidance, options.trace, options.brief)
            history.append(guidance.attempt)
            if options.save_traces:
                append_trace({"scenario": exercise.id, "attempt": attempt_number, "label": label, **guidance.to_dict()}, SAMPLE_TRACE_PATH)

    print("\n=== Scenario 4: guardrails ===")
    exercise = load_exercise("medium_1_add_item")
    cases = [
        ("syntax error", "def add_item(item, items=[]:\n    return items\n"),
        ("blocked import", "import os\ndef add_item(item, items=None):\n    return [item]\n"),
        ("starter code, still buggy", exercise.starter),
    ]
    history = []
    for label, source in cases:
        print(f"\n--- {label} ---")
        guidance = coach_submission(exercise, source, history)
        render(exercise, guidance, options.trace, options.brief)
        history.append(guidance.attempt)
    print("\n--- asking for the solution too early ---")
    ok, text = reveal_solution(exercise, history[:1])
    print(text)
    print("\n--- asking for the solution after 3 failed attempts ---")
    ok, text = reveal_solution(exercise, history)
    print(text.rstrip())
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("start", "check", "reveal"):
        p = sub.add_parser(name)
        p.add_argument("exercise")
        if name == "check":
            p.add_argument("--file", help="path to a different file to check")
            p.add_argument("--trace", action="store_true", help="print the agent trace")
    d = sub.add_parser("demo")
    d.add_argument("--trace", action="store_true")
    d.add_argument("--brief", action="store_true", help="list only failing tests")
    d.add_argument("--save-traces", action="store_true", help="write traces to logs/debug_sample_traces.jsonl")
    args = parser.parse_args(argv)
    try:
        return {"list": cmd_list, "start": cmd_start, "check": cmd_check, "reveal": cmd_reveal, "demo": demo}[args.command](args)
    except FileNotFoundError:
        print(f"Unknown exercise: {getattr(args, 'exercise', '')}. Run: python debug_cli.py list")
        return 1


if __name__ == "__main__":
    sys.exit(main())
