"""Behavioural tests for actions.send_message.

PyAutoGUI, pyperclip, subprocess, webbrowser and time.sleep are all mocked, so
no keys are pressed and no apps are opened.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

import actions.send_message as sm
from actions.send_message import send_message

_REAL_GET_OS = sm._get_os


@pytest.fixture(autouse=True)
def gui(monkeypatch):
    fake_gui = MagicMock(name="pyautogui")
    fake_clip = MagicMock(name="pyperclip")
    monkeypatch.setattr(sm, "pyautogui", fake_gui, raising=False)
    monkeypatch.setattr(sm, "pyperclip", fake_clip, raising=False)
    monkeypatch.setattr(sm, "_PYAUTOGUI", True)
    monkeypatch.setattr(sm, "_PYPERCLIP", True)
    monkeypatch.setattr(sm.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sm, "_get_os", lambda: "windows")
    return SimpleNamespace(gui=fake_gui, clip=fake_clip)


# ── platform resolution ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name, handler",
    [
        ("WhatsApp", "_send_whatsapp"),
        ("wp", "_send_whatsapp"),
        ("Telegram", "_send_telegram"),
        ("tg", "_send_telegram"),
        ("Instagram", "_send_instagram"),
        ("ig", "_send_instagram"),
        ("Signal", "_send_signal"),
        ("signal desktop", "_send_signal"),
        ("Discord", "_send_discord"),
        ("Facebook Messenger", "_send_messenger"),
        ("fb", "_send_messenger"),
    ],
)
def test_resolve_platform(name, handler):
    assert sm._resolve_platform(name) is getattr(sm, handler)


def test_resolve_platform_unknown_uses_titled_app_name():
    with patch.object(sm, "_desktop_send", return_value="sent") as ds:
        assert sm._resolve_platform("  slack ")("bob", "hi") == "sent"
    ds.assert_called_once_with("Slack", "bob", "hi")


# ── OS config ────────────────────────────────────────────────────────────────

def test_get_os_reads_config_and_defaults(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(sm, "_base_dir", lambda: tmp_path)
    assert _REAL_GET_OS() == "windows"  # no config file
    (tmp_path / "config" / "api_keys.json").write_text('{"os_system": "MAC"}', encoding="utf-8")
    assert _REAL_GET_OS() == "mac"


# ── keyboard helpers ─────────────────────────────────────────────────────────

def test_paste_text_uses_clipboard_and_ctrl_v(gui):
    sm._paste_text("hello")
    gui.clip.copy.assert_called_once_with("hello")
    gui.gui.hotkey.assert_called_once_with("ctrl", "v")


def test_paste_text_uses_cmd_v_on_mac(gui, monkeypatch):
    monkeypatch.setattr(sm, "_get_os", lambda: "mac")
    sm._paste_text("x")
    gui.gui.hotkey.assert_called_once_with("command", "v")


def test_paste_text_types_when_no_clipboard(gui, monkeypatch):
    monkeypatch.setattr(sm, "_PYPERCLIP", False)
    sm._paste_text("abc")
    gui.gui.write.assert_called_once_with("abc", interval=0.03)
    gui.clip.copy.assert_not_called()


def test_require_pyautogui(monkeypatch):
    monkeypatch.setattr(sm, "_PYAUTOGUI", False)
    with pytest.raises(RuntimeError, match="PyAutoGUI not installed"):
        sm._paste_text("x")


def test_desktop_send_sequence(gui):
    with patch.object(sm, "_open_app", return_value=True):
        out = sm._desktop_send("Telegram", "Alice", "Hi there")
    assert out == "Message sent to Alice via Telegram."
    assert gui.clip.copy.call_args_list == [call("Alice"), call("Hi there")]
    gui.gui.hotkey.assert_any_call("ctrl", "f")
    assert gui.gui.press.call_args_list[-1] == call("enter")


def test_desktop_send_app_open_failure():
    with patch.object(sm, "_open_app", return_value=False):
        assert sm._desktop_send("Signal", "a", "b") == "Could not open Signal."


def test_open_app_linux_tries_launchers(monkeypatch):
    monkeypatch.setattr(sm, "_get_os", lambda: "linux")
    with patch.object(sm.subprocess, "Popen", side_effect=[FileNotFoundError(), MagicMock()]) as popen:
        assert sm._open_app("Signal") is True
    assert popen.call_args_list[0].args[0] == ["gtk-launch", "signal"]
    assert popen.call_args_list[1].args[0] == ["signal"]


def test_open_app_mac_retries_with_app_suffix(monkeypatch):
    monkeypatch.setattr(sm, "_get_os", lambda: "mac")
    results = [SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)]
    with patch.object(sm.subprocess, "run", side_effect=results) as run:
        assert sm._open_app("Signal") is True
    assert run.call_args_list[1].args[0] == ["open", "-a", "Signal.app"]


def test_instagram_browser_failure():
    with patch.object(sm, "_open_browser_url", return_value=False):
        assert sm._send_instagram("bob", "hi") == "Could not open Instagram in browser."


# ── send_message handler ─────────────────────────────────────────────────────

def test_send_message_validations(monkeypatch):
    assert send_message({"message_text": "x"}) == "Please specify a recipient."
    assert send_message({"receiver": "bob"}) == "Please specify the message content."
    monkeypatch.setattr(sm, "_PYAUTOGUI", False)
    assert send_message({"receiver": "bob", "message_text": "x"}).startswith("PyAutoGUI is not installed")


def test_send_message_routes_to_platform_and_logs():
    handler = MagicMock(return_value="Message sent to bob via Signal.")
    player = MagicMock()
    with patch.object(sm, "_resolve_platform", return_value=handler) as resolve:
        out = send_message({"receiver": " bob ", "message_text": " yo ", "platform": "Signal"}, player=player)
    resolve.assert_called_once_with("Signal")
    handler.assert_called_once_with("bob", "yo")
    assert out == "Message sent to bob via Signal."
    assert player.write_log.call_count == 2


def test_send_message_wraps_handler_errors():
    handler = MagicMock(side_effect=RuntimeError("window vanished"))
    with patch.object(sm, "_resolve_platform", return_value=handler):
        out = send_message({"receiver": "bob", "message_text": "x"})
    assert out == "Could not send message: window vanished"
