import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import plugin_loader
from memory import config_manager


class TestPluginSettingsSchemaCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.config_file = self.config_dir / "api_keys.json"
        self.dir_patch = patch.object(config_manager, "CONFIG_DIR", self.config_dir)
        self.file_patch = patch.object(config_manager, "CONFIG_FILE", self.config_file)
        self.dir_patch.start()
        self.file_patch.start()
        config_manager.invalidate_config_cache()
        self.record = plugin_loader.PluginRecord(
            name="demo",
            description="Demo plugin",
            valid=True,
            settings={
                "namespace": "demo_config",
                "title": "Demo",
                "fields": [{"key": "token", "type": "password"}],
            },
        )
        self.registry = plugin_loader.PluginRegistry({"demo": self.record}, lambda _msg: None)

    def tearDown(self):
        config_manager.invalidate_config_cache()
        self.file_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()

    def test_schema_is_reused_and_callers_cannot_mutate_cache(self):
        with (
            patch.object(plugin_loader, "get_plugin_enabled", return_value=True) as enabled,
            patch.object(plugin_loader, "get_plugin_config", return_value={"token": "secret"}) as config,
        ):
            first = self.registry.settings_schemas()
            first[0]["values"]["token"] = "changed"
            first[0]["fields"].append({"key": "extra"})
            second = self.registry.settings_schemas()

        self.assertEqual(enabled.call_count, 1)
        self.assertEqual(config.call_count, 1)
        self.assertEqual(second[0]["values"], {"token": "secret"})
        self.assertEqual(second[0]["fields"], [{"key": "token", "type": "password"}])

    def test_plugin_config_and_enable_changes_refresh_schema(self):
        with (
            patch.object(plugin_loader, "get_plugin_enabled", wraps=config_manager.get_plugin_enabled) as enabled,
            patch.object(plugin_loader, "get_plugin_config", wraps=config_manager.get_plugin_config) as config,
        ):
            self.assertEqual(self.registry.settings_schemas()[0]["values"], {})
            self.registry.settings_schemas()
            self.assertEqual(enabled.call_count, 1)
            self.assertEqual(config.call_count, 1)

            config_manager.save_assistant_config("Alfred", "User")
            self.registry.settings_schemas()
            self.assertEqual(enabled.call_count, 1)
            self.assertEqual(config.call_count, 1)

            config_manager.save_plugin_config("demo_config", {"token": "new"})
            self.assertEqual(self.registry.settings_schemas()[0]["values"], {"token": "new"})
            self.assertEqual(enabled.call_count, 2)
            self.assertEqual(config.call_count, 2)

    def test_external_plugin_config_write_refreshes_schema(self):
        config_manager.save_plugin_config("demo_config", {"token": "old"})
        self.assertEqual(self.registry.settings_schemas()[0]["values"], {"token": "old"})

        self.config_file.write_text(json.dumps({
            "plugin_config": {"demo_config": {"token": "new-external-value"}},
        }), encoding="utf-8")

        self.assertEqual(
            self.registry.settings_schemas()[0]["values"],
            {"token": "new-external-value"},
        )


if __name__ == "__main__":
    unittest.main()
