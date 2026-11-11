"""
tests/plugins/test_plugin_template.py — Tests for plugins/_template.py (drop-in plugin template).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import plugins._template as template
from core import plugin_loader


def test_template_passes_loader_validation():
    rec = plugin_loader._validate(template, "_template.py")
    assert rec.valid, rec.error
    assert rec.name == "my_plugin"
    assert "example_arg" in rec.parameters["properties"]


def test_run_returns_text_and_logs_to_player():
    player = MagicMock()
    out = template.run({"example_arg": "the lights"}, player=player)
    assert out == "Did the thing with the lights."
    player.write_log.assert_called_once_with("ALFRED: Did the thing with the lights.")


def test_run_without_player_or_args():
    assert template.run({}) == "Did the thing with ."


def test_run_swallows_player_errors():
    player = MagicMock()
    player.write_log.side_effect = RuntimeError("ui closed")
    assert template.run({"example_arg": "x"}, player=player) == "Did the thing with x."


def test_loader_call_run_passes_declared_kwargs():
    player = MagicMock()
    out = plugin_loader._call_run(template.run, {"example_arg": "y"}, player, None)
    assert out == "Did the thing with y."
    player.write_log.assert_called_once()
