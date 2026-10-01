import asyncio
import io
import time
import unittest
import numpy as np
import soundfile as sf
import edge_tts

from core.wake_word import WakeWordDetector


async def _generate_audio(text: str, voice: str) -> np.ndarray:
    comm = edge_tts.Communicate(text, voice)
    data = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            data += chunk["data"]
    audio, sr = sf.read(io.BytesIO(data))
    if sr != 16000:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    return (audio * 32767).astype(np.int16)


class HybridWakeDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generate test audio clips
        cls.alfred_us = asyncio.run(_generate_audio("Alfred", "en-US-GuyNeural"))
        cls.hey_alfred_in = asyncio.run(_generate_audio("Hey Alfred", "en-IN-PrabhatNeural"))

    def test_acoustic_trigger_on_clean_alfred(self):
        detected = []
        detector = WakeWordDetector(
            on_detect=lambda: detected.append(True),
            threshold=0.038,
            logger=lambda m: None,
        )
        self.assertTrue(detector.start())
        try:
            # Feed audio in 1280 sample frames
            for i in range(0, len(self.alfred_us), 1280):
                chunk = self.alfred_us[i:i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                detector.feed(chunk)
                time.sleep(0.01)

            # Wait briefly for detection
            time.sleep(0.2)
            self.assertTrue(len(detected) > 0, "Acoustic detector failed to trigger on 'Alfred'")
        finally:
            detector.stop()

    def test_verifier_trigger_on_hey_alfred_indian_accent(self):
        detected = []
        detector = WakeWordDetector(
            on_detect=lambda: detected.append(True),
            threshold=0.038,
            logger=lambda m: None,
        )
        self.assertTrue(detector.start())
        try:
            # Feed audio in 1280 sample frames
            for i in range(0, len(self.hey_alfred_in), 1280):
                chunk = self.hey_alfred_in[i:i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                detector.feed(chunk)
                time.sleep(0.01)

            # Feed 4 frames of silence to simulate pause after utterance
            silence = np.zeros(1280, dtype=np.int16)
            for _ in range(4):
                detector.feed(silence)
                time.sleep(0.01)

            # Wait up to 2 seconds for verifier thread to finish transcription
            t_end = time.time() + 2.5
            while time.time() < t_end and not detected:
                time.sleep(0.05)

            self.assertTrue(
                len(detected) > 0,
                "Speech verifier failed to trigger on 'Hey Alfred' with Indian accent",
            )
        finally:
            detector.stop()

    def test_multiple_wake_sleep_cycles(self):
        """Verify the detector can trigger repeatedly across multiple sleep/wake cycles."""
        detected_count = 0
        count_box = [0]
        detector = WakeWordDetector(
            on_detect=lambda: count_box.__setitem__(0, count_box[0] + 1),
            threshold=0.038,
            logger=print,
        )
        self.assertTrue(detector.start())
        try:
            silence = np.zeros(1280, dtype=np.int16)

            # Cycle 1: Hey Alfred
            for i in range(0, len(self.hey_alfred_in), 1280):
                chunk = self.hey_alfred_in[i:i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                detector.feed(chunk)
                time.sleep(0.01)
            for _ in range(4):
                detector.feed(silence)
                time.sleep(0.01)

            t_end = time.time() + 4.5
            while time.time() < t_end and count_box[0] < 1:
                time.sleep(0.05)
            self.assertEqual(count_box[0], 1, "Cycle 1 failed to detect")

            # Simulate putting to sleep -> calls reset()
            detector.reset()

            # Cycle 2: Hey Alfred again
            for i in range(0, len(self.hey_alfred_in), 1280):
                chunk = self.hey_alfred_in[i:i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                detector.feed(chunk)
                time.sleep(0.01)
            for _ in range(4):
                detector.feed(silence)
                time.sleep(0.01)

            t_end = time.time() + 4.5
            while time.time() < t_end and count_box[0] < 2:
                time.sleep(0.05)
            self.assertEqual(count_box[0], 2, "Cycle 2 failed to detect after sleep/reset")

            # Simulate putting to sleep -> calls reset()
            detector.reset()

            # Cycle 3: Clean Alfred
            for i in range(0, len(self.alfred_us), 1280):
                chunk = self.alfred_us[i:i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                detector.feed(chunk)
                time.sleep(0.01)

            time.sleep(0.3)
            self.assertEqual(count_box[0], 3, "Cycle 3 failed to detect after sleep/reset")

        finally:
            detector.stop()

    def test_silence_and_low_noise_never_triggers_verifier(self):
        """Verify that silence or ambient background noise never causes hallucination loops or wakeups."""
        detected = []
        detector = WakeWordDetector(
            on_detect=lambda: detected.append(True),
            threshold=0.038,
            logger=lambda m: None,
        )
        self.assertTrue(detector.start())
        try:
            # 1. Feed continuous silence frames
            silence_frame = np.zeros(1280, dtype=np.int16)
            for _ in range(20):
                detector.feed(silence_frame)
                time.sleep(0.01)

            # 2. Feed low-level ambient noise frames (RMS ~ 30)
            noise_frame = np.random.normal(0, 30, 1280).astype(np.int16)
            for _ in range(20):
                detector.feed(noise_frame)
                time.sleep(0.01)

            # Give worker threads time to process
            time.sleep(0.5)
            self.assertEqual(len(detected), 0, "Silence/ambient noise triggered false wakeup")

            # 3. Direct verification of silent burst must not trigger
            silence_burst = np.zeros(16000, dtype=np.int16)
            detector._verify_burst_async(silence_burst, time.perf_counter())
            time.sleep(0.2)
            self.assertEqual(len(detected), 0, "Direct silence burst triggered verifier")

        finally:
            detector.stop()


if __name__ == "__main__":
    unittest.main()

