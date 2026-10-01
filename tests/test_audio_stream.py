"""
tests/test_audio_stream.py — Unit tests for SharedAudioStream, pre-roll circular buffer, and fan-out.
"""

from __future__ import annotations

import queue
import unittest
import numpy as np

from core.audio.stream import (
    SharedAudioStream,
    get_shared_audio_stream,
    SAMPLE_RATE,
    CHUNK_SAMPLES,
    PREROLL_S,
    MAX_SUBSCRIBERS,
)


class TestSharedAudioStream(unittest.TestCase):

    def setUp(self):
        self.stream = SharedAudioStream(
            sample_rate=16000,
            chunk_samples=512,
            preroll_s=1.0,
            max_subscribers=4,
        )

    def test_constants_defined(self):
        self.assertEqual(SAMPLE_RATE, 16000)
        self.assertEqual(CHUNK_SAMPLES, 512)
        self.assertEqual(PREROLL_S, 2.0)
        self.assertEqual(MAX_SUBSCRIBERS, 8)

    def test_subscribe_and_unsubscribe(self):
        q = queue.Queue()
        token = self.stream.subscribe(q)
        self.assertEqual(self.stream.subscriber_count(), 1)

        removed = self.stream.unsubscribe(token)
        self.assertTrue(removed)
        self.assertEqual(self.stream.subscriber_count(), 0)

    def test_max_subscribers_enforced(self):
        tokens = []
        for _ in range(4):
            tokens.append(self.stream.subscribe(lambda b, a: None))
        self.assertEqual(self.stream.subscriber_count(), 4)

        with self.assertRaises(RuntimeError):
            self.stream.subscribe(lambda b, a: None)

        for token in tokens:
            self.stream.unsubscribe(token)

    def test_feed_chunk_fan_out_callback_and_queue(self):
        received_bytes = []
        received_array = []

        def callback(b, a):
            received_bytes.append(b)
            received_array.append(a)

        q = queue.Queue()
        t1 = self.stream.subscribe(callback)
        t2 = self.stream.subscribe(q)

        chunk_arr = np.ones(512, dtype=np.int16) * 42
        self.stream.feed_chunk(chunk_arr)

        self.assertEqual(len(received_bytes), 1)
        self.assertEqual(len(received_array), 1)
        self.assertEqual(received_array[0][0], 42)

        q_item = q.get_nowait()
        self.assertEqual(q_item, chunk_arr.tobytes())

        self.stream.unsubscribe(t1)
        self.stream.unsubscribe(t2)

    def test_preroll_circular_buffer(self):
        # 1.0 second preroll at 16000 Hz with 512 chunks = 31 chunks
        self.assertEqual(len(self.stream.snapshot_preroll()), 0)

        chunk = (np.ones(512, dtype=np.int16)).tobytes()
        for _ in range(50):
            self.stream.feed_chunk(chunk)

        preroll = self.stream.snapshot_preroll()
        # 31 chunks * 1024 bytes per chunk = 31744 bytes
        max_bytes = self.stream._max_preroll_chunks * 512 * 2
        self.assertEqual(len(preroll), max_bytes)

        self.stream.clear_preroll()
        self.assertEqual(len(self.stream.snapshot_preroll()), 0)

    def test_singleton(self):
        s1 = get_shared_audio_stream()
        s2 = get_shared_audio_stream()
        self.assertIs(s1, s2)


if __name__ == "__main__":
    unittest.main()
