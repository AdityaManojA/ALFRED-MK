"""
Unit and integration tests for screen_processor.py window context grounding.
Verifies:
1. Native OS window API querying (`get_active_window_info`, `get_active_window_context`).
2. Resolution latency constraint (< 15ms).
3. Metadata block formatting: `[WINDOW_CONTEXT] App: <Name> | Title: <Title> | Monitor: <ID>`.
4. Visual frame payload construction with prepended metadata block.
5. Graceful fallback to `App: Unknown` on permissions / handle failure.
6. Real capture and synthetic VS Code window verification.
"""
import base64
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.screen_processor import (
    capture_screen,
    _capture_screen,
    get_active_window_info,
    get_active_window_context,
    format_window_context,
    format_visual_payload,
    ScreenCapturePayload,
)


class TestScreenProcessorWindowContext(unittest.TestCase):

    def test_window_info_schema_and_latency(self):
        """Verifies that active window query resolves in < 15ms and adheres to schema."""
        # Warmup call
        get_active_window_info(1)

        t0 = time.perf_counter()
        info = get_active_window_info(monitor_id=1)
        dur_ms = (time.perf_counter() - t0) * 1000

        self.assertIn("app", info)
        self.assertIn("title", info)
        self.assertIn("monitor", info)
        self.assertIn("handle", info)
        self.assertIn("latency_ms", info)
        self.assertIn("context", info)

        self.assertEqual(info["monitor"], 1)
        self.assertTrue(len(info["app"]) > 0, "App name should not be empty")
        self.assertTrue(info["context"].startswith("[WINDOW_CONTEXT]"))
        self.assertIn(f"Monitor: 1", info["context"])

        # Strict latency constraint (< 15ms)
        self.assertLess(info["latency_ms"], 15.0, f"Query took {info['latency_ms']:.2f}ms, expected < 15ms")
        self.assertLess(dur_ms, 15.0, f"Total call took {dur_ms:.2f}ms, expected < 15ms")
        print(f"\n[Test] Window context latency: {info['latency_ms']:.3f}ms | Context: {info['context']}")

    def test_format_window_context(self):
        """Verifies exact string formatting requirements."""
        block = format_window_context("VS Code", "main.py - Alfred-Mark-IV", 1)
        expected = "[WINDOW_CONTEXT] App: VS Code | Title: main.py - Alfred-Mark-IV | Monitor: 1"
        self.assertEqual(block, expected)

        # Fallback handling
        block_fallback = format_window_context("", "", 2)
        self.assertEqual(block_fallback, "[WINDOW_CONTEXT] App: Unknown | Title: None | Monitor: 2")

    def test_format_visual_payload_prepends_metadata(self):
        """Verifies metadata block is prepended directly to the visual frame payload."""
        sample_img = b"FAKE_JPEG_IMAGE_BYTES"
        ctx = "[WINDOW_CONTEXT] App: VS Code | Title: test_file.py | Monitor: 1"
        payload = format_visual_payload(
            img_bytes=sample_img,
            mime_type="image/jpeg",
            window_context=ctx,
            question="What is the bug on line 42?",
        )

        self.assertIn("inline_data", payload)
        self.assertIn("text", payload)
        self.assertEqual(payload["inline_data"]["mime_type"], "image/jpeg")

        # Decode base64 to verify image preservation
        decoded = base64.b64decode(payload["inline_data"]["data"])
        self.assertEqual(decoded, sample_img)

        # Check metadata header is prepended to text
        text = payload["text"]
        self.assertTrue(text.startswith(ctx), "Payload text must start with [WINDOW_CONTEXT] block")
        self.assertIn("[IMAGE SOURCE: SCREEN CAPTURE]", text)
        self.assertIn("What is the bug on line 42?", text)

    def test_capture_screen_returns_hybrid_payload(self):
        """Verifies capture_screen() returns valid compressed image and window context."""
        try:
            res = capture_screen(monitor=1)
        except Exception:
            # Headless or screen locked BitBlt fallback mock
            with patch("actions.screen_processor._mss_factory") as mock_mss:
                mock_sct = MagicMock()
                mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
                fake_shot = MagicMock()
                fake_shot.rgb = b"\x00" * (100 * 100 * 3)
                fake_shot.size = (100, 100)
                mock_sct.grab.return_value = fake_shot
                mock_mss.return_value.__enter__.return_value = mock_sct
                res = capture_screen(monitor=1)

        # 3-tuple unpacking
        img_b, mime_t, win_ctx = res
        self.assertIsInstance(img_b, bytes)
        self.assertTrue(len(img_b) > 0)
        self.assertEqual(mime_t, "image/jpeg")
        self.assertTrue(win_ctx.startswith("[WINDOW_CONTEXT]"))

        # Dict item access
        self.assertIn("inline_data", res)
        self.assertIn("text", res)
        self.assertTrue(res["text"].startswith("[WINDOW_CONTEXT]"))

        # Properties
        self.assertEqual(res.img_bytes, img_b)
        self.assertEqual(res.mime_type, mime_t)
        self.assertEqual(res.window_context, win_ctx)

    def test_graceful_fallback_when_os_api_fails(self):
        """Verifies system falls back to 'App: Unknown' without raising exceptions."""
        with patch("actions.screen_processor._get_windows_window_info", side_effect=Exception("Permission denied")):
            with patch("actions.screen_processor._get_macos_window_info", side_effect=Exception("Permission denied")):
                with patch("actions.screen_processor._get_linux_window_info", side_effect=Exception("Permission denied")):
                    info = get_active_window_info(1)
                    self.assertEqual(info["app"], "Unknown")
                    self.assertEqual(info["title"], "None")
                    self.assertIn("[WINDOW_CONTEXT] App: Unknown | Title: None | Monitor: 1", info["context"])

    def test_vscode_window_context_verification(self):
        """
        Verification Requirement:
        Verify [WINDOW_CONTEXT] header contains VS Code and file title.
        """
        simulated_title = "active_model.py - Alfred-Mark-IV - Visual Studio Code"
        with patch("actions.screen_processor._get_windows_window_info", return_value=("VS Code", simulated_title, 12345)):
            try:
                payload = capture_screen(monitor=1)
            except Exception:
                with patch("actions.screen_processor._mss_factory") as mock_mss:
                    mock_sct = MagicMock()
                    mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
                    fake_shot = MagicMock()
                    fake_shot.rgb = b"\x00" * (100 * 100 * 3)
                    fake_shot.size = (100, 100)
                    mock_sct.grab.return_value = fake_shot
                    mock_mss.return_value.__enter__.return_value = mock_sct
                    payload = capture_screen(monitor=1)

            text_header = payload["text"]

            # Verify [WINDOW_CONTEXT] header contains VS Code and file title
            self.assertIn("[WINDOW_CONTEXT]", text_header)
            self.assertIn("App: VS Code", text_header)
            self.assertIn("Title: active_model.py - Alfred-Mark-IV - Visual Studio Code", text_header)
            print(f"\n[Verification Passed] Output stream payload header:\n{text_header[:120]}...")


if __name__ == "__main__":
    unittest.main()
