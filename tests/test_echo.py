"""Behavioural tests for core.echo (band energies + EchoGuard echo/voice classifier)."""
from __future__ import annotations

import numpy as np
import pytest

from core import echo
from core.echo import EchoGuard, band_energies

SR_MIC, SR_OUT = 16000, 24000


def tone(freqs, sr, n=1024, amp=0.5):
    t = np.arange(n) / sr
    return sum(amp * np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32)


OUR_VOICE = (300, 900, 1400)      # bands 0, 2, 3
OTHER_VOICE = (2000, 3000, 4500)  # bands 4, 5, 6


# ── band_energies ────────────────────────────────────────────────────────────

def test_short_block_gives_zeros():
    out = band_energies(np.ones(10), SR_MIC)
    assert out.shape == (len(echo._BAND_EDGES) - 1,) and not out.any()


def test_tone_lands_in_its_band():
    assert int(np.argmax(band_energies(tone([1000], SR_MIC), SR_MIC))) == 2  # 700–1100 Hz
    assert int(np.argmax(band_energies(tone([6000], SR_MIC), SR_MIC))) == 7  # 5200–7000 Hz


def test_dc_offset_removed():
    assert band_energies(np.full(512, 0.7), SR_MIC).sum() == pytest.approx(0.0, abs=1e-3)


def test_fingerprint_is_sample_rate_agnostic():
    a = band_energies(tone(OUR_VOICE, SR_MIC, 1024), SR_MIC)
    b = band_energies(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert cos > 0.95


# ── EchoGuard ────────────────────────────────────────────────────────────────

def test_initial_state():
    g = EchoGuard()
    assert g.gain == pytest.approx(0.6)
    assert g.calibrated is False and g.reliable is True
    assert g.threshold == pytest.approx(max(echo._MIN_USER, 0.13 * echo._HEAD_MULT))
    assert g.required_blocks == echo._BLOCKS_NORMAL


def test_quiet_mic_is_never_speech():
    assert EchoGuard().is_user_speech(tone(OTHER_VOICE, SR_MIC), SR_MIC, level=0.01) is False


def test_nothing_playing_means_audible_is_user():
    assert EchoGuard().is_user_speech(tone(OTHER_VOICE, SR_MIC), SR_MIC, level=0.3) is True


def test_silent_block_with_history_is_not_speech():
    g = EchoGuard()
    g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=10.0)
    assert g.is_user_speech(np.zeros(1024), SR_MIC, level=0.3, when=10.1) is False


def _warm(g, t0=10.0, blocks=echo._WARMUP):
    out = tone(OUR_VOICE, SR_OUT, 1536)
    mic = tone(OUR_VOICE, SR_MIC, 1024, amp=0.25)
    results = []
    for i in range(blocks):
        t = t0 + i * 0.05
        g.note_output(out, SR_OUT, level=0.5, when=t)
        results.append(g.is_user_speech(mic, SR_MIC, level=0.3, when=t + 0.02))
    return results, t0 + blocks * 0.05


def test_echo_never_speech_and_warmup_then_voice_detected():
    g = EchoGuard()
    results, t = _warm(g)
    assert results == [False] * echo._WARMUP
    assert g.last_similarity > 0.8
    g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=t)
    assert g.is_user_speech(tone(OTHER_VOICE, SR_MIC), SR_MIC, level=0.3, when=t + 0.02) is True
    assert g.last_similarity < 0.5


def test_voice_during_warmup_is_not_trusted():
    g = EchoGuard()
    g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=10.0)
    assert g.is_user_speech(tone(OTHER_VOICE, SR_MIC), SR_MIC, level=0.3, when=10.02) is False


def test_gain_learns_from_confident_echo():
    g = EchoGuard()
    _, t = _warm(g, blocks=echo._WARMUP + 10)
    assert g.calibrated is True
    # mic level 0.3 vs output 0.5 → observed 0.6; started at 0.6 so it stays put.
    assert g.gain == pytest.approx(0.6, abs=1e-6)


def test_gain_moves_toward_observed_ratio():
    g = EchoGuard()
    _warm(g)
    out = tone(OUR_VOICE, SR_OUT, 1536)
    mic = tone(OUR_VOICE, SR_MIC, 1024, amp=0.25)
    for i in range(10):
        t = 20.0 + i * 0.05
        g.note_output(out, SR_OUT, level=0.2, when=t)
        g.is_user_speech(mic, SR_MIC, level=0.4, when=t + 0.02)  # observed ratio 2.0
    assert 0.6 < g.gain < 2.0


def test_long_run_of_speech_triggers_relearn():
    g = EchoGuard()
    _, t = _warm(g)
    out, voice = tone(OUR_VOICE, SR_OUT, 1536), tone(OTHER_VOICE, SR_MIC)
    results = []
    for i in range(echo._RELEARN_RUN + 1):
        tt = t + i * 0.05
        g.note_output(out, SR_OUT, level=0.5, when=tt)
        results.append(g.is_user_speech(voice, SR_MIC, level=0.3, when=tt + 0.02))
    assert results[:-1] == [True] * echo._RELEARN_RUN
    assert results[-1] is False
    assert g._residuals == []  # room is re-characterised from scratch


def test_out_of_window_history_ignored():
    g = EchoGuard()
    g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=0.0)
    # Output is 5 s old (beyond _HISTORY_S): nothing explains the mic block.
    assert g.is_user_speech(tone(OUR_VOICE, SR_MIC), SR_MIC, level=0.3, when=5.0) is True


def test_history_pruned_after_eight_entries():
    g = EchoGuard()
    for i in range(12):
        g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=float(i))
    # Pruning is lazy (only once >8 entries) but stale slices must be gone.
    times = [h[0] for h in g._hist]
    assert len(times) <= 8 and 0.0 not in times and times[-1] == 11.0


def test_quiet_mic_with_loud_playback_learns_zero_echo_room():
    g = EchoGuard()
    g.note_output(tone(OUR_VOICE, SR_OUT, 1536), SR_OUT, level=0.5, when=1.0)
    for _ in range(echo._WARMUP):
        assert g.is_user_speech(np.zeros(1024), SR_MIC, level=0.0, when=1.1) is False
    assert g.floor == 0.0 and g.reliable is True
    assert g.threshold == pytest.approx(echo._MIN_USER)


def test_unreliable_room_requires_more_blocks():
    g = EchoGuard()
    g._floor = echo._UNRELIABLE_FLOOR + 0.01
    assert g.reliable is False and g.required_blocks == echo._BLOCKS_NOISY


def test_reset_clears_history_but_keeps_learning():
    g = EchoGuard()
    _warm(g)
    floor = g.floor
    g.reset()
    assert g._hist == [] and g.last_similarity == 0.0 and g.floor == floor


def test_errors_never_raise():
    g = EchoGuard()
    g.note_output(object(), SR_OUT, level="bad")  # swallowed
    g._hist.append((1.0, "garbage", 0.5))
    assert g.is_user_speech(tone(OUR_VOICE, SR_MIC), SR_MIC, level=0.3, when=1.1) is False
