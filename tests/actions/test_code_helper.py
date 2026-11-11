"""Behavioural tests for actions.code_helper (Gemini and subprocess are mocked)."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.code_helper as ch
from actions.code_helper import code_helper


class _FakeModel:
    """Stands in for the object returned by _get_gemini()."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.prompts = []

    def generate_content(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.texts.pop(0))


@pytest.fixture(autouse=True)
def _desktop(tmp_path, monkeypatch):
    desk = tmp_path / "Desktop"
    monkeypatch.setattr(ch, "DESKTOP", desk)
    return desk


# ── pure helpers ──────────────────────────────────────────────────────────────

def test_clean_code_strips_markdown_fence():
    assert ch._clean_code("```python\nprint(1)\n```") == "print(1)"
    assert ch._clean_code("  x = 1  ") == "x = 1"


def test_resolve_save_path_uses_language_extension(_desktop):
    assert ch._resolve_save_path("", "JavaScript") == _desktop / "alfred_code.js"
    assert ch._resolve_save_path("", "unknown-lang") == _desktop / "alfred_code.py"
    assert ch._resolve_save_path("sub/x.rs", "rust") == _desktop / "sub" / "x.rs"


def test_resolve_save_path_keeps_absolute(tmp_path):
    target = tmp_path / "abs.py"
    assert ch._resolve_save_path(str(target), "python") == target


def test_read_file_errors_and_success(tmp_path):
    assert ch._read_file("") == ("", "No file path provided.")
    missing = tmp_path / "nope.py"
    assert ch._read_file(str(missing)) == ("", f"File not found: {missing}")
    f = tmp_path / "a.py"
    f.write_text("print('hi')", encoding="utf-8")
    assert ch._read_file(str(f)) == ("print('hi')", "")


def test_save_file_creates_parents(tmp_path):
    target = tmp_path / "deep" / "dir" / "f.txt"
    assert ch._save_file(target, "data") == f"Saved to: {target}"
    assert target.read_text(encoding="utf-8") == "data"


def test_preview_truncates_with_count():
    code = "\n".join(f"l{i}" for i in range(15))
    out = ch._preview(code, lines=10)
    assert out.splitlines()[:10] == [f"l{i}" for i in range(10)]
    assert out.endswith("... (5 more lines)")
    assert ch._preview("a\nb") == "a\nb"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Output:\nhello", False),
        ("Executed with no output.", False),
        ("Traceback (most recent call last)", True),
        ("Stderr:\nwarning", True),
        ("Build FAILED", True),
    ],
)
def test_has_error(text, expected):
    assert ch._has_error(text) is expected


# ── Gemini wrapper / intent detection ────────────────────────────────────────

def test_get_gemini_raises_when_ladder_fails():
    with patch.object(ch.gemini, "call", return_value=None):
        with pytest.raises(RuntimeError, match="ladder failed"):
            ch._get_gemini().generate_content("x")


def test_get_gemini_passes_tier_and_timeout():
    resp = SimpleNamespace(text="ok")
    with patch.object(ch.gemini, "call", return_value=resp) as call:
        assert ch._get_gemini("fast").generate_content("prompt") is resp
    call.assert_called_once_with("prompt", tier="fast", timeout_ms=60000)


def test_detect_intent_uses_model_answer():
    with patch.object(ch, "_get_gemini", return_value=_FakeModel("`Optimize`.")):
        assert ch._detect_intent("make it faster", "", "") == "optimize"


def test_detect_intent_ignores_invalid_answer_and_falls_back(tmp_path):
    existing = tmp_path / "f.py"
    existing.write_text("x=1", encoding="utf-8")
    with patch.object(ch, "_get_gemini", return_value=_FakeModel("banana")):
        assert ch._detect_intent("change it", str(existing), "") == "edit"


def test_detect_intent_structural_fallback_on_error(tmp_path):
    existing = tmp_path / "f.py"
    existing.write_text("x=1", encoding="utf-8")
    broken = MagicMock(side_effect=RuntimeError("offline"))
    with patch.object(ch, "_get_gemini", broken):
        assert ch._detect_intent("", str(existing), "") == "explain"
        assert ch._detect_intent("x", "", "print(1)") == "explain"
        assert ch._detect_intent("x", "", "") == "write"


# ── _run_file ────────────────────────────────────────────────────────────────

def test_run_file_unknown_extension(tmp_path):
    assert ch._run_file(tmp_path / "x.xyz", [], 5) == "No interpreter for .xyz."


def test_run_file_combines_stdout_and_stderr(tmp_path):
    script = tmp_path / "s.py"
    fake = SimpleNamespace(stdout="hi\n", stderr="warn\n")
    with patch.object(ch.subprocess, "run", return_value=fake) as run:
        out = ch._run_file(script, ["--flag"], 7)
    assert out == "Output:\nhi\n\nStderr:\nwarn"
    args, kwargs = run.call_args
    assert args[0] == [sys.executable, str(script), "--flag"]
    assert kwargs["timeout"] == 7 and kwargs["cwd"] == str(tmp_path)


def test_run_file_no_output(tmp_path):
    with patch.object(ch.subprocess, "run", return_value=SimpleNamespace(stdout="", stderr="")):
        assert ch._run_file(tmp_path / "s.py", None, 5) == "Executed with no output."


def test_run_file_timeout_and_missing_interpreter(tmp_path):
    with patch.object(ch.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 3)):
        assert ch._run_file(tmp_path / "s.js", [], 3) == "Timed out after 3s."
    with patch.object(ch.subprocess, "run", side_effect=FileNotFoundError()):
        assert ch._run_file(tmp_path / "s.js", [], 3) == "Interpreter not found: node."


# ── _build loop ──────────────────────────────────────────────────────────────

def test_build_requires_description():
    assert "describe" in ch._build("", "python", "", [], 5)


def test_build_succeeds_after_fix(_desktop):
    model = _FakeModel("print(undefined)", "print('ok')")
    outputs = iter(["Stderr:\nNameError: undefined", "Output:\nok"])
    speak = MagicMock()
    with patch.object(ch, "_get_gemini", return_value=model), \
         patch.object(ch, "_run_file", side_effect=lambda *a: next(outputs)):
        out = ch._build("print ok", "python", "", [], 5, speak=speak)
    assert "working after 2 attempts" in out
    saved = _desktop / "alfred_code.py"
    assert saved.read_text(encoding="utf-8") == "print('ok')"
    speak.assert_called_once()


def test_build_gives_up_after_max_attempts(_desktop):
    model = _FakeModel(*(["bad"] * (ch.MAX_BUILD_ATTEMPTS + 1)))
    with patch.object(ch, "_get_gemini", return_value=model), \
         patch.object(ch, "_run_file", return_value="Traceback: error"):
        out = ch._build("thing", "python", "", [], 5)
    assert f"after {ch.MAX_BUILD_ATTEMPTS} attempts" in out
    assert "Last code saved to:" in out


# ── code_helper dispatch ─────────────────────────────────────────────────────

def test_unknown_action():
    assert code_helper({"action": "teleport"}).startswith("Unknown action: 'teleport'")


def test_write_action_saves_and_previews(_desktop):
    with patch.object(ch, "_get_gemini", return_value=_FakeModel("```python\nx = 1\n```")):
        out = code_helper({"action": "write", "description": "set x", "language": "python"})
    assert out.startswith(f"Code written. Saved to: {_desktop / 'alfred_code.py'}")
    assert out.endswith("x = 1")


def test_write_action_requires_description():
    assert "describe" in code_helper({"action": "write"})


def test_edit_action_validations(tmp_path):
    assert code_helper({"action": "edit"}) == "Please provide a file path to edit, sir."
    f = tmp_path / "e.py"
    f.write_text("a = 1", encoding="utf-8")
    assert code_helper({"action": "edit", "file_path": str(f)}) == (
        "Please describe what change to make, sir."
    )


def test_edit_action_writes_back_using_instruction_param(tmp_path):
    f = tmp_path / "e.py"
    f.write_text("a = 1", encoding="utf-8")
    model = _FakeModel("a = 2")
    with patch.object(ch, "_get_gemini", return_value=model):
        out = code_helper({"action": "edit", "file_path": str(f), "instruction": "bump a"})
    assert f.read_text(encoding="utf-8") == "a = 2"
    assert out.startswith("File edited.")
    assert "Change: bump a" in model.prompts[0]


def test_explain_action_requires_code():
    assert code_helper({"action": "explain"}) == "Please provide code or a file path to explain, sir."


def test_explain_action_returns_model_text():
    with patch.object(ch, "_get_gemini", return_value=_FakeModel("  It prints.  ")):
        assert code_helper({"action": "explain", "code": "print(1)"}) == "It prints."


def test_run_action_missing_file(tmp_path):
    missing = tmp_path / "nope.py"
    assert code_helper({"action": "run", "file_path": str(missing)}) == f"File not found: {missing}"


def test_optimize_action_reports_line_delta(tmp_path):
    f = tmp_path / "o.py"
    f.write_text("a = 1\nb = 2\nc = a + b\nprint(c)", encoding="utf-8")
    with patch.object(ch, "_get_gemini", return_value=_FakeModel("print(3)")):
        out = code_helper({"action": "optimize", "file_path": str(f)})
    assert "Lines: 4 → 1 (−3 lines)" in out
    assert f.read_text(encoding="utf-8") == "print(3)"


def test_auto_action_routes_through_intent_detection():
    with patch.object(ch, "_detect_intent", return_value="explain") as det, \
         patch.object(ch, "_explain_action", return_value="explained") as exp:
        assert code_helper({"action": "auto", "code": "x"}) == "explained"
    det.assert_called_once_with("", "", "x")
    exp.assert_called_once()


def test_screen_debug_without_screenshot():
    with patch.object(ch, "_take_screenshot", return_value=None):
        out = code_helper({"action": "screen_debug"})
    assert out.startswith("Could not take screenshot")
