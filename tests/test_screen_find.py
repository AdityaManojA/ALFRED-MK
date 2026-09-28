import io
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageDraw

from actions.screen_find import (
    find_element,
    get_rapid_ocr,
    get_onnx_session,
    is_icon_query,
    _calculate_similarity,
    _GLOBAL_ONNX_SESSIONS,
)
from actions.computer_control import computer_control, _screen_find


class TestScreenFindHybridGrounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a mock text editor window (800x600) with a standard toolbar and code lines
        cls.editor_img = Image.new("RGB", (800, 600), color=(30, 30, 30))
        d = ImageDraw.Draw(cls.editor_img)
        # Menu and toolbar items
        d.text((20, 15), "File", fill=(220, 220, 220))
        d.text((70, 15), "Edit", fill=(220, 220, 220))
        d.text((120, 15), "Save", fill=(220, 220, 220))
        d.text((180, 15), "View", fill=(220, 220, 220))
        d.text((240, 15), "Settings", fill=(220, 220, 220))

        # Editor content
        for y in range(60, 500, 40):
            d.text((30, y), f"// Code line at y={y}: let val = 42;", fill=(100, 180, 120))

        # Warm up OCR once to eliminate one-time engine spin-up
        find_element("Save", screenshot=cls.editor_img)

    def test_find_element_save_sub_150ms_without_gemini(self):
        """
        Verification Requirement:
        Call find_element('Save') on a text editor window.
        Verify coordinate return completes in <150ms without initiating a Gemini API call.
        """
        with patch("core.gemini.call") as mock_gemini_call:
            t0 = time.monotonic()
            coords = find_element("Save", screenshot=self.editor_img, threshold=0.80)
            elapsed_ms = (time.monotonic() - t0) * 1000

            # 1. Verification of return coordinates
            self.assertIsNotNone(coords, "find_element('Save') failed to locate the Save button")
            norm_x, norm_y = coords

            # Normalized coordinates must be between 0.0 and 1.0
            self.assertTrue(0.0 <= norm_x <= 1.0)
            self.assertTrue(0.0 <= norm_y <= 1.0)

            # In our 800x600 image, 'Save' was drawn at x=120, y=15:
            # Expected norm_x ≈ 120/800 = 0.15, norm_y ≈ 15/600 = 0.025
            self.assertAlmostEqual(norm_x, 0.16, delta=0.08)
            self.assertAlmostEqual(norm_y, 0.03, delta=0.06)

            # 2. Verification of sub-150ms latency
            self.assertLess(
                elapsed_ms, 150.0,
                f"Element localization took {elapsed_ms:.2f}ms, exceeding the 150ms threshold"
            )

            # 3. Verification that Gemini API was NOT called
            mock_gemini_call.assert_not_called()
            print(f"\n[Verification Passed] find_element('Save') returned in {elapsed_ms:.2f}ms without Gemini API call. Coords: {coords}")

    def test_onnx_model_session_caching(self):
        """Verify ONNX model sessions are cached globally in memory on first load."""
        session1 = get_onnx_session("omniparser_v2_quant.onnx")
        self.assertIsNotNone(session1)
        self.assertIn("omniparser_v2_quant.onnx", _GLOBAL_ONNX_SESSIONS)

        # Subsequent retrieval must return the exact same instance without disk reload
        session2 = get_onnx_session("omniparser_v2_quant.onnx")
        self.assertIs(session1, session2)

    def test_icon_query_detection(self):
        """Verify icon query classification heuristic."""
        self.assertTrue(is_icon_query("save_icon"))
        self.assertTrue(is_icon_query("gear icon"))
        self.assertTrue(is_icon_query("close_button"))
        self.assertFalse(is_icon_query("Save"))
        self.assertFalse(is_icon_query("Edit"))

    def test_low_confidence_fallback_to_gemini_with_red_tag_log(self):
        """
        Verify that if local confidence < 0.80, system logs:
        [screen] Local grounding confidence low (score) — delegating to Gemini
        and falls back to Gemini visual grounding.
        """
        mock_response = MagicMock()
        mock_response.text = "400, 300"

        # Search for a non-existent element on blank image
        blank_img = Image.new("RGB", (800, 600), color=(0, 0, 0))

        with patch("core.gemini.call", return_value=mock_response) as mock_gemini:
            with patch("sys.stdout") as mock_stdout, patch("builtins.print") as mock_print:
                coords = find_element("NonExistentSpecialButton999", screenshot=blank_img, threshold=0.80)

                # Verify red tag log emitted
                print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
                delegating_logs = [log for log in print_calls if "Local grounding confidence low" in log and "delegating to Gemini" in log]
                self.assertGreater(len(delegating_logs), 0, "Expected red-tag delegation log was not printed")

                # Verify Gemini was called
                mock_gemini.assert_called_once()

                # Verify coordinates returned from Gemini fallback (400/800 = 0.5, 300/600 = 0.5)
                self.assertIsNotNone(coords)
                self.assertAlmostEqual(coords[0], 0.5, delta=0.01)
                self.assertAlmostEqual(coords[1], 0.5, delta=0.01)

    def test_computer_control_integration(self):
        """Verify computer_control screen_find and screen_click use local grounding."""
        # Mock pyautogui size and click
        with patch("pyautogui.size", return_value=(800, 600)):
            with patch("pyautogui.screenshot", return_value=self.editor_img):
                # 1. Test _screen_find
                px_coords = _screen_find("Save")
                self.assertIsNotNone(px_coords)
                # Should be scaled to pixel dimensions (approx 120, 20)
                self.assertAlmostEqual(px_coords[0], 128, delta=50)
                self.assertAlmostEqual(px_coords[1], 20, delta=30)

                # 2. Test computer_control action='screen_find'
                res = computer_control({"action": "screen_find", "description": "Save"})
                self.assertIn(",", res)
                self.assertNotIn("NOT_FOUND", res)

                # 3. Test computer_control action='screen_click'
                with patch("actions.computer_control._click") as mock_click:
                    click_res = computer_control({"action": "screen_click", "description": "Save"})
                    self.assertIn("Clicked 'Save'", click_res)
                    mock_click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
