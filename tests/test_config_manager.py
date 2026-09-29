import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from memory import config_manager


class TestConfigCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.config_file = self.config_dir / "api_keys.json"
        self.dir_patch = patch.object(config_manager, "CONFIG_DIR", self.config_dir)
        self.file_patch = patch.object(config_manager, "CONFIG_FILE", self.config_file)
        self.dir_patch.start()
        self.file_patch.start()
        config_manager.invalidate_config_cache()

    def tearDown(self):
        config_manager.invalidate_config_cache()
        self.file_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()

    def _write_raw(self, data):
        self.config_file.write_text(json.dumps(data), encoding="utf-8")

    def test_repeated_loads_read_file_once_and_return_isolated_copies(self):
        self._write_raw({"assistant_name": "Alfred", "nested": {"value": 1}})
        original_read_text = Path.read_text

        with patch.object(
            Path,
            "read_text",
            autospec=True,
            side_effect=lambda path, *args, **kwargs: original_read_text(path, *args, **kwargs),
        ) as read_text:
            first = config_manager.load_api_keys()
            first["nested"]["value"] = 99
            second = config_manager.load_api_keys()
            self.assertEqual(config_manager.get_assistant_name(), "Alfred")

        self.assertEqual(read_text.call_count, 1)
        self.assertEqual(second["nested"]["value"], 1)

    def test_write_through_updates_cache_without_another_read(self):
        self._write_raw({"assistant_name": "Old", "preserved": True})
        original_read_text = Path.read_text

        with patch.object(
            Path,
            "read_text",
            autospec=True,
            side_effect=lambda path, *args, **kwargs: original_read_text(path, *args, **kwargs),
        ) as read_text:
            self.assertEqual(config_manager.get_assistant_name(), "Old")
            config_manager.save_assistant_config("New", "User")
            self.assertEqual(config_manager.get_assistant_name(), "New")
            self.assertEqual(config_manager.load_api_keys()["preserved"], True)

        self.assertEqual(read_text.call_count, 1)
        self.assertEqual(json.loads(self.config_file.read_text(encoding="utf-8"))["user_name"], "User")

    def test_signature_change_reloads_external_write(self):
        self._write_raw({"assistant_name": "Before"})
        self.assertEqual(config_manager.get_assistant_name(), "Before")

        self._write_raw({"assistant_name": "After external write"})
        self.assertEqual(config_manager.get_assistant_name(), "After external write")

    def test_failed_write_does_not_advance_cached_value(self):
        self._write_raw({"assistant_name": "Before"})
        self.assertEqual(config_manager.get_assistant_name(), "Before")

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                config_manager.save_assistant_config("After", "User")

        self.assertEqual(config_manager.get_assistant_name(), "Before")

    def test_concurrent_writers_do_not_lose_unrelated_fields(self):
        self._write_raw({"preserved": "yes"})
        config_manager.load_api_keys()
        barrier = threading.Barrier(3)

        def save_input():
            barrier.wait()
            config_manager.save_input_device("Mic")

        def save_output():
            barrier.wait()
            config_manager.save_output_device("Speakers")

        threads = [threading.Thread(target=save_input), threading.Thread(target=save_output)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        config = config_manager.load_api_keys()
        self.assertEqual(config["input_device"], "Mic")
        self.assertEqual(config["output_device"], "Speakers")
        self.assertEqual(config["preserved"], "yes")

    def test_voice_engine_round_trip_and_defaults(self):
        # Default when unset
        self.assertEqual(config_manager.get_voice_engine(), "default")
        self.assertFalse(config_manager.get_jarvis_allow_cpu())

        # Save jarvis
        config_manager.save_voice_engine("jarvis")
        self.assertEqual(config_manager.get_voice_engine(), "jarvis")

        # Round trips in stored JSON
        raw = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(raw.get("voice_engine"), "jarvis")
        self.assertEqual(raw.get("voice", {}).get("engine"), "jarvis")

        # Invalid engine falls back to default
        config_manager.save_voice_engine("non_existent_engine")
        self.assertEqual(config_manager.get_voice_engine(), "default")

        # CPU allow toggle
        config_manager.save_jarvis_allow_cpu(True)
        self.assertTrue(config_manager.get_jarvis_allow_cpu())


if __name__ == "__main__":
    unittest.main()

