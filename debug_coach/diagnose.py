"""Work out the most likely bug from a submission and its test results.

Static checks read the code with the ast module. Dynamic checks read which tests failed.
The first rule that matches wins. These are heuristics: each result carries a confidence.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from debug_coach.sandbox import CaseResult, RunResult

TAGS = (
    "syntax_error", "blocked_code", "infinite_loop", "load_error", "runtime_error",
    "mutable_default", "modify_while_iterating", "late_binding", "off_by_one",
    "inverted_condition", "case_sensitivity", "wrong_value",
)

OPPOSITE_WORDS = [("HIGHER", "LOWER"), ("TOO HIGH", "TOO LOW"), ("TRUE", "FALSE"), ("YES", "NO"), ("INCREASE", "DECREASE")]
MUTATING_METHODS = {"remove", "pop", "insert", "append", "extend", "clear"}
CASE_FIXES = (".lower(", ".upper(", ".casefold(", "re.I", "IGNORECASE")


@dataclass
class Diagnosis:
    tag: str
    confidence: float
    line: int | None = None
    function: str | None = None
    evidence: str = ""
    focus: CaseResult | None = None


def _parents(tree: ast.AST) -> dict:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _enclosing_function(node: ast.AST, parents: dict) -> str | None:
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return None


def _find_mutable_default(tree, parents):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
            for default in defaults:
                literal = isinstance(default, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp))
                call = isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id in {"list", "dict", "set"}
                if literal or call:
                    return default.lineno, getattr(node, "name", None)
    return None


def _find_modify_while_iterating(tree, parents):
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            name = node.iter.id
            for statement in node.body:
                for inner in ast.walk(statement):
                    if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                            and isinstance(inner.func.value, ast.Name) and inner.func.value.id == name
                            and inner.func.attr in MUTATING_METHODS):
                        return inner.lineno, _enclosing_function(node, parents)
                    if isinstance(inner, ast.Delete) and any(
                            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == name
                            for t in inner.targets):
                        return inner.lineno, _enclosing_function(node, parents)
    return None


def _lambda_or_def_params(node) -> set:
    args = node.args
    names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    names |= {a.arg for a in (args.vararg, args.kwarg) if a}
    return names


def _uses_unbound_loop_variable(container, targets: set) -> int | None:
    for sub in ast.walk(container):
        if isinstance(sub, (ast.Lambda, ast.FunctionDef)):
            used = {n.id for n in ast.walk(sub) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            if (used & targets) - _lambda_or_def_params(sub):
                return sub.lineno
    return None


def _find_late_binding(tree, parents):
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            targets = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
            for statement in node.body:
                line = _uses_unbound_loop_variable(statement, targets)
                if line:
                    return line, _enclosing_function(node, parents)
        if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
            targets = {n.id for g in node.generators for n in ast.walk(g.target) if isinstance(n, ast.Name)}
            line = _uses_unbound_loop_variable(node.elt, targets)
            if line:
                return line, _enclosing_function(node, parents)
    return None


def _minus_one(node) -> bool:
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and isinstance(node.right, ast.Constant) and node.right.value == 1


def _find_off_by_one(tree, parents):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            if any(_minus_one(arg) for arg in node.args):
                return node.lineno, _enclosing_function(node, parents)
        if isinstance(node, ast.Slice) and node.upper is not None and _minus_one(node.upper):
            return node.lineno, _enclosing_function(node, parents)
    return None


def _opposite(expected, actual) -> bool:
    if isinstance(expected, bool) and isinstance(actual, bool):
        return expected != actual
    if isinstance(expected, str) and isinstance(actual, str):
        e, a = expected.upper(), actual.upper()
        return any(
            (x in e and y in a and y not in e and x not in a) or (y in e and x in a and x not in e and y not in a)
            for x, y in OPPOSITE_WORDS
        )
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return any(_opposite(e, a) for e, a in zip(expected, actual))
    return False


def _has_uppercase_text(expr: str) -> bool:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and any(c.isupper() for c in n.value) for n in ast.walk(tree))


def _function_for(case: CaseResult | None, tree) -> tuple[str | None, int | None]:
    """Find which function the test calls, among the functions the submission defines."""
    if case is None or tree is None:
        return None, None
    defined = {n.name: n.lineno for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in re.findall(r"([A-Za-z_]\w*)\(", case.expr):
        if name in defined:
            return name, defined[name]
    return None, None


def diagnose(source: str, run: RunResult) -> Diagnosis:
    if run.status == "syntax_error":
        return Diagnosis("syntax_error", 1.0, run.line, evidence=run.message)
    if run.status == "blocked":
        return Diagnosis("blocked_code", 1.0, run.line, evidence=run.message)
    if run.status == "timeout":
        return Diagnosis("infinite_loop", 0.8, evidence=run.message)
    if run.status == "crash":
        return Diagnosis("load_error", 0.5, evidence=run.message)
    if run.status == "load_error":
        return Diagnosis("load_error", 0.85, run.line, evidence=run.message)
    if run.all_passed:
        return Diagnosis("solved", 1.0)

    tree = ast.parse(source)
    parents = _parents(tree)
    failing = run.failing
    focus = next((c for c in failing if not c.hidden), failing[0])
    function, function_line = _function_for(focus, tree)

    for tag, finder in (
        ("mutable_default", _find_mutable_default),
        ("modify_while_iterating", _find_modify_while_iterating),
        ("late_binding", _find_late_binding),
        ("off_by_one", _find_off_by_one),
    ):
        found = finder(tree, parents)
        if found:
            line, name = found
            return Diagnosis(tag, 0.9, line, name or function, f"pattern found at line {line}", focus)

    errors = [c for c in failing if c.error_type]
    if errors and len(errors) == len(failing):
        first = errors[0]
        return Diagnosis("runtime_error", 0.85, first.line, function, f"{first.error_type}: {first.error_message}", first)

    if any(not c.hidden and _opposite(c.expected, c.actual) for c in failing):
        case = next(c for c in failing if not c.hidden and _opposite(c.expected, c.actual))
        name, line = _function_for(case, tree)
        return Diagnosis("inverted_condition", 0.75, line, name, "a result is the opposite of the expected one", case)

    visible_failing = [c for c in failing if not c.hidden]
    visible_passing = [c for c in run.cases if c.passed and not c.hidden]
    # Letter case is blamed only when uppercase text separates the failing tests from the passing ones.
    if (visible_failing
            and all(_has_uppercase_text(c.expr) for c in visible_failing)
            and not any(_has_uppercase_text(c.expr) for c in visible_passing)
            and not any(marker in source for marker in CASE_FIXES)):
        case = visible_failing[0]
        name, line = _function_for(case, tree)
        return Diagnosis("case_sensitivity", 0.7, line, name, "failing input has uppercase letters and the code never changes case", case)

    return Diagnosis("wrong_value", 0.4, function_line, function, "results differ from the expected values", focus)
