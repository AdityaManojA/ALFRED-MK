"""Behavioural tests for core.audio_devices (device listing, filtering and resolution).

sounddevice is replaced with an in-memory fake; no audio hardware is touched.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from core import audio_devices as ad

APIS = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}]
MME, DS, WASAPI = 0, 1, 2

LONG = "Realtek HD Audio 2nd output (Realtek(R) Audio)"
TRUNC = LONG[:31]


def dev(name, api, i=0, o=0):
    return {"name": name, "hostapi": api, "max_input_channels": i, "max_output_channels": o}


DEVICES = [
    dev("Microsoft Sound Mapper - Input", MME, i=2),     # 0 pseudo
    dev("Microphone (USB Mic)", MME, i=1),                # 1
    dev(TRUNC, MME, o=2),                                 # 2 truncated name
    dev("Speakers (Realtek)", MME, o=2),                  # 3
    dev("Primary Sound Capture Driver", DS, i=2),         # 4 pseudo
    dev("Microphone (USB Mic)", DS, i=1),                 # 5
    dev("Microphone (USB Mic)", DS, i=1),                 # 6 duplicate
    dev("", DS, i=1),                                     # 7 unnamed
    dev(LONG, DS, o=2),                                   # 8
    dev("Speakers (Realtek)", DS, o=2),                   # 9
    dev("Speakers (Realtek)", WASAPI, o=0),               # 10 zero channels
]


class FakeSD:
    def __init__(self, devices=DEVICES, apis=APIS, unusable=(), fake_sink_apis=(), input_frames=10**6):
        self.devices, self.apis = devices, apis
        self.unusable = set(unusable)
        self.fake_sink_apis = set(fake_sink_apis)
        self.input_frames = input_frames
        self.opened = []
        self.clock = [0.0]

    # sounddevice API
    def query_devices(self):
        return self.devices

    def query_hostapis(self):
        return self.apis

    def _stream(self, kind, kwargs):
        idx = kwargs["device"]
        self.opened.append((kind, idx, kwargs["samplerate"]))
        if idx in self.unusable:
            raise OSError("Invalid sample rate")
        sd = self

        class Stream:
            closed = False

            def start(self):
                if kind == "input" and kwargs.get("callback"):
                    kwargs["callback"](None, sd.input_frames)

            def write(self, data):
                api = sd.devices[idx]["hostapi"]
                if api not in sd.fake_sink_apis:
                    sd.clock[0] += len(data) / 2 / kwargs["samplerate"]  # real-time sink

            def stop(self):
                pass

            def close(self):
                Stream.closed = True

        return Stream()

    def InputStream(self, **kwargs):
        return self._stream("input", kwargs)

    def RawOutputStream(self, **kwargs):
        return self._stream("output", kwargs)


@pytest.fixture
def sd(monkeypatch):
    def install(**kw):
        fake = FakeSD(**kw)
        mod = types.ModuleType("sounddevice")
        for name in ("query_devices", "query_hostapis", "InputStream", "RawOutputStream"):
            setattr(mod, name, getattr(fake, name))
        monkeypatch.setitem(sys.modules, "sounddevice", mod)
        monkeypatch.setattr(ad, "time", SimpleNamespace(monotonic=lambda: fake.clock[0], sleep=lambda s: None))
        return fake

    # Pretend Qt is absent so list_devices() never takes the "on GUI thread" path
    # (other tests in the session may have created a QApplication).
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", None)
    monkeypatch.setattr(ad, "_cache", None)
    monkeypatch.setattr(ad, "_probe_results", {})
    monkeypatch.setattr(ad, "_chosen_api", {"input": None, "output": None})
    monkeypatch.setattr(ad, "_RATES", {"input": 16000, "output": 24000})
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    return install


# ── pure helpers ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name, pseudo",
    [("Microsoft Sound Mapper - Output", True), ("sysdefault:CARD=PCH", True), ("Default", True),
     ("dmix", True), ("Headset (Jabra)", False), ("Speakers (Realtek)", False)],
)
def test_is_pseudo(name, pseudo):
    assert ad._is_pseudo(name) is pseudo


def test_display_name_expands_truncated_mme_names():
    assert ad._display_name(TRUNC, DEVICES) == LONG
    assert ad._display_name("Short name", DEVICES) == "Short name"
    assert ad._display_name("X" * 31, DEVICES) == "X" * 31  # no longer match


def test_configure_sets_rates_and_drops_cache(sd, monkeypatch):
    monkeypatch.setattr(ad, "_cache", {"input": ["stale"], "output": []})
    ad.configure(48000, 44100.0)
    assert ad._RATES == {"input": 48000, "output": 44100}
    assert ad._cache is None


# ── _usable / _transport_works ───────────────────────────────────────────────

def test_usable_opens_at_configured_rate(sd):
    fake = sd(unusable={3})
    assert ad._usable(1, "input") is True
    assert ad._usable(9, "output") is True
    assert ad._usable(3, "output") is False
    assert fake.opened == [("input", 1, 16000), ("output", 9, 24000), ("output", 3, 24000)]


def test_transport_output_detects_fake_sink_and_caches(sd):
    fake = sd(fake_sink_apis={DS})
    assert ad._transport_works(9, "output", ("directsound", "output")) is False
    assert ad._transport_works(3, "output", ("mme", "output")) is True
    opened = len(fake.opened)
    assert ad._transport_works(9, "output", ("directsound", "output")) is False
    assert len(fake.opened) == opened  # cached, not re-probed


def test_transport_input_counts_callback_frames(sd):
    sd(input_frames=10)
    assert ad._transport_works(1, "input", ("mme", "input")) is False
    ad._probe_results.clear()
    sd(input_frames=16000)
    assert ad._transport_works(1, "input", ("mme", "input")) is True


def test_transport_probe_error_is_false(sd):
    sd(unusable={1})
    assert ad._transport_works(1, "input", ("x", "input")) is False


# ── _query / list_devices ────────────────────────────────────────────────────

def test_query_filters_and_picks_api_per_direction(sd):
    sd(fake_sink_apis={DS})
    result = ad._query()
    # Input: DirectSound preferred; pseudo, unnamed and duplicate entries dropped.
    assert result["input"] == ["Microphone (USB Mic)"]
    assert ad._chosen_api["input"] == "directsound"
    # Output: DirectSound is a silent sink, so MME is used, with full display names.
    assert result["output"] == [LONG, "Speakers (Realtek)"]
    assert ad._chosen_api["output"] == "mme"


def test_query_skips_unusable_devices(sd):
    sd(unusable={5, 6})
    assert ad._query()["input"] == ["Microphone (USB Mic)"]
    assert ad._chosen_api["input"] == "mme"


def test_query_never_raises_without_sounddevice(sd, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert ad._query() == {"input": [], "output": []}


def test_list_devices_caches_and_refreshes(sd, monkeypatch):
    sd()
    calls = []
    monkeypatch.setattr(ad, "_query", lambda: calls.append(1) or {"input": ["Mic"], "output": ["Spk"]})
    assert ad.list_devices("input") == ["Mic"]
    assert ad.list_devices("output") == ["Spk"]
    assert len(calls) == 1
    ad.list_devices("input", refresh=True)
    assert len(calls) == 2
    assert ad.list_devices("bogus") == []


def test_list_devices_on_gui_thread_defers_to_prefetch(sd, monkeypatch):
    sd()
    main_thread = object()
    app = SimpleNamespace(thread=lambda: main_thread)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", SimpleNamespace(QThread=SimpleNamespace(currentThread=lambda: main_thread)))
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: app)))
    monkeypatch.setattr(ad, "_query", lambda: pytest.fail("must not query synchronously on the GUI thread"))
    prefetched = []
    monkeypatch.setattr(ad, "prefetch", lambda on_ready=None: prefetched.append(True))
    assert ad.list_devices("input") == []
    assert prefetched == [True]


def test_prefetch_fills_cache_and_calls_back(sd, monkeypatch):
    import threading

    sd()
    done = threading.Event()
    monkeypatch.setattr(ad, "_query", lambda: {"input": ["A"], "output": []})
    ad.prefetch(on_ready=done.set)
    assert done.wait(2)
    assert ad._cache == {"input": ["A"], "output": []}


# ── resolve ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["", "   ", None, ad.DEFAULT_LABEL])
def test_resolve_default_is_none(sd, name):
    assert ad.resolve(name, "input") is None


def test_resolve_exact_name_on_chosen_api(sd):
    sd(fake_sink_apis={DS})
    assert ad.resolve("Speakers (Realtek)", "output") == 3  # MME, the API the picker chose
    assert ad.resolve("Microphone (USB Mic)", "input") == 5  # DirectSound


def test_resolve_long_name_maps_to_truncated_endpoint(sd):
    sd(fake_sink_apis={DS})
    assert ad.resolve(LONG, "output") == 2


def test_resolve_skips_unusable_exact_match(sd):
    sd(unusable={5})
    assert ad.resolve("Microphone (USB Mic)", "input") == 6


def test_resolve_missing_device_falls_back_to_default(sd):
    sd()
    assert ad.resolve("Headset (Jabra)", "input") is None


def test_resolve_error_falls_back_to_default(sd, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert ad.resolve("Microphone (USB Mic)", "input") is None
