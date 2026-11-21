from debug_coach.editor import EDITOR_JS, number_lines


def test_number_lines_numbers_every_line_and_aligns():
    out = number_lines("a\nb\n" + "\n".join("x" for _ in range(8))).split("\n")
    assert out[0] == " 1 | a"
    assert out[9] == "10 | x"
    assert len(out) == 10


def test_number_lines_keeps_indentation_and_blank_lines():
    assert number_lines("def f():\n    return 1\n") == "1 | def f():\n2 |     return 1\n3 | "


def test_editor_script_targets_the_code_box_and_keeps_ctrl_enter():
    assert 'aria-label="Your code"' in EDITOR_JS
    assert "ctrlKey" in EDITOR_JS and "Tab" in EDITOR_JS
