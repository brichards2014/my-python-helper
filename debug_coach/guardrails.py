"""Checks run on every piece of guidance before the student sees it."""
from __future__ import annotations

MAX_HINT_WORDS = 70
MIN_LINE_LENGTH = 12
MAX_SOURCE_CHARS = 20_000
REVEAL_AFTER_FAILED_ATTEMPTS = 3


def normalize(text: str) -> str:
    return " ".join(text.split())


def solution_only_lines(solution: str, starter: str) -> list[str]:
    """Lines of the reference solution that the starter does not already contain."""
    starter_lines = {normalize(line) for line in starter.splitlines()}
    lines = []
    for raw in solution.splitlines():
        line = normalize(raw)
        if len(line) >= MIN_LINE_LENGTH and line not in starter_lines and not line.startswith("#"):
            lines.append(line)
    return lines


def leaked_lines(text: str, solution: str, starter: str) -> list[str]:
    """Return the solution-only lines that appear inside text."""
    flat = normalize(text)
    return [line for line in solution_only_lines(solution, starter) if line in flat]


def check_hint(text: str, solution: str, starter: str) -> dict[str, bool]:
    """Each key is a check name. Each value is True when the check passed."""
    return {
        "has_text": bool(text.strip()),
        "within_word_limit": len(text.split()) <= MAX_HINT_WORDS,
        "no_unfilled_template": "{" not in text and "}" not in text,
        "no_solution_leak": not leaked_lines(text, solution, starter),
    }


def can_reveal(failed_attempts: int) -> bool:
    return failed_attempts >= REVEAL_AFTER_FAILED_ATTEMPTS
