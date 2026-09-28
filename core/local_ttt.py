"""
Local Text-to-Speech wrappers for MARK XL.
Provides unified interface for Kokoro, EdgeTTS, and ElevenLabs TTS engines.
"""

import threading
import queue
import time
from typing import Optional, Callable
import numpy as np

from core.tts import (
    KokoroTTSEngine,
    EdgeTTSEngine,
    ElevenLabsTTSEngine,
    TTSPlayer,
    create_tts_player
)


class LocalTTSManager:
    """Manages local text-to-speech synthesis with streaming capabilities."""

    def __init__(self, config: dict):
        self.config = config
        self.engine_name = config.get("tts_engine", "kokoro").lower()
        self.voice = config.get("tts_voice", "af_heart")
        self.speed = float(config.get("tts_speed", 1.0))

        # Create the appropriate TTS engine
        tts_config = {
            "tts_engine": self.engine_name,
            "tts_voice": self.voice,
            "tts_speed": self.speed
        }

        try:
            self.tts_engine = create_tts_player(tts_config)
        except Exception as e:
            print(f"[LocalTTS] Failed to initialize {self.engine_name} engine: {e}")
            # Fallback to Kokoro if specified engine fails
            if self.engine_name != "kokoro":
                print("[LocalTTS] Falling back to Kokoro engine")
                fallback_config = {
                    "tts_engine": "kokoro",
                    "tts_voice": "af_heart",
                    "tts_speed": 1.0
                }
                self.tts_engine = create_tts_player(fallback_config)
                self.engine_name = "kokoro"
            else:
                raise

        # Queues for streaming
        self.text_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.is_speaking = False
        self.speak_thread = None
        self._stop_event = threading.Event()

        # Sentence boundary detection for smoother streaming
        import re
        self._sent_end = re.compile(r'(?<=[.!?])\s+|(?<=\n)\s*\n')
        self._text_buffer = ""

    def start(self):
        """Start the TTS processing thread."""
        if self.is_speaking:
            return

        self.is_speaking = True
        self._stop_event.clear()
        self.speak_thread = threading.Thread(
            target=self._speak_loop,
            daemon=True
        )
        self.speak_thread.start()

    def stop(self):
        """Stop the TTS processing thread."""
        self.is_speaking = False
        self._stop_event.set()
        if self.speak_thread:
            self.speak_thread.join(timeout=1.0)
        # Also stop the underlying TTS player
        self.tts_engine.stop()

    def speak_text(self, text: str):
        """Add text to be spoken (non-blocking)."""
        if not text or not text.strip():
            return

        self.text_queue.put(text.strip())

    def speak_sentence(self, sentence: str):
        """Add a sentence to be spoken, with sentence boundary detection."""
        if not sentence:
            return

        self._text_buffer += sentence + " "

        # Check for sentence boundaries
        while True:
            match = self._sent_end.search(self._text_buffer)
            if not match:
                break
            sentence = self._text_buffer[:match.end()].strip()
            self._text_buffer = self._text_buffer[match.end():]

            if sentence:
                self.text_queue.put(sentence)

    def flush(self):
        """Flush any remaining text in buffer."""
        if self._text_buffer.strip():
            self.text_queue.put(self._text_buffer.strip())
            self._text_buffer = ""

    def _speak_loop(self):
        """Main loop for processing text queue and speaking."""
        while not self._stop_event.is_set():
            try:
                # Get text with timeout to allow checking stop event
                text = self.text_queue.get(timeout=0.1)

                if text:  # Speak the text
                    self.tts_engine.speak(text)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[LocalTTS] Speech error: {e}")
                # Continue processing other items

        # Flush any remaining text when stopping
        self.flush()


def create_local_tts_engine(config: dict) -> LocalTTSManager:
    """Factory function to create a local TTS manager."""
    return LocalTTSManager(config)