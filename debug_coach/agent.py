"""Debug Coach agent.

Each submission goes through a fixed loop and every step is recorded in a trace:

    validate -> run tests -> diagnose -> plan -> retrieve -> compose -> check -> (revise) -> score

The coach gives tiered hints. The first failure of a kind gets a nudge. The same kind of
failure again gets a pinpoint, then a description of the technique. Hints never contain the
reference solution, and the solution is shown only on request after repeated failures.
"""
from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from pathlib import Path

from coach.log import get_logger
from coach.retriever import Retriever, load_knowledge, load_references
from debug_coach import guardrails
from debug_coach.diagnose import Diagnosis, diagnose
from debug_coach.exercises import Exercise
from debug_coach.sandbox import RunResult, run_submission

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge" / "debugging"
REFERENCES_PATH = ROOT / "data" / "public_references.json"

TAG_QUERIES = {
    "syntax_error": "syntax error invalid code colon bracket",
    "blocked_code": "blocked import not allowed",
    "infinite_loop": "loop never ends too long",
    "load_error": "error before tests run at load time",
    "runtime_error": "exception crashed error raised",
    "mutable_default": "default argument list shared between calls remembers earlier call",
    "modify_while_iterating": "removing items from list while looping skipped items",
    "late_binding": "lambda functions created in a loop all return same result",
    "off_by_one": "loop stops one early range stop value",
    "inverted_condition": "result is the opposite reversed comparison",
    "case_sensitivity": "uppercase lowercase letters compare",
    "wrong_value": "wrong result differs expected value",
}

RELEVANCE_REFERENCE = 0.35
BASE_CONFIDENCE = 0.3

_retriever: Retriever | None = None


def build_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever(load_knowledge(KNOWLEDGE_DIR) + load_references(REFERENCES_PATH))
    return _retriever


@dataclass(frozen=True)
class Attempt:
    """One earlier submission, kept so the coach can escalate hints and show progress."""
    passed: int
    total: int
    tag: str
    function: str | None = None


@dataclass
class Guidance:
    exercise_id: str
    solved: bool
    tag: str
    level: int
    hint: str
    passed: int
    total: int
    confidence: float
    progress: str = ""
    references: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    revised: bool = False
    trace: list = field(default_factory=list)
    run: RunResult | None = None
    diagnosis: Diagnosis | None = None

    @property
    def attempt(self) -> Attempt:
        return Attempt(self.passed, self.total, self.tag, self.diagnosis.function if self.diagnosis else None)

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id, "solved": self.solved, "tag": self.tag, "level": self.level,
            "hint": self.hint, "passed": self.passed, "total": self.total, "confidence": self.confidence,
            "progress": self.progress, "references": self.references, "sources": self.sources,
            "checks": self.checks, "revised": self.revised, "trace": self.trace,
        }


def _show(value, limit: int = 40) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _level(history, tag: str, function: str | None) -> int:
    """Escalate while the same kind of failure repeats in the same function. A new problem starts at level 1."""
    streak = 0
    for attempt in reversed(list(history)):
        if attempt.tag != tag or attempt.function != function:
            break
        streak += 1
    return min(3, streak + 1)


def _progress(history, passed: int, total: int) -> str:
    if not history:
        return ""
    before = history[-1]
    if before.total == total and passed > before.passed:
        return f"Progress: {passed} of {total} tests pass, up from {before.passed}."
    if before.total == total and passed < before.passed:
        return f"Regression: {passed} of {total} tests pass, down from {before.passed}. Your last change broke something that worked."
    return ""


def _fallback_hint(focus, failed: int, total: int) -> str:
    if focus is None or focus.hidden:
        return f"{failed} of {total} tests fail, including a hidden one. Check edge cases such as empty input, zero, and the largest allowed value."
    return (f"{failed} of {total} tests fail. Start with `{focus.expr}`: expected {_show(focus.expected)}, "
            f"got {_show(focus.actual)}. Work through that input by hand.")


def _terminal(exercise: Exercise, tag: str, hint: str, trace: list) -> Guidance:
    trace.append({"step": "stop", "tag": tag})
    return Guidance(exercise.id, False, tag, 1, hint, 0, len(exercise.cases), 0.0, trace=trace)


def coach_submission(exercise: Exercise, source: str, history=(), retriever: Retriever | None = None) -> Guidance:
    """Run the student's code and return guidance. This function never raises on bad input."""
    log = get_logger()
    trace: list[dict] = []
    history = list(history)

    if not isinstance(source, str) or not source.strip():
        trace.append({"step": "validate", "ok": False})
        return _terminal(exercise, "invalid_input", "The submission is empty. Write your fix and run it again.", trace)
    if len(source) > guardrails.MAX_SOURCE_CHARS:
        trace.append({"step": "validate", "ok": False})
        return _terminal(exercise, "invalid_input", "The submission is too long for this exercise. Keep only the function you are fixing.", trace)
    trace.append({"step": "validate", "ok": True, "unchanged": guardrails.normalize(source) == guardrails.normalize(exercise.starter)})

    run = run_submission(source, exercise.cases)
    trace.append({"step": "run", "status": run.status, "passed": run.passed, "total": run.total or len(exercise.cases)})

    diagnosis = diagnose(source, run)
    trace.append({"step": "diagnose", "tag": diagnosis.tag, "confidence": diagnosis.confidence,
                  "line": diagnosis.line, "evidence": diagnosis.evidence})

    retriever = retriever or build_retriever()
    total = run.total or len(exercise.cases)

    if diagnosis.tag == "solved":
        lesson_hits = retriever.search(TAG_QUERIES[exercise.bug_tag], k=1, source="knowledge")
        lesson = lesson_hits[0].doc.fields.get("lesson", "") if lesson_hits else ""
        hint = f"All {total} tests pass. {lesson}".strip()
        trace.append({"step": "solved", "lesson_from": lesson_hits[0].doc.doc_id if lesson_hits else None})
        log.info("exercise=%s solved after %d earlier attempts", exercise.id, len(history))
        return Guidance(exercise.id, True, "solved", 1, hint, run.passed, total, 1.0,
                        _progress(history, run.passed, total), [], [], {}, False, trace, run, diagnosis)

    level = _level(history, diagnosis.tag, diagnosis.function)
    query = TAG_QUERIES.get(diagnosis.tag, TAG_QUERIES["wrong_value"])
    plan_note = {"step": "plan", "level": level, "query": query}
    trace.append(plan_note)

    hits = retriever.search(query, k=3, source="knowledge")
    reference_hits = retriever.search(query, k=3, source="reference")
    trace.append({"step": "retrieve", "knowledge": [(h.doc.doc_id, h.score, h.relevance) for h in hits],
                  "reference": [(h.doc.doc_id, h.score) for h in reference_hits]})

    focus = diagnosis.focus
    failed = len(run.failing) if run.cases else total
    values = {
        "function": diagnosis.function or "your function",
        "where": f"line {diagnosis.line}" if diagnosis.line else "your code",
        "expr": focus.expr if focus else "a test",
        "expected": _show(focus.expected) if focus else "?",
        "actual": _show(focus.actual) if focus else "?",
        "failed": failed, "total": total,
        "error": diagnosis.evidence or run.message or "an error",
    }

    chosen = hits[0] if hits else None
    relevance = chosen.relevance if chosen else 0.0
    matches = bool(chosen) and chosen.doc.fields.get("pattern") == diagnosis.tag
    hint, sources, revised = "", [], False
    if matches:
        try:
            hint = string.Formatter().vformat(chosen.doc.fields[f"hint{level}"], (), values)
            sources.append(chosen.doc.doc_id)
        except (KeyError, IndexError, ValueError) as error:
            trace.append({"step": "compose", "error": f"template failed: {error}"})
    trace.append({"step": "compose", "used": chosen.doc.doc_id if matches else None, "hint": hint})

    checks = guardrails.check_hint(hint, exercise.solution, exercise.starter)
    checks["retrieval_matches_diagnosis"] = matches
    trace.append({"step": "check", "checks": checks})

    if not all(checks.values()):
        revised = True
        hint = _fallback_hint(focus, failed, total)
        sources, relevance = ["fallback"], 0.0
        checks = guardrails.check_hint(hint, exercise.solution, exercise.starter)
        checks["retrieval_matches_diagnosis"] = True
        trace.append({"step": "revise", "reason": "a check failed", "hint": hint, "checks": checks})
        log.warning("exercise=%s hint revised for tag %s", exercise.id, diagnosis.tag)

    references = []
    if level >= 2:  # references appear once the student has tried more than once
        for hit in reference_hits:
            if hit.doc.fields.get("pattern") != diagnosis.tag or len(references) == 2:
                continue
            if guardrails.leaked_lines(f"{hit.doc.fields['title']} {hit.doc.text}", exercise.solution, exercise.starter):
                continue
            references.append({"title": hit.doc.fields["title"], "url": hit.doc.fields["url"]})
            sources.append(hit.doc.doc_id)

    passed_checks = sum(checks.values()) / len(checks)
    confidence = round(passed_checks * (BASE_CONFIDENCE + 0.35 * min(1.0, relevance / RELEVANCE_REFERENCE)
                                        + 0.35 * diagnosis.confidence), 2)
    trace.append({"step": "confidence", "checks_passed": round(passed_checks, 2), "relevance": relevance,
                  "diagnosis_confidence": diagnosis.confidence, "confidence": confidence})
    log.info("exercise=%s tag=%s level=%d passed=%d/%d confidence=%s revised=%s",
             exercise.id, diagnosis.tag, level, run.passed, total, confidence, revised)

    return Guidance(exercise.id, False, diagnosis.tag, level, hint, run.passed, total, confidence,
                    _progress(history, run.passed, total), references, sources, checks, revised, trace, run, diagnosis)


def reveal_solution(exercise: Exercise, history) -> tuple[bool, str]:
    """Return the reference solution, but only after repeated failed attempts."""
    failed = sum(1 for attempt in history if attempt.tag not in ("solved", "invalid_input"))
    if not guardrails.can_reveal(failed):
        need = guardrails.REVEAL_AFTER_FAILED_ATTEMPTS - failed
        return False, f"Try {need} more time(s) before viewing the solution. Each run gives a new hint."
    return True, exercise.solution
