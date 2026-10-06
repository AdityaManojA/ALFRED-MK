"""
Default Text-to-Speech engines for ALFRED.

EdgeTTS     – free Microsoft TTS (internet required, no API key)
Kokoro      – fully offline neural TTS (~330 MB model)
ElevenLabs  – cloud API (API key required, best quality)

Wraps the legacy engines behind the TTSEngine interface with zero behaviour change.
"""
from __future__ import annotations

import asyncio
import os
import queue as _queue
import threading
from typing import Callable, Optional

import numpy as np
try:
    import sounddevice as sd
except OSError as e:
    from core.audio_portaudio import handle_portaudio_os_error
    handle_portaudio_os_error(e)
    raise

from core.tts.engine_base import Capability, TTSEngine

# USE_TF=0 stops transformers from importing TensorFlow (saves 4-8 s startup).
os.environ.setdefault("USE_TF",                 "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# ---------------------------------------------------------------------------
# Audio playback helpers
# ---------------------------------------------------------------------------

def _to_numpy(samples) -> np.ndarray:
    """Convert samples to float32 numpy array.

    Handles both numpy arrays and PyTorch tensors (Kokoro >= 0.9).
    """
    if hasattr(samples, "detach"):                  # PyTorch tensor
        t = samples.detach().cpu().float()
        try:
            return t.numpy()                        # fast path (compatible versions)
        except RuntimeError:
            return np.asarray(t.tolist(), dtype=np.float32)
    return np.asarray(samples, dtype=np.float32)


def _compress_silence(
    arr: np.ndarray,
    sample_rate: int    = 24_000,
    max_silence_ms: int = 500,    # cap punctuation pauses — keeps natural rhythm
    threshold: float    = 0.003,  # RMS below this = silence; lower = less clipping
) -> np.ndarray:
    """Shorten Kokoro's very long punctuation pauses (1-2 s → ≤500 ms)."""
    max_samp  = int(max_silence_ms * sample_rate / 1000)
    frame_len = 240                   # ~10 ms at 24 kHz
    out: list[np.ndarray] = []
    silent_acc = 0

    for i in range(0, len(arr), frame_len):
        chunk = arr[i : i + frame_len]
        if np.sqrt(np.mean(chunk ** 2) + 1e-12) < threshold:
            silent_acc += len(chunk)
            if silent_acc <= max_samp:
                out.append(chunk)
        else:
            silent_acc = 0
            out.append(chunk)

    return np.concatenate(out) if out else arr


def _get_output_device_idx() -> int | None:
    """Resolve configured output device index from config, or None for system default."""
    try:
        from memory.config_manager import get_output_device
        from core import audio_devices
        out_name = get_output_device()
        if out_name:
            return audio_devices.resolve(out_name, "output")
    except Exception:
        pass
    return None


def _play_np(samples, sample_rate: int) -> None:
    """Play float32 mono (or stereo) audio via sounddevice using configured output device."""
    dev_idx = _get_output_device_idx()
    arr = _to_numpy(samples)
    try:
        sd.play(arr, sample_rate, device=dev_idx)
        sd.wait()
    except Exception as e:
        print(f"[TTS] [ERROR] Audio playback failed on device {dev_idx}: {e}")
        if dev_idx is not None:
            try:
                print("[TTS] [INFO] Retrying playback on system default output device...")
                sd.play(arr, sample_rate, device=None)
                sd.wait()
            except Exception as e2:
                print(f"[TTS] [ERROR] Default output retry also failed: {e2}")


def _play_audio_bytes(audio_bytes: bytes) -> None:
    """Decode MP3/WAV/OGG bytes and play via sounddevice (uses soundfile / miniaudio / av)."""
    samples = None
    sample_rate = 24000

    # 1. Try soundfile (standard libsndfile with built-in MP3 support)
    try:
        import io
        import soundfile as sf
        samples, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if samples.ndim > 1:
            samples = samples.mean(axis=1)  # convert to mono
    except Exception:
        samples = None

    # 2. Fallback to miniaudio if available
    if samples is None:
        try:
            import miniaudio
            decoded = miniaudio.decode(
                audio_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
            )
            samples = np.array(decoded.samples, dtype=np.float32)
            sample_rate = decoded.sample_rate
        except Exception:
            samples = None

    # 3. Fallback to PyAV (av)
    if samples is None:
        try:
            import av
            import io
            container = av.open(io.BytesIO(audio_bytes))
            chunks = []
            for frame in container.decode(audio=0):
                chunks.append(frame.to_ndarray())
            if chunks:
                raw_np = np.concatenate(chunks, axis=1)
                samples = raw_np.mean(axis=0).astype(np.float32)
                sample_rate = container.streams.audio[0].rate
        except Exception:
            samples = None

    if samples is None:
        print(f"[TTS] [ERROR] Audio decoding failed ({len(audio_bytes)} bytes): no supported decoder available")
        return

    dev_idx = _get_output_device_idx()
    try:
        sd.play(samples, sample_rate, device=dev_idx)
        sd.wait()
    except Exception as e:
        print(f"[TTS] [ERROR] Audio playback failed on device {dev_idx}: {e}")
        if dev_idx is not None:
            try:
                print("[TTS] [INFO] Retrying playback on system default output device...")
                sd.play(samples, sample_rate, device=None)
                sd.wait()
            except Exception as e2:
                print(f"[TTS] [ERROR] Default output retry also failed: {e2}")


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

class EdgeTTSEngine:
    """Microsoft EdgeTTS – free, requires internet."""

    def __init__(self, voice: str = "en-US-GuyNeural"):
        self.voice = voice

    def speak(self, text: str) -> None:
        loop = asyncio.new_event_loop()
        try:
            print(f"[TTS] [EdgeTTS] Synthesizing speech with voice '{self.voice}': \"{text[:60]}...\"")
            audio_bytes = loop.run_until_complete(self._synth(text))
        except Exception as e:
            print(f"[TTS] [EdgeTTS] [ERROR] Synthesis failed: {e}")
            audio_bytes = None
        finally:
            loop.close()
        if audio_bytes:
            print(f"[TTS] [EdgeTTS] Generated {len(audio_bytes)} bytes. Playing audio...")
            _play_audio_bytes(audio_bytes)
            print("[TTS] [EdgeTTS] Playback finished.")
        else:
            print(f"[TTS] [EdgeTTS] [WARN] No audio returned for text: \"{text[:40]}\"")

    async def _synth(self, text: str) -> bytes:
        import edge_tts
        comm = edge_tts.Communicate(text, self.voice)
        buf  = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)


# ---------------------------------------------------------------------------
# Kokoro import helper — auto-upgrades on version-mismatch errors
# ---------------------------------------------------------------------------

_KOKORO_COMPAT_ERRORS = ("AlbertModel", "AutoModel", "cannot import name")


def _import_kokoro_pipeline():
    """Import KPipeline, auto-upgrading kokoro if a version mismatch is found."""
    import sys

    def _try_import():
        from kokoro import KPipeline  # noqa: PLC0415
        return KPipeline

    try:
        return _try_import()
    except Exception as first_err:
        err_msg = str(first_err)
        if not any(marker in err_msg for marker in _KOKORO_COMPAT_ERRORS):
            raise RuntimeError(
                f"Kokoro import failed: {first_err}\n"
                "Run: pip install kokoro>=0.9 soundfile"
            ) from first_err

        print("[TTS] Kokoro/transformers version mismatch detected — upgrading kokoro…")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "kokoro>=0.9",
             "--upgrade", "--quiet", "--disable-pip-version-check"],
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"Kokoro auto-upgrade failed: {stderr[:200]}\n"
                "Run manually: pip install kokoro>=0.9 soundfile"
            ) from first_err

        stale = [k for k in sys.modules if k == "kokoro" or k.startswith("kokoro.")]
        for key in stale:
            del sys.modules[key]

        print("[TTS] Kokoro upgraded — retrying import…")
        try:
            return _try_import()
        except Exception as retry_err:
            raise RuntimeError(
                f"Kokoro still broken after upgrade: {retry_err}\n"
                "Run manually: pip install --upgrade kokoro transformers"
            ) from retry_err


_KOKORO_LANG_CODES = {
    "a": "a",   # American English
    "b": "b",   # British English
    "j": "j",   # Japanese
    "z": "z",   # Mandarin Chinese
    "s": "s",   # Spanish
    "f": "f",   # French
    "h": "h",   # Hindi
    "i": "i",   # Italian
    "p": "p",   # Brazilian Portuguese
    "r": "r",   # Russian
    "e": "e",   # German
}


class KokoroTTSEngine:
    """Fully offline Kokoro neural TTS."""

    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        self.voice     = voice
        self.speed     = speed
        self._pipeline = None
        self._lock     = threading.Lock()
        self._init()

    @property
    def _lang_code(self) -> str:
        prefix = self.voice[0].lower() if self.voice else "a"
        return _KOKORO_LANG_CODES.get(prefix, "a")

    def _init(self) -> None:
        if self._pipeline is not None:
            return

        lang = self._lang_code

        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                import os as _os
                n_threads = max(1, min(4, (_os.cpu_count() or 4) // 2))
                try:
                    torch.set_num_threads(n_threads)
                    torch.set_num_interop_threads(2)
                except RuntimeError:
                    pass
        except Exception:
            device = "cpu"

        KPipeline = _import_kokoro_pipeline()

        def _create_pipeline():
            try:
                return KPipeline(lang_code=lang, device=device)
            except TypeError:
                return KPipeline(lang_code=lang)

        try:
            self._pipeline = _create_pipeline()
        except Exception as _first_err:
            _e = str(_first_err).lower()
            _offline_keywords = (
                "offline", "not found", "cache", "localentry",
                "does not exist", "outgoing", "local_files_only",
            )
            if any(k in _e for k in _offline_keywords):
                os.environ.pop("HF_HUB_OFFLINE",      None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
                os.environ.pop("HF_DATASETS_OFFLINE",  None)
                self._pipeline = _create_pipeline()
            else:
                raise

        try:
            for _ in self._pipeline("hello", voice=self.voice, speed=self.speed):
                pass
        except Exception as e:
            print(f"[TTS] Kokoro warmup warning: {e}")

    def speak(self, text: str) -> None:
        with self._lock:
            if self._pipeline is None:
                self._init()

        audio_q: "_queue.Queue[np.ndarray | None]" = _queue.Queue(maxsize=4)
        synth_error: list[Exception] = []

        def _synth():
            try:
                for _, _, audio in self._pipeline(text, voice=self.voice, speed=self.speed):
                    if audio is not None:
                        arr = _to_numpy(audio)
                        arr = _compress_silence(arr)
                        if arr.size > 0:
                            audio_q.put(arr)
            except Exception as exc:
                synth_error.append(exc)
            finally:
                audio_q.put(None)

        synth_thread = threading.Thread(target=_synth, daemon=True)
        synth_thread.start()

        while True:
            arr = audio_q.get()
            if arr is None:
                break
            _play_np(arr, 24000)

        synth_thread.join()

        if synth_error:
            raise synth_error[0]


class ElevenLabsTTSEngine:
    """ElevenLabs cloud TTS – API key required."""

    def __init__(self, api_key: str, voice_id: str = "pNInz6obpgDQGcFmaJgB"):
        self.api_key  = api_key
        self.voice_id = voice_id

    def speak(self, text: str) -> None:
        import requests
        headers = {
            "xi-api-key":   self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text":     text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            json=payload, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        _play_audio_bytes(resp.content)


# ---------------------------------------------------------------------------
# Thread-safe player wrapper
# ---------------------------------------------------------------------------

class TTSPlayer:
    """
    Wraps any *Engine. Exposes a blocking speak() method
    meant to be called from a dedicated background thread.
    """

    def __init__(self, engine):
        self._engine  = engine
        self._playing = False
        self._lock    = threading.Lock()

    @property
    def engine(self):
        return self._engine

    @property
    def is_playing(self) -> bool:
        return self._playing

    def speak(
        self,
        text:     str,
        on_start: Optional[Callable] = None,
        on_done:  Optional[Callable] = None,
    ) -> None:
        """Synthesise and play text. BLOCKING – call from a dedicated thread."""
        try:
            with self._lock:
                self._playing = True
            if on_start:
                on_start()
            self._engine.speak(text)
        except Exception as e:
            print(f"[TTS] Error: {e}")
        finally:
            with self._lock:
                self._playing = False
            if on_done:
                on_done()

    def stop(self) -> None:
        sd.stop()
        with self._lock:
            self._playing = False


# ---------------------------------------------------------------------------
# Unified EngineDefault (implements TTSEngine)
# ---------------------------------------------------------------------------

class EngineDefault(TTSEngine):
    """
    Wraps existing default TTS engines (EdgeTTS, Kokoro, ElevenLabs) behind TTSEngine.
    The existing speech output path, latency, and call sites remain byte-for-byte identical.
    """

    def __init__(self, config: Optional[dict] = None, concrete_engine=None):
        self._config = config or {}
        if concrete_engine is not None:
            self._engine = concrete_engine
        else:
            engine_name = self._config.get("tts_engine", "edgetts").lower()
            if engine_name == "kokoro":
                voice = self._config.get("tts_voice", "af_heart")
                speed = float(self._config.get("tts_speed", 1.0))
                self._engine = KokoroTTSEngine(voice=voice, speed=speed)
            elif engine_name == "elevenlabs":
                api_key  = self._config.get("elevenlabs_api_key", "")
                voice_id = self._config.get("tts_voice", "pNInz6obpgDQGcFmaJgB")
                self._engine = ElevenLabsTTSEngine(api_key=api_key, voice_id=voice_id)
            else:
                voice = self._config.get("tts_voice", "en-US-GuyNeural")
                self._engine = EdgeTTSEngine(voice=voice)

    @property
    def name(self) -> str:
        return "default"

    def is_available(self) -> Capability:
        return Capability.OK

    def warm_up(self) -> None:
        if hasattr(self._engine, "_init"):
            self._engine._init()

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize to PCM numpy array and sample rate."""
        if isinstance(self._engine, KokoroTTSEngine):
            with self._engine._lock:
                if self._engine._pipeline is None:
                    self._engine._init()
            chunks = []
            for _, _, audio in self._engine._pipeline(text, voice=self._engine.voice, speed=self._engine.speed):
                if audio is not None:
                    arr = _to_numpy(audio)
                    arr = _compress_silence(arr)
                    if arr.size > 0:
                        chunks.append(arr)
            pcm = np.concatenate(chunks) if chunks else np.zeros((0,), dtype=np.float32)
            return pcm, 24000

        if isinstance(self._engine, EdgeTTSEngine):
            import miniaudio
            loop = asyncio.new_event_loop()
            try:
                audio_bytes = loop.run_until_complete(self._engine._synth(text))
            finally:
                loop.close()
            if not audio_bytes:
                return np.zeros((0,), dtype=np.float32), 24000
            decoded = miniaudio.decode(
                audio_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
            )
            return np.array(decoded.samples, dtype=np.float32), decoded.sample_rate

        # Elevenlabs or generic
        import miniaudio
        import requests
        headers = {"xi-api-key": getattr(self._engine, "api_key", ""), "Content-Type": "application/json"}
        payload = {"text": text, "model_id": "eleven_multilingual_v2"}
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{getattr(self._engine, 'voice_id', '')}",
            json=payload, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        decoded = miniaudio.decode(resp.content, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1)
        return np.array(decoded.samples, dtype=np.float32), decoded.sample_rate

    def speak(self, text: str) -> None:
        """Play speech through existing concrete engine directly."""
        self._engine.speak(text)

    def shutdown(self) -> None:
        pass


def create_tts_player(config: dict) -> TTSPlayer:
    engine = EngineDefault(config=config)
    return TTSPlayer(engine)
