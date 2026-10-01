# Phase 3 Notes — Single Shared Audio Stream

## Status: COMPLETE

### 1. Architectural Architecture & Design
1. **Single InputStream Guarantee**:
   - Replaced multiple independent PortAudio stream allocations with a singleton `SharedAudioStream` in `core/audio/stream.py` (registered in `core.registry` under `"shared_audio_stream"`).
   - Capture parameters:
     - `SAMPLE_RATE = 16000` (16 kHz mono PCM)
     - `CHUNK_SAMPLES = 512` (~32 ms window)
     - `CHANNELS = 1`
     - `PREROLL_S = 2.0` (2-second circular buffer window in RAM)
     - `MAX_SUBSCRIBERS = 8`
     - `STREAM_LATENCY = "low"`

2. **Pre-Roll Circular Buffer**:
   - Implemented via bounded `collections.deque(maxlen=max_preroll_chunks)` where `max_preroll_chunks = 62` (at 16 kHz / 512 samples).
   - Provides thread-safe `snapshot_preroll() -> bytes` to retrieve contiguous PCM audio spanning the last 2 seconds immediately upon wake-word detection or session restart.
   - Provides `clear_preroll()` for session boundaries.

3. **Multi-Consumer Distribution**:
   - `SharedAudioStream.subscribe(sub)` supports both callable callbacks `(bytes, np.ndarray)` and queue instances (`asyncio.Queue`, `queue.Queue`).
   - `feed_chunk()` distributes frames safely with non-blocking dispatch; slow or full subscriber queues do not stall the producer or other subscribers.

4. **Integration**:
   - `_listen_audio` in `main.py` migrated from raw `sd.InputStream` to subscribing to `get_shared_audio_stream()`.
   - Hardware fallback: if the configured device fails, it gracefully falls back to system default.

### 2. Verification
- `py -3.12 -m unittest tests/test_audio_stream.py`: 6/6 PASS in 0.002s.
- `py -3.12 -m unittest tests/test_audio_stream.py tests/test_audio_gate.py tests/test_uplink_latency.py tests/test_voice_sleep.py tests/test_wake_word.py`: 26/26 PASS in 1.190s.
