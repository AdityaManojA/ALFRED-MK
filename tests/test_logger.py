"""Behavioural tests for core.logger (timestamped print, URL redaction, ffmpeg filter)."""
from __future__ import annotations

import builtins
import io
import json
import time

import pytest

from core import logger


# ── redact_signed_urls ───────────────────────────────────────────────────────

def test_redact_leaves_plain_text_untouched():
    assert logger.redact_signed_urls("no links here") == "no links here"


def test_redact_strips_path_and_query():
    text = "fetching https://cdn.example.com/a/b.mp3?sig=SECRET&exp=1 now"
    out = logger.redact_signed_urls(text)
    assert out == "fetching https://cdn.example.com/… now"
    assert "SECRET" not in out


def test_redact_handles_multiple_and_quoted_urls():
    text = 'a "http://h1.io/x?t=1" and (https://h2.net:8443/y)'
    assert logger.redact_signed_urls(text) == 'a "http://h1.io/…" and (https://h2.net:8443/…)'


# ── _is_ffmpeg_banner ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "line",
    [
        "Input #0, mp3, from 'pipe:':",
        "  Output #0, wav, to 'out.wav':",
        "    Stream #0:0: Audio: mp3",
        "  Metadata:",
        "  Duration: 00:00:03.10, start: 0.0, bitrate: 128 kb/s",
        "Stream mapping: mp3 (mp3float) -> pcm",
    ],
)
def test_ffmpeg_banners_detected(line):
    assert logger._is_ffmpeg_banner(line) is True


@pytest.mark.parametrize("line", ["", "   ", "Hello sir", "Duration: 3 minutes"])
def test_normal_lines_not_banners(line):
    assert logger._is_ffmpeg_banner(line) is False


# ── format_timestamp ─────────────────────────────────────────────────────────

def test_format_timestamp_wall_and_elapsed(monkeypatch):
    monkeypatch.setattr(logger, "_T0", 100.0)
    wall = time.mktime((2026, 1, 2, 15, 42, 7, 0, 0, -1)) + 0.3185
    assert logger.format_timestamp(wall, 100.0 + 63.4125) == "[15:42:07.318 | +01:03.412]"


def test_format_timestamp_clamps_negative_elapsed(monkeypatch):
    monkeypatch.setattr(logger, "_T0", 100.0)
    assert logger.format_timestamp(time.time(), 50.0).endswith("| +00:00.000]")


# ── ts_print ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fixed_prefix(monkeypatch):
    monkeypatch.setattr(logger, "_DEBUG_TIMESTAMPS", True)
    monkeypatch.setattr(logger, "format_timestamp", lambda w, m: "[TS]")


def test_ts_print_prefixes_each_line_and_drops_banners(fixed_prefix, capsys):
    logger.ts_print("hello", "world\nStream #0:0: Audio\n\nsee https://x.io/p?k=1")
    out = capsys.readouterr().out
    assert out == "[TS] hello world\n\n[TS] see https://x.io/…\n"


def test_ts_print_respects_sep_and_end(fixed_prefix, capsys):
    logger.ts_print("a", "b", sep="-", end="!")
    assert capsys.readouterr().out == "[TS] a-b!"


def test_ts_print_blank_content_not_prefixed(fixed_prefix, capsys):
    logger.ts_print("   ")
    assert capsys.readouterr().out == "   \n"


def test_ts_print_stderr_is_prefixed(fixed_prefix, capsys):
    import sys

    logger.ts_print("oops", file=sys.stderr)
    assert capsys.readouterr().err == "[TS] oops\n"


def test_ts_print_custom_file_passthrough(fixed_prefix):
    buf = io.StringIO()
    logger.ts_print("raw https://x.io/p?k=1", file=buf)
    assert buf.getvalue() == "raw https://x.io/p?k=1\n"


def test_ts_print_disabled_is_plain_print(monkeypatch, capsys):
    monkeypatch.setattr(logger, "_DEBUG_TIMESTAMPS", False)
    logger.ts_print("Stream #0:0 stays", "x")
    assert capsys.readouterr().out == "Stream #0:0 stays x\n"


# ── config toggle + install ──────────────────────────────────────────────────

def _point_config_at(monkeypatch, tmp_path, payload):
    (tmp_path / "core").mkdir(exist_ok=True)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(exist_ok=True)
    if payload is not None:
        (cfg_dir / "api_keys.json").write_text(payload, encoding="utf-8")
    monkeypatch.setattr(logger, "__file__", str(tmp_path / "core" / "logger.py"))


@pytest.mark.parametrize(
    "payload, expected",
    [(None, True), ("{}", True), (json.dumps({"debug_timestamps": False}), False), ("{not json", True)],
)
def test_debug_toggle_from_config(monkeypatch, tmp_path, payload, expected):
    _point_config_at(monkeypatch, tmp_path, payload)
    assert logger._is_debug_timestamps_enabled() is expected


def test_install_is_idempotent(monkeypatch, tmp_path):
    _point_config_at(monkeypatch, tmp_path, json.dumps({"debug_timestamps": False}))
    monkeypatch.setattr(builtins, "print", builtins.print)  # restored on teardown
    monkeypatch.setattr(logger, "_installed", False)
    monkeypatch.setattr(logger, "_DEBUG_TIMESTAMPS", True)
    logger.install_timestamped_logging()
    assert builtins.print is logger.ts_print
    assert logger._DEBUG_TIMESTAMPS is False
    monkeypatch.setattr(logger, "_DEBUG_TIMESTAMPS", True)
    logger.install_timestamped_logging()  # second call is a no-op
    assert logger._DEBUG_TIMESTAMPS is True
