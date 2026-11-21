"""Load exercises from the exercises/ folder."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXERCISES_DIR = ROOT / "exercises"
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    difficulty: str
    description: str
    bug_tag: str
    origin: str
    sources: tuple
    cases: tuple
    starter: str
    solution: str = field(repr=False)


def load_exercise(exercise_id: str, directory: Path = EXERCISES_DIR) -> Exercise:
    folder = Path(directory) / exercise_id
    meta = json.loads((folder / "exercise.json").read_text(encoding="utf-8"))
    return Exercise(
        id=meta["id"],
        title=meta["title"],
        difficulty=meta["difficulty"],
        description=meta["description"],
        bug_tag=meta["bug_tag"],
        origin=meta["origin"],
        sources=tuple(meta.get("sources", [])),
        cases=tuple(meta["cases"]),
        starter=(folder / "starter.py").read_text(encoding="utf-8"),
        solution=(folder / "solution.py").read_text(encoding="utf-8"),
    )


def list_exercises(directory: Path = EXERCISES_DIR) -> list[Exercise]:
    found = [load_exercise(p.name, directory) for p in Path(directory).iterdir() if (p / "exercise.json").exists()]
    return sorted(found, key=lambda e: (DIFFICULTY_ORDER.get(e.difficulty, 9), e.id))
