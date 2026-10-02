"""
core/wake_word.py — Wake-word detection for ALFRED.

Design:
  - Each WakeWordDetector gets its OWN Model instance (no shared state).
    OpenWakeWord Model.predict() mutates rolling internal buffers — sharing
    a single Model across threads silently corrupts detection.
  - The model is loaded lazily on first detector start, but each detector
    owns its instance so there is no state leakage.
  - The mic callback only does a cheap queue push; all inference runs in the
    dedicated WakeWordThread — the real-time audio path is never blocked.
  - Thread-safe singleton at the JarvisLive level (via self._wake_lock).
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

WAKE_PHRASE = "Alfred"
WAKE_MODEL  = "alfred"
WAKE_MODEL_PATH    = Path(__file__).resolve().parent.parent / "models" / "alfred.onnx"
WAKEWORD_MODEL_PATH = WAKE_MODEL_PATH
AUDIO_BUFFER_SIZE: int   = 1280    # 80 ms at 16 kHz int16 — native OpenWakeWord window
WAKEWORD_TIMEOUT_S: float = 5.0    # Max wait time for detection cycle
WAKE_MODEL_URL = (
    "https://raw.githubusercontent.com/fwartner/"
    "home-assistant-wakewords-collection/main/en/alfred/alfred.onnx"
)
WAKE_MODEL_SHA256 = "6b67237ff9da3bf00cb443438503ef842655263b62323f7da48e3f7c2e81940e"

# Detection sensitivity: 0.038 is calibrated for clean acoustic activations.
DEFAULT_THRESHOLD = 0.038
SAMPLE_RATE = 16000

# Shared speech verifier using faster-whisper for non-US accents & multi-word triggers ("Hey Alfred")
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()


def _get_whisper_verifier():
    """Return a shared WhisperModel instance for speech verification."""
    global _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is None:
            try:
                from faster_whisper import WhisperModel
                _WHISPER_MODEL = WhisperModel(
                    "tiny.en",
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=4,
                )
            except Exception:
                return None
        return _WHISPER_MODEL


def _is_alfred_wake_phrase(text: str) -> bool:
    """Check if transcribed speech contains Alfred or recognized phonetic variants."""
    if not text:
        return False
    clean = re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()
    words = set(clean.split())
    target_words = {"alfred", "alferd", "elfred"}
    if words.intersection(target_words):
        return True
    # Bigram & phonetic variants for natural connected speech
    for phrase in ("al fred", "all fred", "el fred", "he alfred", "hey alfred", "he and fred", "hey and fred"):
        if phrase in clean:
            return True
    return False


def _prewarm_whisper_background() -> None:
    """Prewarm Whisper in background so first verification doesn't stall."""
    try:
        vm = _get_whisper_verifier()
        if vm is not None:
            import numpy as np
            t = np.linspace(0, 0.4, 6400, dtype=np.float32)
            dummy = (np.sin(2 * np.pi * 440 * t) * 0.1).astype(np.float32)
            list(vm.transcribe(dummy, language="en", beam_size=1, temperature=0.0, vad_filter=False)[0])
    except Exception:
        pass


# Prewarm openwakeword modules at import to prevent circular import races across worker threads
try:
    import openwakeword
    import openwakeword.utils
    from openwakeword.model import Model
except Exception:
    pass

_MODEL_INIT_LOCK = threading.Lock()


def _ensure_openwakeword():
    """Ensure openwakeword is completely initialized and attribute-populated."""
    try:
        import openwakeword
        import openwakeword.utils
        if not hasattr(openwakeword, "get_pretrained_model_paths"):
            models = getattr(openwakeword, "MODELS", {})
            def get_pretrained_model_paths(inference_framework="tflite"):
                if inference_framework == "tflite":
                    return [models[i]["model_path"] for i in models.keys()]
                elif inference_framework == "onnx":
                    return [models[i]["model_path"].replace(".tflite", ".onnx") for i in models.keys()]
            openwakeword.get_pretrained_model_paths = get_pretrained_model_paths
        return openwakeword
    except Exception:
        return None


def _make_model():
    """Create a fresh, independent OpenWakeWord Model instance."""
    with _MODEL_INIT_LOCK:
        _ensure_openwakeword()
        from openwakeword.model import Model
        return Model(
            wakeword_models=[str(WAKEWORD_MODEL_PATH)],
            inference_framework="onnx",
        )


get_shared_model = _make_model


def _prediction_score(scores: object) -> float:
    """Return the Alfred score while tolerating backend-specific key suffixes."""
    if not isinstance(scores, dict) or not scores:
        return 0.0
    matches = [float(v) for k, v in scores.items() if WAKE_MODEL in str(k).lower()]
    return max(matches) if matches else max(float(v) for v in scores.values())


def is_installed() -> bool:
    """True if the openwakeword package is importable (no model check)."""
    try:
        import importlib.util
        return importlib.util.find_spec("openwakeword") is not None
    except Exception:
        return False


def is_ready() -> bool:
    """True if openwakeword is installed AND all model files are on disk.

    Deliberately avoids constructing a Model — that is slow and would double
    the initialisation cost when the real detector is already running.
    """
    if not is_installed():
        return False
    try:
        with _MODEL_INIT_LOCK:
            ow = _ensure_openwakeword()
            if ow is None:
                return False
            models_dir = Path(ow.__file__).resolve().parent / "resources" / "models"
            if not models_dir.is_dir():
                return False
            has_wake = WAKE_MODEL_PATH.is_file()
            has_mel  = (any(models_dir.glob("melspectrogram*.onnx"))
                        or any(models_dir.glob("melspectrogram*.tflite")))
            has_emb  = (any(models_dir.glob("embedding_model*.onnx"))
                        or any(models_dir.glob("embedding_model*.tflite")))
            return bool(has_wake and has_mel and has_emb)
    except Exception:
        return False


def install_and_download(logger: Callable[[str], None] = print,
                         notify: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """One-click setup: pip-install openwakeword then download the model."""
    _tell = notify or (lambda _m: None)
    try:
        if not is_installed():
            logger("Wake word: installing openwakeword (one-time)…")
            _tell("Wake word: installing openwakeword (one-time)…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "openwakeword"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
                return False, f"pip install failed: {tail[0][:160]}"
        logger("Wake word: downloading models…")
        _tell("Wake word: downloading models…")
        try:
            import openwakeword.utils as _u
            _u.download_models([WAKE_MODEL])
            if not WAKE_MODEL_PATH.is_file():
                WAKE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                temp_path = WAKE_MODEL_PATH.with_suffix(".download")
                urllib.request.urlretrieve(WAKE_MODEL_URL, temp_path)
                digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
                if digest != WAKE_MODEL_SHA256:
                    temp_path.unlink(missing_ok=True)
                    return False, "Alfred wake model failed its integrity check."
                temp_path.replace(WAKE_MODEL_PATH)
        except Exception as e:
            return False, f"model download failed: {e}"
        if not is_ready():
            return False, "installed, but the wake model could not be loaded."
        logger("Wake word: ready.")
        return True, "Wake word installed and ready."
    except Exception as e:
        return False, f"setup error: {e}"


# Module-level singleton reference (for InterruptDetector.is_triggered() check)
_GLOBAL_DETECTOR: "WakeWordDetector | None" = None


def get_detector() -> "WakeWordDetector | None":
    """Return the currently active WakeWordDetector instance."""
    return _GLOBAL_DETECTOR


class WakeWordDetector:
    """
    Dedicated wake-word inference thread.

    CRITICAL: Each instance creates its OWN Model — never shares a model with
    another detector. OpenWakeWord Model.predict() mutates internal rolling
    state (accumulated_samples, prediction_buffer) so sharing is not safe.

    Public API:
        start()        → load model + begin inference thread
        stop()         → tear down gracefully
        feed(indata)   → called from mic callback (real-time, non-blocking)
        ready          → bool property
        is_triggered() → bool, resets flag (used by InterruptDetector poll)
    """

    def __init__(self,
                 on_detect: Callable[[], None] | None = None,
                 threshold: float = DEFAULT_THRESHOLD,
                 energy_threshold: float = 0.0,
                 logger: Callable[[str], None] = print,
                 notify: Callable[[str], None] | None = None):
        global _GLOBAL_DETECTOR
        # Stop any previous detector before replacing it
        if _GLOBAL_DETECTOR is not None and _GLOBAL_DETECTOR is not self:
            try:
                _GLOBAL_DETECTOR.stop()
            except Exception:
                pass
        _GLOBAL_DETECTOR = self

        self._on_detect        = on_detect or (lambda: None)
        self._threshold        = threshold
        self._energy_threshold = energy_threshold
        self._logger           = logger
        self._notify           = notify or (lambda _m: None)
        self._queue: queue.Queue = queue.Queue(maxsize=60)
        self._thread: threading.Thread | None = None
        self._verifier_executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._lock             = threading.Lock()
        self._running          = False
        self._model            = None
        self._ready            = False
        self._triggered        = False
        self._last_trigger_time: float = 0.0
        self._last_reset_time: float = 0.0
        self._reset_requested: bool = False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Load a fresh Model and spawn the inference thread. Idempotent."""
        with self._lock:
            if self._running:
                return True

        self._logger("Wake word: loading model…")
        try:
            model = get_shared_model()
        except Exception as e:
            self._logger(f"Wake word: could not load model — {e}")
            self._notify("Wake word unavailable — use the WAKE NOW button.")
            return False

        with self._lock:
            if self._running:
                # Another thread raced and won; discard the model we just built
                return True
            self._model   = model
            self._running = True
            self._ready   = True
            self._last_trigger_time = 0.0
            self._reset_requested = False
            self._verifier_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="WakeWordVerifier"
            )
            self._thread  = threading.Thread(
                target=self._loop, daemon=True, name="WakeWordThread"
            )
            self._thread.start()

        # Warm up faster-whisper verifier in the background
        threading.Thread(
            target=_prewarm_whisper_background, daemon=True, name="WakeWordPrewarm"
        ).start()

        self._logger(f"Wake word: listening for '{WAKE_PHRASE}'.")
        return True

    def stop(self) -> None:
        with self._lock:
            if not self._running and not self._ready:
                return
            self._running = False
            self._ready   = False
            self._triggered = False
            self._last_trigger_time = 0.0
        try:
            self._queue.put_nowait(None)          # unblock the blocking get()
        except Exception:
            pass
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.0)
        self._thread = None
        self._model  = None

        ex = self._verifier_executor
        if ex is not None:
            try:
                ex.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._verifier_executor = None

    def reset(self) -> None:
        """Reset trigger latch, cooldown, and burst buffer so detector is immediately ready for next wake phrase."""
        with self._lock:
            self._triggered = False
            self._last_trigger_time = 0.0
            self._last_reset_time = time.monotonic()
            self._reset_requested = True
        self._drain()

    @property
    def ready(self) -> bool:
        return self._ready

    # ── data path (real-time, called from mic callback) ────────────────────────

    def feed(self, frame_int16, timestamp: float | None = None) -> None:
        """Queue a raw mic frame for inference. Non-blocking; drops if backed up."""
        if not self._running:
            return
        try:
            import time as _t
            ts = timestamp if timestamp is not None else _t.perf_counter()
            # Flatten mono array (sounddevice yields shape [N,1])
            data = (frame_int16[:, 0].copy()
                    if getattr(frame_int16, "ndim", 1) > 1
                    else frame_int16.copy())
            self._queue.put_nowait((data, ts))
        except queue.Full:
            # Drop oldest frame and insert fresh one to stay current
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((data, ts))
            except Exception:
                pass
        except Exception:
            pass

    # ── trigger dispatch ──────────────────────────────────────────────────────

    def _trigger_match(self, source: str = "acoustic", latency_ms: float = 0.0) -> None:
        now = time.monotonic()
        with self._lock:
            # Enforce 1.2s cooldown to prevent double firing on the same speech utterance
            if (now - self._last_trigger_time) < 1.2 or not self._running:
                return
            self._last_trigger_time = now
            self._triggered = True
        self._drain()
        try:
            detect_start = time.perf_counter()
            self._on_detect()
            start_latency_ms = (time.perf_counter() - detect_start) * 1000.0
            if start_latency_ms > 20.0:
                self._logger(f"[WakeWord] on_detect dispatch time={start_latency_ms:.1f}ms")
        except Exception as e:
            self._logger(f"Wake word: on_detect error — {e}")

    # ── speech burst verification (runs in worker thread) ─────────────────────

    def _verify_burst_async(self, audio_data, burst_start_ts: float) -> None:
        now = time.monotonic()
        with self._lock:
            if not self._running or (now - self._last_trigger_time) < 1.2:
                return
            if burst_start_ts < self._last_reset_time:
                return
        try:
            import numpy as np
            audio_float = audio_data.astype(np.float32) / 32768.0

            # 1. Pre-verifier validation: reject bursts that are too short or too quiet (silence/pops)
            if len(audio_float) < int(16000 * 0.35):
                return
            burst_rms = float(np.sqrt(np.mean(audio_float ** 2)) * 32768.0)
            if burst_rms < 120.0:
                return

            vm = _get_whisper_verifier()
            if vm is None:
                return
            t0 = time.perf_counter()

            # 2. Transcribe with Silero VAD enabled and focused prompt="Alfred"
            # vad_filter=True and pre-verifier RMS checks completely prevent decoding silence/noise.
            segments, _ = vm.transcribe(
                audio_float,
                language="en",
                beam_size=1,
                temperature=0.0,
                initial_prompt="Alfred",
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=200),
            )

            # 3. Filter hallucinated or non-speech segments
            valid_texts = []
            for s in segments:
                if getattr(s, "no_speech_prob", 0.0) > 0.6:
                    continue
                if getattr(s, "compression_ratio", 1.0) > 2.2:
                    continue
                valid_texts.append(s.text)
            text = " ".join(valid_texts).strip()

            # 4. Anti-hallucination repetition guard: legitimate wake words contain at most 2 mentions
            clean_lower = text.lower()
            if clean_lower.count("alfred") > 2:
                self._logger(f"[WakeWord] Verifier repetition hallucination suppressed ({clean_lower.count('alfred')} occurrences)")
                return

            verif_ms = (time.perf_counter() - t0) * 1000.0
            if _is_alfred_wake_phrase(text):
                total_latency_ms = (time.perf_counter() - burst_start_ts) * 1000.0
                self._logger(
                    f"[WakeWord] Match detected via speech verifier ('{text}') "
                    f"verify_latency={verif_ms:.1f}ms total={total_latency_ms:.1f}ms"
                )
                self._trigger_match(source="verifier", latency_ms=total_latency_ms)
            else:
                if text:
                    self._logger(f"[WakeWord] Candidate burst rejected ('{text}')")
        except Exception as e:
            self._logger(f"[WakeWord] speech verifier error: {e}")

    # ── inference loop (runs in WakeWordThread) ────────────────────────────────

    def _loop(self) -> None:
        import time
        import numpy as np

        last_heartbeat = time.monotonic()
        peak_score_window = 0.0
        rms_window = []

        # Speech burst tracking for hybrid verifier
        noise_floor = 110.0
        in_burst = False
        burst_frames: list[np.ndarray] = []
        silence_count = 0
        burst_start_ts = 0.0
        pre_roll: list[np.ndarray] = []

        while self._running:
            try:
                item = self._queue.get()
                if item is None or not self._running:
                    break
                frame, feed_ts = item if isinstance(item, tuple) else (item, time.perf_counter())

                if self._reset_requested:
                    with self._lock:
                        self._reset_requested = False
                    in_burst = False
                    burst_frames.clear()
                    silence_count = 0
                    pre_roll.clear()

                arr = np.asarray(frame, dtype=np.int16)
                if arr.size == 0:
                    continue

                scores = self._model.predict(arr)
                score  = _prediction_score(scores)

                now = time.monotonic()
                # Fast RMS for real-time mic health telemetry
                rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                rms_window.append(rms)
                if score > peak_score_window:
                    peak_score_window = score

                if (now - last_heartbeat) >= 4.0:
                    avg_rms = sum(rms_window) / len(rms_window) if rms_window else 0.0
                    self._logger(
                        f"[WakeWord] listening for '{WAKE_PHRASE}' | mic_rms={avg_rms:.0f} "
                        f"| peak_score_4s={peak_score_window:.3f} | threshold={self._threshold:.3f}"
                    )
                    last_heartbeat = now
                    peak_score_window = 0.0
                    rms_window.clear()

                if score >= 0.02:
                    self._logger(
                        f"[WakeWord] candidate score={score:.3f} "
                        f"(threshold={self._threshold:.3f})"
                    )

                # High acoustic match -> immediate fast trigger
                if score >= self._threshold:
                    gate_latency_ms = (time.perf_counter() - feed_ts) * 1000.0
                    self._logger(
                        f"[WakeWord] Match detected (score={score:.2f}) "
                        f"gate_latency={gate_latency_ms:.1f}ms"
                    )
                    self._trigger_match(source="acoustic", latency_ms=gate_latency_ms)
                    in_burst = False
                    burst_frames.clear()
                    silence_count = 0
                    continue

                # Hybrid Speech Verifier: buffer speech bursts
                if not in_burst:
                    noise_floor = 0.98 * noise_floor + 0.02 * min(rms, 250.0)

                speech_thresh = (
                    self._energy_threshold
                    if self._energy_threshold > 0.0
                    else max(160.0, noise_floor * 1.45)
                )
                is_speech = rms >= speech_thresh

                if is_speech:
                    if not in_burst:
                        in_burst = True
                        burst_start_ts = feed_ts
                        burst_frames = list(pre_roll)
                        silence_count = 0
                    burst_frames.append(arr)
                    silence_count = 0

                    if len(burst_frames) > 40:  # > 3.2s
                        in_burst = False
                        burst_frames.clear()
                        silence_count = 0
                else:
                    if in_burst:
                        silence_count += 1
                        burst_frames.append(arr)
                        if silence_count >= 3:  # ~240ms silence pause
                            dur_s = len(burst_frames) * 0.08
                            if 0.35 <= dur_s <= 3.0:
                                concat_audio = np.concatenate(burst_frames)
                                max_frame_rms = max(float(np.sqrt(np.mean(f.astype(np.float32) ** 2))) for f in burst_frames)
                                if max_frame_rms >= max(140.0, noise_floor * 1.3):
                                    ex = self._verifier_executor
                                    with self._lock:
                                        in_cooldown = (time.monotonic() - self._last_trigger_time) < 1.2
                                    if ex is not None and not in_cooldown:
                                        ex.submit(
                                            self._verify_burst_async, concat_audio, burst_start_ts
                                        )
                            in_burst = False
                            burst_frames.clear()
                            silence_count = 0

                pre_roll.append(arr)
                if len(pre_roll) > 2:
                    pre_roll.pop(0)

            except Exception as e:
                self._logger(f"Wake word: inference error — {e}")

    def is_triggered(self) -> bool:
        """Consume and return the trigger flag (used by InterruptDetector poll)."""
        with self._lock:
            if self._triggered:
                self._triggered = False
                return True
            return False

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass
