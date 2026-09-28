"""
Local Speech-to-Text wrappers for MARK XL.
Provides unified interface for Whisper and Vosk STT engines.
"""

import numpy as np
import queue
import threading
import time
from typing import Optional, Callable

# ── Speech-finalisation debounce ──────────────────────────────────────────────
# Vosk fires a "final" result every time the user pauses, even mid-sentence.
# Instead of dispatching immediately, accumulate finals and wait FINISH_MS for
# more speech. If the timer fires without new input the full sentence is sent.
# Short interrupt words (single word, in _INTERRUPT_WORDS) skip this entirely
# and fire at once.
FINISH_MS = 900          # milliseconds to wait before committing a sentence

_INTERRUPT_WORDS: frozenset[str] = frozenset({
    "stop", "wait", "pause", "cancel", "abort", "halt",
    "quiet", "silence", "enough", "nevermind", "shh",
})

from core.stt import WhisperSTT, VoskSTT


class LocalSTTManager:
    """Manages local speech-to-text transcription with streaming capabilities."""

    def __init__(self, config: dict):
        engine = config.get("stt_engine", "whisper").lower()
        model = config.get("stt_model", "base")
        language = config.get("stt_language")

        self.config = config
        self.engine = engine

        if engine == "vosk":
            self.stt = VoskSTT(model_path=model, language=language or "en-us")
        else:  # whisper default
            self.stt = WhisperSTT(model_name=model, language=language)

        self.sample_rate = 16000
        self.chunk_size = 1024
        self.is_listening = False
        self.listen_thread = None

        # For Whisper batch processing
        self.audio_buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.silence_threshold = config.get("stt_silence_threshold", 0.01)
        self.min_silence_chunks = config.get("stt_min_silence_chunks", 10)
        self.silence_counter = 0

        # Callback for audio data (from microphone)
        self.audio_callback = None

        # Transcription results
        self.transcript_queue = queue.Queue()
        self.partial_transcript = ""

        # ── FINISH_MS speech debounce state (Vosk path) ───────────────────────
        # _speech_buf accumulates final chunks; _finish_timer fires after
        # FINISH_MS of silence and commits the full accumulated sentence.
        self._speech_buf: list[str] = []
        self._finish_timer: threading.Timer | None = None
        self._speech_buf_lock = threading.Lock()

    def set_audio_callback(self, callback: Optional[Callable[[bytes], None]]):
        """Set callback to receive raw audio data."""
        self.audio_callback = callback

    def start_listening(self):
        """Start processing audio from microphone."""
        if self.is_listening:
            return

        self.is_listening = True
        self.listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )
        self.listen_thread.start()

    def stop_listening(self):
        """Stop audio processing."""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=1.0)

    def _listen_loop(self):
        """Continuously process audio chunks from microphone."""
        import sounddevice as sd

        def audio_callback_wrapper(indata, frames, time_info, status):
            if not self.is_listening:
                return

            # Convert to mono if needed
            if indata.shape[1] > 1:
                audio = np.mean(indata, axis=1)
            else:
                audio = indata[:, 0]

            # Convert to int16 bytes
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # Send to audio callback if set
            if self.audio_callback:
                self.audio_callback(audio_bytes)

            # Process for transcription
            self._process_audio_bytes(audio_bytes)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.chunk_size,
                callback=audio_callback_wrapper
            ):
                while self.is_listening:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[LocalSTT] Audio stream error: {e}")

    def _process_audio_bytes(self, audio_bytes: bytes):
        """Process audio bytes for transcription based on engine type."""
        if self.engine == "vosk":
            self._process_vosk_audio(audio_bytes)
        else:  # whisper
            self._process_whisper_audio(audio_bytes)

    # ── FINISH_MS helpers ────────────────────────────────────────────────────

    def _cancel_finish_timer(self) -> None:
        """Cancel any pending debounce timer, thread-safe."""
        with self._speech_buf_lock:
            t = self._finish_timer
            self._finish_timer = None
        if t is not None:
            t.cancel()

    def _restart_finish_timer(self) -> None:
        """Reset the FINISH_MS countdown from zero."""
        with self._speech_buf_lock:
            t = self._finish_timer
            self._finish_timer = threading.Timer(
                FINISH_MS / 1000.0, self._on_finish_timer
            )
            self._finish_timer.daemon = True
            self._finish_timer.start()
        if t is not None:
            t.cancel()

    def _on_finish_timer(self) -> None:
        """Timer callback: commit the accumulated sentence to the queue."""
        with self._speech_buf_lock:
            self._finish_timer = None
            sentence = " ".join(self._speech_buf).strip()
            self._speech_buf.clear()
        if sentence:
            self.transcript_queue.put(sentence)
            self.partial_transcript = ""

    def _flush_speech_buffer(self, extra: str = "") -> None:
        """Immediately commit whatever is in the buffer (+ optional extra word)."""
        with self._speech_buf_lock:
            parts = list(self._speech_buf)
            self._speech_buf.clear()
        if extra:
            parts.append(extra)
        sentence = " ".join(parts).strip()
        if sentence:
            self.transcript_queue.put(sentence)
            self.partial_transcript = ""

    # ── Vosk streaming handler ───────────────────────────────────────────────

    def _process_vosk_audio(self, audio_bytes: bytes):
        """Process audio using Vosk streaming STT.

        Final results are held for FINISH_MS before dispatch so that
        mid-sentence pauses do not fragment the user's thought.
        Single-word interrupt commands bypass the buffer and fire at once.
        """
        try:
            text, is_final = self.stt.process_chunk(audio_bytes)
            if is_final and text.strip():
                word = text.strip()
                # Short interrupt words bypass the buffer and fire instantly
                if word.lower() in _INTERRUPT_WORDS and " " not in word:
                    self._cancel_finish_timer()
                    self._flush_speech_buffer(extra=word)
                else:
                    with self._speech_buf_lock:
                        self._speech_buf.append(word)
                    self._restart_finish_timer()
                self.partial_transcript = ""
            elif text.strip():
                self.partial_transcript = text.strip()
        except Exception as e:
            print(f"[LocalSTT] Vosk transcription error: {e}")

    def _process_whisper_audio(self, audio_bytes: bytes):
        """Process audio using Whisper with batch accumulation and VAD."""
        try:
            # Convert bytes to numpy array for energy calculation
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Calculate energy (simple VAD)
            energy = np.sqrt(np.mean(audio_np ** 2))

            with self.buffer_lock:
                self.audio_buffer.extend(audio_bytes)

                if energy < self.silence_threshold:
                    self.silence_counter += 1
                else:
                    self.silence_counter = 0

                # If we have enough silence after speech, process utterance
                if (self.silence_counter > self.min_silence_chunks and
                    len(self.audio_buffer) > self.sample_rate * 0.5):  # Minimum 0.5 seconds of audio
                    self._process_whisper_buffer()

        except Exception as e:
            print(f"[LocalSTT] Whisper processing error: {e}")

    def _process_whisper_buffer(self):
        """Process accumulated Whisper audio buffer."""
        with self.buffer_lock:
            if len(self.audio_buffer) == 0:
                return

            audio_data = bytes(self.audio_buffer)
            self.audio_buffer = bytearray()
            self.silence_counter = 0

        try:
            # Convert to float32 numpy array for Whisper
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Transcribe using Whisper
            text = self.stt.transcribe(audio_np)

            if text and text.strip():
                self.transcript_queue.put(text.strip())

        except Exception as e:
            print(f"[LocalSTT] Whisper transcription error: {e}")

    def get_transcription(self, timeout: float = 0.1) -> Optional[str]:
        """Get latest transcription if available."""
        try:
            return self.transcript_queue.get_nowait()
        except queue.Empty:
            return None

    def get_partial_transcription(self) -> str:
        """Get current partial transcription (for Vosk)."""
        return self.partial_transcript

    def flush(self):
        """Flush any remaining audio buffer (for Whisper)."""
        if self.engine == "whisper":
            with self.buffer_lock:
                if len(self.audio_buffer) > 0:
                    self._process_whisper_buffer()


def create_local_stt_engine(config: dict) -> LocalSTTManager:
    """Factory function to create a local STT manager."""
    return LocalSTTManager(config)