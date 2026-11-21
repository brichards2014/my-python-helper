"""Scripted student attempts. The demo shows them and the evaluation harness checks them.

Each entry is (label, source, expected_tag). The expected tag is what a person would say
the attempt got wrong, written before running the coach. "solved" means all tests pass.
"""
from __future__ import annotations

from debug_coach.exercises import Exercise, list_exercises

REMOVE_NEGATIVES_NEW_LIST = '''def remove_negatives(nums):
    """Remove every negative number from nums in place and return nums."""
    return [n for n in nums if n >= 0]
'''

MULTIPLIERS_HELPER = '''def make_multipliers(n):
    """Return a list of n functions. The function at index i multiplies its argument by i."""
    def make(i):
        return lambda x: x * i
    return [make(i) for i in range(n)]
'''


def scripts_for(exercise: Exercise) -> list[tuple[str, str, str]]:
    start, solution = exercise.starter, exercise.solution
    table = {
        "easy_1_count_vowels": [
            ("starter code", start, "case_sensitivity"),
            ("same code again", start, "case_sensitivity"),
            ("forgot the letter u", solution.replace('"aeiou"', '"aeio"'), "wrong_value"),
            ("correct fix", solution, "solved"),
        ],
        "easy_2_sum_first_n": [
            ("starter code", start, "off_by_one"),
            ("range(n + 1)", solution.replace("range(n)", "range(n + 1)"), "wrong_value"),
            ("correct fix", solution, "solved"),
        ],
        "medium_1_add_item": [
            ("starter code", start, "mutable_default"),
            ("None default without creating a list", start.replace("items=[]", "items=None"), "runtime_error"),
            ("correct fix", solution, "solved"),
        ],
        "medium_2_remove_negatives": [
            ("starter code", start, "modify_while_iterating"),
            ("returns a new list instead of changing nums", REMOVE_NEGATIVES_NEW_LIST, "wrong_value"),
            ("correct fix", solution, "solved"),
        ],
        "hard_1_make_multipliers": [
            ("starter code", start, "late_binding"),
            ("different correct fix (helper function)", MULTIPLIERS_HELPER, "solved"),
        ],
        "hard_2_game_logic": [
            ("starter code", start, "inverted_condition"),
            ("fixed check_guess only", start.replace('"Go HIGHER!"\n    return "Too Low", "Go LOWER!"', '"Go LOWER!"\n    return "Too Low", "Go HIGHER!"'), "wrong_value"),
            ("also fixed the ranges", start.replace('"Go HIGHER!"\n    return "Too Low", "Go LOWER!"', '"Go LOWER!"\n    return "Too Low", "Go HIGHER!"').replace("return 1, 100\n    if difficulty == \"Hard\":\n        return 1, 50", "return 1, 50\n    if difficulty == \"Hard\":\n        return 1, 100"), "wrong_value"),
            ("correct fix", solution, "solved"),
        ],
    }
    return table[exercise.id]


def all_scripts() -> dict:
    return {e.id: scripts_for(e) for e in list_exercises()}
