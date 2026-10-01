"""
tests/test_audio_gate.py — Unit tests for AudioGate additive gating, hold/release, and delay.
"""

from __future__ import annotations

import time
import unittest

from core.audio.gate import (
    AudioGate,
    GATE_TTS,
    GATE_MEDIA,
    GATE_AUTOMATION,
    GATE_RESOLVING,
    get_audio_gate,
)


class TestAudioGate(unittest.TestCase):

    def setUp(self):
        self.gate = AudioGate(release_delay_ms=50)

    def test_initially_open(self):
        self.assertTrue(self.gate.is_open())
        self.assertEqual(len(self.gate.active_reasons()), 0)

    def test_single_reason_blocks_gate(self):
        self.gate.hold(GATE_TTS)
        self.assertFalse(self.gate.is_open())
        self.assertTrue(self.gate.is_reason_held(GATE_TTS))
        self.assertFalse(self.gate.is_reason_held(GATE_MEDIA))

    def test_additive_multiple_reasons(self):
        self.gate.hold(GATE_TTS)
        self.gate.hold(GATE_MEDIA)
        self.assertFalse(self.gate.is_open())
        self.assertEqual(self.gate.active_reasons(), {GATE_TTS, GATE_MEDIA})

        # Releasing one still leaves gate closed
        self.gate.release(GATE_TTS)
        self.assertFalse(self.gate.is_open())
        self.assertFalse(self.gate.is_reason_held(GATE_TTS))
        self.assertTrue(self.gate.is_reason_held(GATE_MEDIA))

    def test_release_delay_tail(self):
        self.gate.hold(GATE_AUTOMATION)
        self.gate.release(GATE_AUTOMATION)
        # Immediately after release, gate is in release tail cooldown
        self.assertFalse(self.gate.is_open())
        # Wait for 50ms release delay
        time.sleep(0.07)
        self.assertTrue(self.gate.is_open())

    def test_context_manager_holding(self):
        with self.gate.holding(GATE_RESOLVING):
            self.assertTrue(self.gate.is_reason_held(GATE_RESOLVING))
            self.assertFalse(self.gate.is_open())
        self.assertFalse(self.gate.is_reason_held(GATE_RESOLVING))

    def test_reset(self):
        self.gate.hold(GATE_TTS)
        self.gate.hold(GATE_MEDIA)
        self.gate.reset()
        self.assertTrue(self.gate.is_open())
        self.assertEqual(len(self.gate.active_reasons()), 0)

    def test_singleton(self):
        g1 = get_audio_gate()
        g2 = get_audio_gate()
        self.assertIs(g1, g2)


if __name__ == "__main__":
    unittest.main()
