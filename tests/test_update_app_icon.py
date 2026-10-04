"""
tests/test_update_app_icon.py — Unit tests for update_app_icon action and thread-safe icon updates.
"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from actions.update_app_icon import update_app_icon


class TestUpdateAppIconAction(unittest.TestCase):

    def test_empty_icon_name(self):
        """Verify passing empty icon_name prompts for a valid insignia name."""
        result = update_app_icon({"icon_name": ""})
        self.assertIn("Please specify which icon to switch to", result)

    def test_player_set_app_icon_success(self):
        """Verify successful delegation to player.set_app_icon."""
        mock_player = MagicMock()
        mock_player.set_app_icon.return_value = True

        result = update_app_icon({"icon_name": "Batman Beyond"}, player=mock_player)
        mock_player.set_app_icon.assert_called_once_with("Batman Beyond")
        self.assertIn("successfully updated in realtime", result)
        self.assertIn("Batman Beyond", result)

    def test_player_set_app_icon_not_found(self):
        """Verify failed icon resolution provides available options."""
        mock_player = MagicMock()
        mock_player.set_app_icon.return_value = False

        result = update_app_icon({"icon_name": "NonExistentInsignia"}, player=mock_player)
        mock_player.set_app_icon.assert_called_once_with("NonExistentInsignia")
        self.assertIn("Could not find an icon matching", result)
        self.assertIn("Available insignias", result)

    def test_player_exception_handled_cleanly(self):
        """Verify exceptions during icon update are captured and returned cleanly without crashing."""
        mock_player = MagicMock()
        mock_player.set_app_icon.side_effect = RuntimeError("Simulated UI error")

        result = update_app_icon({"icon_name": "Batman Beyond"}, player=mock_player)
        self.assertIn("Failed to update application icon", result)
        self.assertIn("Simulated UI error", result)

    def test_fallback_to_config_manager(self):
        """Verify fallback saves icon to config when no player is attached."""
        with patch("memory.config_manager.save_app_icon") as mock_save:
            result = update_app_icon({"icon_name": "Classic Bat"}, player=None)
            mock_save.assert_called_once_with("Classic Bat")
            self.assertIn("successfully updated in realtime", result)


class TestThreadSafeSetAppIcon(unittest.TestCase):

    def test_set_app_icon_dispatches_from_worker_thread(self):
        """Verify calling set_app_icon off-thread signals GUI thread without touching widgets."""
        from ui import MainWindow

        # Create a mock MainWindow instance without initializing GUI widgets
        win = object.__new__(MainWindow)
        win._set_app_icon_sig = MagicMock()
        win._apply_app_icon_ui = MagicMock()

        # Mock icon path resolution
        fake_path = r"D:\Projects\Alfred-Mark-VIII\Icons\baticon_Beyond.png"
        win._resolve_icon_path = MagicMock(return_value=fake_path)

        # Call from a background worker thread
        worker_res = []

        def worker():
            with patch("memory.config_manager.save_app_icon"):
                ok = MainWindow.set_app_icon(win, "Batman Beyond", notify=True)
                worker_res.append(ok)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(worker_res, [True])
        win._set_app_icon_sig.emit.assert_called_once_with(fake_path, True)
        win._apply_app_icon_ui.assert_not_called()


if __name__ == "__main__":
    unittest.main()
