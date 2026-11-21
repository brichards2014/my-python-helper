"""Small helpers for the Debug Coach page: line numbers and Tab or Enter handling in the code box."""
from __future__ import annotations


def number_lines(source: str) -> str:
    """Return the source with a line number in front of each line, so hints that say 'line 3' are easy to follow."""
    lines = source.split("\n")
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, start=1))


# Runs once in a zero-height frame and attaches to the "Your code" box in the page.
# Tab inserts 4 spaces (Shift+Tab removes them), Enter keeps the indent and adds 4 after a colon.
# Ctrl+Enter is left alone so Streamlit can submit the form.
EDITOR_JS = """
<script>
(function () {
  const doc = window.parent.document;
  const Win = window.parent;
  const INDENT = "    ";
  function setValue(ta, value, start, end) {
    const setter = Object.getOwnPropertyDescriptor(Win.HTMLTextAreaElement.prototype, "value").set;
    setter.call(ta, value);
    ta.selectionStart = start;
    ta.selectionEnd = end;
    ta.dispatchEvent(new Win.Event("input", { bubbles: true }));
  }
  function onKey(e) {
    const ta = e.target;
    const v = ta.value, s = ta.selectionStart, end = ta.selectionEnd;
    if (e.key === "Tab") {
      e.preventDefault();
      const lineStart = v.lastIndexOf("\\n", s - 1) + 1;
      if (e.shiftKey || v.slice(s, end).includes("\\n")) {
        const block = v.slice(lineStart, end).split("\\n");
        const out = block.map(l => e.shiftKey ? (l.startsWith(INDENT) ? l.slice(4) : l.replace(/^ {1,3}/, "")) : INDENT + l);
        const text = out.join("\\n");
        const delta = text.length - (end - lineStart);
        const first = out[0].length - block[0].length;
        setValue(ta, v.slice(0, lineStart) + text + v.slice(end), Math.max(lineStart, s + first), end + delta);
      } else {
        setValue(ta, v.slice(0, s) + INDENT + v.slice(end), s + 4, s + 4);
      }
    } else if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      const lineStart = v.lastIndexOf("\\n", s - 1) + 1;
      const line = v.slice(lineStart, s);
      let pad = line.match(/^ */)[0];
      if (line.trimEnd().endsWith(":")) pad += INDENT;
      setValue(ta, v.slice(0, s) + "\\n" + pad + v.slice(end), s + 1 + pad.length, s + 1 + pad.length);
    }
  }
  function attach() {
    doc.querySelectorAll('textarea[aria-label="Your code"]').forEach(ta => {
      if (ta.dataset.coachEditor) return;
      ta.dataset.coachEditor = "1";
      ta.addEventListener("keydown", onKey, true);
      ta.setAttribute("spellcheck", "false");
      ta.style.fontFamily = "monospace";
    });
  }
  attach();
  new Win.MutationObserver(attach).observe(doc.body, { childList: true, subtree: true });
})();
</script>
"""
