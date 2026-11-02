"""
tests/test_core_prompt.py — Contract tests for core/prompt.txt.

The prompt is hand-edited, so these pin the things that silently break ALFRED
when they drift:

- every {token} main.py fills in is still present;
- every tool the prompt tells the model to call is a tool ALFRED declares
  (the old prompt named shutdown_jarvis and screen_capture, neither of which
  the model could see);
- "# " editor notes are stripped before the prompt is sent;
- no mandatory screenshot after every action, and no hardcoded folder for the
  source-code restriction (main.py injects that, from one place);
- the persona defers to the configured [IDENTITY] form of address.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT_PATH = ROOT / "core" / "prompt.txt"

# Words in the prompt that look like snake_case tool names but are arguments,
# action values or memory keys rather than tools.
_NOT_TOOLS = {
    "assistant_name", "briefing_preference", "drill_sergeant", "duration_minutes",
    "is_relative", "lock_tab", "locus_confirmed", "mute_mic", "unmute_mic",
    "query_time", "seek_s", "start_s", "toggle_wifi",
}


def _declared_tool_names() -> set[str]:
    names: set[str] = set()
    sources = [ROOT / "main.py", *ROOT.glob("actions/*.py"), *ROOT.glob("plugins/**/*.py")]
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="ignore")
        names.update(re.findall(r'"name"\s*:\s*"([a-z][a-z0-9_]*)"', text))
    return names


def _render(template: str) -> str:
    from main import _render_prompt
    return _render_prompt(template, {
        "assistant_name": "ALFRED",
        "platform": "Windows 11",
        "capabilities": "- (capabilities)",
        "limits": "- (limits)",
    })


class TestCorePrompt(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = PROMPT_PATH.read_text(encoding="utf-8")
        cls.body = "\n".join(
            l for l in cls.raw.splitlines() if not (l.startswith("# ") or l == "#")
        )

    def test_tokens_present(self):
        for tok in ("{assistant_name}", "{platform}", "{capabilities}", "{limits}"):
            self.assertIn(tok, self.body, f"{tok} missing from prompt.txt")

    def test_every_called_tool_is_declared(self):
        declared = _declared_tool_names()
        self.assertIn("shutdown_alfred", declared)  # sanity: scanner works
        mentioned = set(re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", self.body)) - _NOT_TOOLS
        missing = sorted(n for n in mentioned if n not in declared)
        self.assertFalse(missing, f"prompt.txt names tools ALFRED does not declare: {missing}")

    def test_dead_tool_names_gone(self):
        for dead in ("shutdown_jarvis", "screen_capture"):
            self.assertNotIn(dead, self.body)

    def test_no_mandatory_screenshot_after_actions(self):
        self.assertNotRegex(self.body.lower(), r"after (completing )?any file or system action")

    def test_restriction_path_not_duplicated_here(self):
        # main.py injects the source-code restriction; a second, stale copy of
        # the path in prompt.txt is how the two drifted apart before.
        self.assertNotIn("Personal-Assistant", self.body)

    def test_persona_defers_to_identity(self):
        self.assertIn("follow the ADDRESS line in [IDENTITY]", self.body)

    def test_editor_notes_are_stripped_when_rendered(self):
        rendered = _render(self.raw)
        self.assertNotIn("Editor notes", rendered)
        self.assertFalse(any(l.startswith("# ") for l in rendered.splitlines()))
        self.assertIn("You are ALFRED", rendered)
        self.assertNotIn("{assistant_name}", rendered)

    def test_render_keeps_stray_braces(self):
        self.assertEqual(_render("keep {this} as is"), "keep {this} as is")


if __name__ == "__main__":
    unittest.main()
