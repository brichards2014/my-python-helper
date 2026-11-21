"""Evaluation harness for the Debug Coach.

    python eval_debug.py             # full run, writes logs/debug_eval_report.txt
    python eval_debug.py --no-write  # print only

It checks the exercises, the diagnosis of scripted student attempts, retrieval, hint
escalation, the no-solution-leak guardrail, the sandbox guardrails, and the reveal gate.
It compares the coach with a plain test report. It exits with code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from coach.retriever import Document, Retriever
from debug_coach import guardrails, sandbox
from debug_coach.agent import TAG_QUERIES, Attempt, build_retriever, coach_submission, reveal_solution
from debug_coach.exercises import list_exercises
from debug_coach.scripted import scripts_for

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "logs" / "debug_eval_report.txt"


@dataclass
class Check:
    group: str
    name: str
    passed: bool
    detail: str = ""


def exercise_checks(exercises) -> list[Check]:
    checks = []
    for e in exercises:
        starter = sandbox.run_submission(e.starter, e.cases)
        solution = sandbox.run_submission(e.solution, e.cases)
        ok = starter.status == "ok" and 0 < starter.passed < starter.total and solution.all_passed
        checks.append(Check("exercises", f"{e.id}: starter fails some tests, solution passes all", ok,
                            f"starter {starter.passed}/{starter.total}, solution {solution.passed}/{solution.total}"))
    return checks


def diagnosis_checks(exercises) -> tuple[list[Check], list]:
    """Run every scripted attempt. Returns the checks and all guidance objects for reuse."""
    checks, outputs = [], []
    correct = total = 0
    for e in exercises:
        history = []
        for label, source, expected in scripts_for(e):
            guidance = coach_submission(e, source, history)
            history.append(guidance.attempt)
            outputs.append((e, label, expected, guidance))
            total += 1
            ok = guidance.tag == expected
            correct += ok
            checks.append(Check("diagnosis", f"{e.id}: {label}", ok, f"expected {expected}, got {guidance.tag}"))
    checks.append(Check("diagnosis", f"overall accuracy {correct}/{total}", correct == total, ""))
    return checks, outputs


def retrieval_checks() -> list[Check]:
    retriever = build_retriever()
    checks = []
    for tag, query in TAG_QUERIES.items():
        hits = retriever.search(query, k=1, source="knowledge")
        got = hits[0].doc.fields.get("pattern") if hits else None
        checks.append(Check("retrieval", f"query for {tag} returns the {tag} note", got == tag, f"top note pattern: {got}"))
    for tag in ("mutable_default", "modify_while_iterating", "late_binding"):
        hits = [h for h in retriever.search(TAG_QUERIES[tag], k=3, source="reference") if h.doc.fields["pattern"] == tag]
        checks.append(Check("retrieval", f"public references found for {tag}", bool(hits), ", ".join(h.doc.doc_id for h in hits)))
    return checks


def escalation_checks(exercises) -> list[Check]:
    checks = []
    for e in exercises:
        history, levels, hints = [], [], []
        for _ in range(4):
            g = coach_submission(e, e.starter, history)
            history.append(g.attempt)
            levels.append(g.level)
            hints.append(g.hint)
        ok = levels == [1, 2, 3, 3] and len(set(hints[:3])) == 3
        checks.append(Check("escalation", f"{e.id}: same mistake repeated gives levels 1, 2, 3, 3 with different hints", ok, f"levels {levels}"))
    e = exercises[0]
    first = coach_submission(e, e.starter, [])
    second = coach_submission(e, e.starter, [first.attempt])
    changed = coach_submission(e, e.solution.replace('"aeiou"', '"aeio"'), [first.attempt, second.attempt])
    checks.append(Check("escalation", "a different kind of failure restarts at level 1", changed.level == 1, f"level {changed.level}"))
    return checks


def leak_checks(exercises, outputs) -> list[Check]:
    texts = 0
    leaks = []
    for e in exercises:
        history = []
        for _ in range(3):  # every hint level on the starter
            g = coach_submission(e, e.starter, history)
            history.append(g.attempt)
            text = g.hint + " " + " ".join(r["title"] for r in g.references)
            texts += 1
            leaks += [(e.id, line) for line in guardrails.leaked_lines(text, e.solution, e.starter)]
    for e, label, _expected, g in outputs:
        if not g.solved:
            texts += 1
            leaks += [(e.id, line) for line in guardrails.leaked_lines(g.hint, e.solution, e.starter)]
    checks = [Check("leak", f"no solution line appears in {texts} generated hints", not leaks, f"leaks: {leaks[:3]}")]

    e = next(x for x in exercises if x.id == "medium_1_add_item")
    control = "Try this: if items is None:"  # a solution-only line, so the guardrail must flag it
    checks.append(Check("leak", "control: the leak check flags a hint that contains a solution line", bool(guardrails.leaked_lines(control, e.solution, e.starter)), ""))
    return checks


def sandbox_checks(exercises) -> list[Check]:
    e = exercises[0]
    cases = [
        ("infinite loop times out", "while True:\n    pass\n", "timeout"),
        ("syntax error is reported", "def f(:\n", "syntax_error"),
        ("import os is blocked", "import os\n", "blocked"),
        ("open() is blocked", "open('x.txt', 'w')\n", "blocked"),
        ("input() is blocked", "x = input()\n", "blocked"),
        ("error at load time is reported", "raise ValueError('boom')\n", "load_error"),
    ]
    original = sandbox.TIMEOUT_SECONDS
    sandbox.TIMEOUT_SECONDS = 1
    try:
        checks = []
        for name, source, status in cases:
            run = sandbox.run_submission(source, e.cases)
            checks.append(Check("sandbox", name, run.status == status, f"status {run.status}"))
        flood = sandbox.run_submission("print('x' * 10**7)\ndef count_vowels(t):\n    return 0\n", e.cases)
        checks.append(Check("sandbox", "huge printed output is truncated and the run still completes", flood.status == "ok" and len(flood.stdout) <= 500, f"status {flood.status}"))
        crash = sandbox.run_submission("def count_vowels(t):\n    raise RuntimeError('x')\n", e.cases)
        checks.append(Check("sandbox", "a crashing function fails its tests without stopping the run", crash.status == "ok" and crash.passed == 0, f"{crash.passed} passed"))
    finally:
        sandbox.TIMEOUT_SECONDS = original
    guidance = coach_submission(e, "", [])
    checks.append(Check("sandbox", "empty submission is refused before running", guidance.tag == "invalid_input", guidance.hint))
    guidance = coach_submission(e, "x = 1\n" * 10_000, [])
    checks.append(Check("sandbox", "oversized submission is refused", guidance.tag == "invalid_input", guidance.hint))
    return checks


def reveal_checks(exercises) -> list[Check]:
    e = exercises[0]
    failed = Attempt(3, 6, "case_sensitivity", "count_vowels")
    checks = []
    for count in (0, 1, 2):
        ok, _ = reveal_solution(e, [failed] * count)
        checks.append(Check("reveal", f"solution is refused after {count} failed attempts", not ok, ""))
    ok, text = reveal_solution(e, [failed] * 3)
    checks.append(Check("reveal", "solution is shown after 3 failed attempts", ok and text == e.solution, ""))
    ok, _ = reveal_solution(e, [Attempt(0, 6, "invalid_input")] * 5)
    checks.append(Check("reveal", "empty submissions do not unlock the solution", not ok, ""))
    return checks


def fallback_checks(exercises) -> list[Check]:
    e = exercises[0]
    broken = Retriever([Document("x#broken", "knowledge", "Letter case", "case sensitivity uppercase lowercase letters compare",
                                 fields={"pattern": "case_sensitivity", "hint1": "Look at {nonexistent}.", "hint2": "", "hint3": ""})])
    g = coach_submission(e, e.starter, [], retriever=broken)
    checks = [Check("fallback", "a broken hint template is replaced by a safe fallback", g.revised and "expected 5" in g.hint and g.confidence < 0.7, f"confidence {g.confidence}")]
    g = coach_submission(e, e.starter, [], retriever=Retriever([]))
    checks.append(Check("fallback", "an empty knowledge base still gives a safe hint", g.revised and "expected 5" in g.hint, g.hint))
    wrong_note = Retriever([Document("x#other", "knowledge", "Off by one", "uppercase lowercase letters compare case",
                                     fields={"pattern": "off_by_one", "hint1": "Count the loop passes.", "hint2": "x", "hint3": "y"})])
    g = coach_submission(e, e.starter, [], retriever=wrong_note)
    checks.append(Check("fallback", "a note that does not match the diagnosis is not used", g.revised and "loop passes" not in g.hint, g.hint))
    return checks


def progress_checks(exercises) -> list[Check]:
    e = exercises[0]
    better = coach_submission(e, e.solution, [Attempt(3, 6, "case_sensitivity", "count_vowels")])
    worse = coach_submission(e, e.starter, [Attempt(5, 6, "wrong_value", "count_vowels")])
    return [
        Check("progress", "more passing tests is reported as progress", better.progress.startswith("Progress"), better.progress),
        Check("progress", "fewer passing tests is reported as a regression", worse.progress.startswith("Regression"), worse.progress),
    ]


def baseline_comparison(exercises, outputs) -> dict:
    """Compare the coach's hints with a plain test report (what a student sees without the coach)."""
    baseline, by_level = [], {1: [], 2: [], 3: []}
    for e in exercises:
        history = []
        for level in (1, 2, 3):
            g = coach_submission(e, e.starter, history)
            history.append(g.attempt)
            by_level[level].append(g)
            if level == 1:
                first = g.diagnosis.focus
                text = f"{len(g.run.failing)} of {g.total} tests failed. {first.name}: expected {first.expected}, got {first.actual}."
                baseline.append((text, g))

    def stats(items):
        texts = [t for t, _ in items]
        def places(text, g):
            d = g.diagnosis
            return bool((d.function and d.function in text) or (d.line and f"line {d.line}" in text))
        return {
            "avg_words": statistics.mean(len(t.split()) for t in texts),
            "pct_question": 100 * sum("?" in t for t in texts) / len(texts),
            "pct_place": 100 * sum(places(t, g) for t, g in items) / len(items),
            "pct_cites_test": 100 * sum(bool(g.diagnosis.focus and g.diagnosis.focus.expr in t) for t, g in items) / len(items),
        }

    rows = {"Plain test report": stats(baseline)}
    for level in (1, 2, 3):
        rows[f"Coach hint level {level}"] = stats([(g.hint, g) for g in by_level[level]])
    return rows


def run_all() -> dict:
    exercises = list_exercises()
    diag, outputs = diagnosis_checks(exercises)
    checks = (exercise_checks(exercises) + diag + retrieval_checks() + escalation_checks(exercises)
              + leak_checks(exercises, outputs) + sandbox_checks(exercises) + reveal_checks(exercises)
              + fallback_checks(exercises) + progress_checks(exercises))
    confidences = [g.confidence for _, _, _, g in outputs if not g.solved]
    return {"checks": checks, "baseline": baseline_comparison(exercises, outputs),
            "confidence": (statistics.mean(confidences), min(confidences), len(confidences)),
            "exercise_count": len(exercises), "attempt_count": len(outputs)}


def format_report(result: dict, summary: bool = False) -> str:
    lines = ["DEBUG COACH EVALUATION", "=" * 70]
    group = None
    if summary:
        lines.append("")
        for name in dict.fromkeys(c.group for c in result["checks"]):
            members = [c for c in result["checks"] if c.group == name]
            lines.append(f"  {name:<12} {sum(c.passed for c in members)}/{len(members)} passed")
            lines += [f"    FAIL  {c.name}  ({c.detail})" for c in members if not c.passed]
    else:
        for check in result["checks"]:
            if check.group != group:
                group = check.group
                lines.append(f"\n[{group}]")
            lines.append(f"  {'PASS' if check.passed else 'FAIL'}  {check.name}" + (f"  ({check.detail})" if check.detail else ""))
    lines += ["", f"HINT STYLE: plain test report vs coach, {result['exercise_count']} exercises", "-" * 70,
              f"{'':<20}{'avg words':>10}{'asks a question':>17}{'names function/line':>21}{'quotes a test input':>21}"]
    for name, s in result["baseline"].items():
        lines.append(f"{name:<20}{s['avg_words']:>10.1f}{s['pct_question']:>16.0f}%{s['pct_place']:>20.0f}%{s['pct_cites_test']:>20.0f}%")
    mean, low, n = result["confidence"]
    lines += ["", f"CONFIDENCE over {n} failing scripted attempts: average {mean:.2f}, lowest {low:.2f}"]
    passed = sum(c.passed for c in result["checks"])
    lines += ["", "=" * 70, f"RESULT: {passed}/{len(result['checks'])} checks passed"]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-write", action="store_true", help="do not write logs/debug_eval_report.txt")
    parser.add_argument("--summary", action="store_true", help="print one line per group instead of every check")
    args = parser.parse_args(argv)
    result = run_all()
    print(format_report(result, summary=args.summary))
    if not args.no_write:
        REPORT_PATH.parent.mkdir(exist_ok=True)
        REPORT_PATH.write_text(format_report(result) + "\n", encoding="utf-8")
    return 0 if all(c.passed for c in result["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
