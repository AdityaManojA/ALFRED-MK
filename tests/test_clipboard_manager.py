"""
tests/test_clipboard_manager.py — Unit tests for persistent semantically indexed clipboard history.
"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from actions.clipboard_manager import (
    ClipboardManager,
    get_recent_clipboards,
    search_clipboard,
    paste_clipboard_item,
    add_clipboard_item,
    is_sensitive_content,
    classify_content_type,
    clipboard_manager_action,
)


class TestClipboardManager(unittest.TestCase):
    def setUp(self):
        # Point to a temporary file for isolated test history
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_history = Path(self.tmp_dir.name) / "test_clipboard_history.json"
        self.patcher = patch("actions.clipboard_manager.HISTORY_FILE", self.tmp_history)
        self.patcher.start()

        # Reset clipboard manager instance
        self.mgr = ClipboardManager.get_instance()
        self.mgr._history = []

    def tearDown(self):
        self.patcher.stop()
        self.tmp_dir.cleanup()

    def test_verification_requirement_copy_3_and_retrieve_chronological(self):
        """
        Verification Requirement:
        Copy 3 distinct text blocks sequentially.
        Call get_recent_clipboards(3) and verify all 3 items return accurately in chronological order.
        """
        block1 = "First block: System architecture overview of ALFRED-MK-IV."
        block2 = "Second block: RapidOCR and ONNX element detector pipeline."
        block3 = "Third block: Process-level audio ducking using pycaw session controls."

        # Copy 3 distinct text blocks sequentially
        item1 = add_clipboard_item(block1)
        time.sleep(0.01)
        item2 = add_clipboard_item(block2)
        time.sleep(0.01)
        item3 = add_clipboard_item(block3)

        self.assertIsNotNone(item1)
        self.assertIsNotNone(item2)
        self.assertIsNotNone(item3)

        # Call get_recent_clipboards(3)
        recent = get_recent_clipboards(3)
        self.assertEqual(len(recent), 3, f"Expected 3 items, got {len(recent)}")

        # Verify chronological order (oldest to newest: block1, block2, block3)
        self.assertEqual(recent[0]["text"], block1)
        self.assertEqual(recent[1]["text"], block2)
        self.assertEqual(recent[2]["text"], block3)

        # Also verify chronological timestamps
        self.assertLessEqual(recent[0]["timestamp"], recent[1]["timestamp"])
        self.assertLessEqual(recent[1]["timestamp"], recent[2]["timestamp"])

    def test_password_scrubbing(self):
        """Verify that passwords, password managers, and secret tokens are scrubbed."""
        # 1. Secret API token
        api_key = "sk-1234567890abcdef1234567890abcdef12345678"
        self.assertTrue(is_sensitive_content(api_key))
        res = add_clipboard_item(api_key)
        self.assertIsNone(res, "API key should not be recorded in clipboard history")

        # 2. Originating from password manager window
        pw_text = "StandardUserPass123!"
        self.assertTrue(is_sensitive_content(pw_text, source_proc="1password.exe", source_title="1Password"))
        res = add_clipboard_item(pw_text, source_app="1password.exe")
        self.assertIsNone(res, "Content from password manager should be scrubbed")

        # 3. High-entropy password pattern
        secret_blob = "k9#mP$2vL!8xQ@4z"
        self.assertTrue(is_sensitive_content(secret_blob))
        res = add_clipboard_item(secret_blob)
        self.assertIsNone(res, "High entropy secret pattern should be scrubbed")

        # 4. Normal text is NOT scrubbed
        normal_text = "Wayne Enterprises Tactical Terminal MK-IV"
        self.assertFalse(is_sensitive_content(normal_text, source_proc="code.exe", source_title="VS Code"))
        res = add_clipboard_item(normal_text)
        self.assertIsNotNone(res)

    def test_semantic_and_keyword_search(self):
        """Verify search_clipboard accurately matches contents by keyword and semantics."""
        add_clipboard_item("Batman Batmobile defense protocol specifications")
        add_clipboard_item("Python asyncio background worker queue implementation")
        add_clipboard_item("FastAPI WebSocket secure remote telemetry server")

        # Search for Batmobile
        matches = search_clipboard("Batmobile")
        self.assertGreater(len(matches), 0)
        self.assertIn("Batmobile", matches[0]["text"])

        # Search for background jobs
        matches2 = search_clipboard("background worker")
        self.assertGreater(len(matches2), 0)
        self.assertIn("asyncio", matches2[0]["text"])

    def test_paste_clipboard_item(self):
        """Verify pushing historical item back to active system clipboard."""
        add_clipboard_item("First line of notes")
        add_clipboard_item("Second line of notes")
        add_clipboard_item("Third line of notes")

        # Item 1 is newest ("Third line of notes"), Item 2 is ("Second line of notes")
        with patch("pyperclip.copy") as mock_copy:
            pasted = paste_clipboard_item(2)
            self.assertIsNotNone(pasted)
            self.assertEqual(pasted["text"], "Second line of notes")
            mock_copy.assert_called_with("Second line of notes")

    def test_rolling_stack_max_50_items(self):
        """Verify rolling history stack caps at 50 items."""
        for i in range(60):
            add_clipboard_item(f"Item number {i}")

        self.assertEqual(len(self.mgr._history), 50)
        # Newest item must be Item 59
        self.assertEqual(self.mgr._history[0]["text"], "Item number 59")

    def test_content_type_classification(self):
        """Verify content type heuristic classification."""
        self.assertEqual(classify_content_type("https://github.com/AdityaManojA/ALFRED-MK-IV"), "url")
        self.assertEqual(classify_content_type("bruce@wayne-enterprises.com"), "email")
        self.assertEqual(classify_content_type('{"key": "value", "status": true}'), "json")
        self.assertEqual(classify_content_type("def calculate_metrics(items):\n    return len(items)"), "code")
        self.assertEqual(classify_content_type("Just a regular sentence about tactical systems."), "text")

    def test_action_handler_interface(self):
        """Verify clipboard_manager TOOL action handler."""
        add_clipboard_item("Action test snippet")

        # 1. recent
        out_recent = clipboard_manager_action({"action": "recent", "count": 1})
        self.assertIn("Action test snippet", out_recent)

        # 2. search
        out_search = clipboard_manager_action({"action": "search", "query": "snippet"})
        self.assertIn("Action test snippet", out_search)

        # 3. paste
        with patch("pyperclip.copy"):
            out_paste = clipboard_manager_action({"action": "paste", "index": 1})
            self.assertIn("Active clipboard restored", out_paste)


if __name__ == "__main__":
    unittest.main()
