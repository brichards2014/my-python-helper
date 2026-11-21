"""Run a submission against an exercise's test cases in a separate process.

Guardrails: a static check blocks risky imports and builtins, the run has a time limit,
output is captured and truncated, and the submission cannot crash the coach.

This is a safety net for student code, not a security boundary. Only run code you wrote
or trust.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 200_000

BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "ctypes", "importlib", "pathlib", "requests",
    "urllib", "http", "pickle", "multiprocessing", "threading", "signal", "builtins", "tempfile", "glob",
}
BLOCKED_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals"}

RUNNER = r'''
import json, runpy, sys, io, contextlib, traceback

try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
except Exception:
    pass

submission, cases_path = sys.argv[1], sys.argv[2]
cases = json.load(open(cases_path, encoding="utf-8"))
real_stdout = sys.stdout


def clean(value):
    return json.loads(json.dumps(value, default=lambda o: list(o) if isinstance(o, (set, frozenset, tuple)) else repr(o)))


results = []
status, message, line = "ok", "", None
sink = io.StringIO()
with contextlib.redirect_stdout(sink):
    try:
        runpy.run_path(submission)
    except BaseException as error:
        status, message = "load_error", f"{type(error).__name__}: {error}"
        tb = traceback.extract_tb(error.__traceback__)
        line = next((f.lineno for f in reversed(tb) if f.filename.endswith("submission.py")), None)
    if status == "ok":
        for case in cases:
            entry = {"name": case["name"], "passed": False, "error_type": None, "error_message": None, "actual": None, "line": None}
            try:
                namespace = runpy.run_path(submission)
                for step in case.get("steps", []):
                    exec(step, namespace)
                actual = clean(eval(case["expr"], namespace))
                entry["actual"] = actual
                entry["passed"] = actual == case["expect"]
            except BaseException as error:
                entry["error_type"] = type(error).__name__
                entry["error_message"] = str(error)[:200]
                tb = traceback.extract_tb(error.__traceback__)
                entry["line"] = next((f.lineno for f in reversed(tb) if f.filename.endswith("submission.py")), None)
            results.append(entry)

real_stdout.write("\n@@RESULT@@" + json.dumps({"status": status, "message": message, "line": line, "cases": results, "stdout": sink.getvalue()[:500]}))
'''


@dataclass
class CaseResult:
    name: str
    passed: bool
    expr: str
    expected: object
    actual: object = None
    error_type: str | None = None
    error_message: str | None = None
    line: int | None = None
    hidden: bool = False


@dataclass
class RunResult:
    status: str  # ok, syntax_error, blocked, timeout, load_error, crash
    message: str = ""
    line: int | None = None
    cases: list = field(default_factory=list)
    stdout: str = ""

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(c.passed for c in self.cases)

    @property
    def failing(self) -> list:
        return [c for c in self.cases if not c.passed]

    @property
    def all_passed(self) -> bool:
        return self.status == "ok" and bool(self.cases) and self.passed == self.total


def check_source(source: str) -> RunResult | None:
    """Return a failing RunResult if the source cannot be run, otherwise None."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return RunResult("syntax_error", f"{error.msg}", error.lineno)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [(node.module or "").split(".")[0]]
        else:
            modules = []
        for module in modules:
            if module in BLOCKED_IMPORTS:
                return RunResult("blocked", f"import of '{module}' is not allowed in exercises", node.lineno)
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            return RunResult("blocked", f"'{node.id}' is not allowed in exercises", node.lineno)
    return None


def run_submission(source: str, cases, timeout: int | None = None) -> RunResult:
    """Run source against cases. Never raises."""
    timeout = timeout or TIMEOUT_SECONDS
    blocked = check_source(source)
    if blocked is not None:
        return blocked
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        (folder / "submission.py").write_text(source, encoding="utf-8")
        (folder / "runner.py").write_text(RUNNER, encoding="utf-8")
        (folder / "cases.json").write_text(json.dumps(list(cases)), encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-I", "runner.py", "submission.py", "cases.json"],
                cwd=folder, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return RunResult("timeout", f"the code ran longer than {timeout} seconds (possible infinite loop)")
        except OSError as error:
            return RunResult("crash", f"could not start the test runner: {error}")
    output = (done.stdout or "")[:MAX_OUTPUT_CHARS]
    if "@@RESULT@@" not in output:
        detail = (done.stderr or "").strip().splitlines()[-1:] or ["no result"]
        return RunResult("crash", f"the test runner stopped early ({detail[0][:120]})")
    try:
        data = json.loads(output.split("@@RESULT@@", 1)[1])
    except json.JSONDecodeError:
        return RunResult("crash", "the test runner returned unreadable output")
    results = []
    for case, entry in zip(cases, data["cases"]):
        hidden = bool(case.get("hidden"))
        results.append(CaseResult(
            name=case["name"], passed=entry["passed"],
            expr="a hidden test" if hidden else case["expr"],
            expected="(hidden)" if hidden else case["expect"],
            actual="(hidden)" if hidden else entry["actual"],
            error_type=entry["error_type"], error_message=entry["error_message"],
            line=entry["line"], hidden=hidden,
        ))
    return RunResult(data["status"], data["message"], data["line"], results, data["stdout"])
