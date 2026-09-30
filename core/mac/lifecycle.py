"""Siri-style lifecycle for the agent when alfredd (the native listener) runs it.

    alfredd hears "Hey Alfred"  ──wake──▶  agent connects Gemini Live (or is started)
    alfredd transcribes the rest ─command─▶ agent sends it as the user's turn
    no activity for N seconds    ────────▶  agent disconnects, releases the mic ("dormant")
    dormant for M more seconds   ────────▶  agent exits; alfredd keeps listening

While dormant nothing is streamed and Gemini is not connected, so there is no
token cost; alfredd owns the microphone again at ~0.03 % of one core.

Config (config/api_keys.json):
    mac_dormant_after_s   default 120  — idle seconds before disconnecting
    mac_exit_after_s      default 900  — dormant seconds before the process exits (0 = never)
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

from core.mac.daemon_client import DaemonClient, get_client

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "api_keys.json"


def _cfg() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


class MacLifecycle:
    def __init__(self, live):
        self.live = live
        self.client: DaemonClient | None = get_client(start=False)
        cfg = _cfg()
        self.dormant_after = float(cfg.get("mac_dormant_after_s", 120))
        self.exit_after = float(cfg.get("mac_exit_after_s", 900))
        self.launch_reason = os.environ.get("ALFRED_LAUNCH_REASON", "")
        self.dormant = False
        self.last_wake = time.monotonic()
        self._gate_until = 0.0
        # Requests from alfredd: {"text": on-device transcript, "audio": path to 16 kHz PCM or None}
        self._pending: list[dict] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake_evt: asyncio.Event | None = None
        self._sleep_now = False
        self._session_live = False
        # Recordings alfredd handed to an agent that never replayed them.
        support = Path.home() / "Library/Application Support/ALFRED"
        for f in support.glob("utterance-*.pcm"):
            try:
                if time.time() - f.stat().st_mtime > 300:
                    f.unlink()
            except OSError:
                pass
        if self.client is not None:
            self.client.on("wake", self._on_wake)
            self.client.on("command", self._on_command)
            self.client.on("show", lambda _m: self._on_show())
            self.client.on("alarm_fired", self._on_alarm)
            # alfredd greets every (re)connection. Tell it what we are doing: an
            # agent that outlived a listener restart must not leave the new one
            # listening over our own voice.
            self.client.on("welcome", lambda _m: self._report_state())
            self.client.start()

    @property
    def managed(self) -> bool:
        return self.client is not None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._wake_evt = asyncio.Event()

    # ── Signals from alfredd (client thread) ──────────────────────────────────

    def _on_wake(self, msg: dict) -> None:
        print(f"[mac] wake ({msg.get('source', 'menu')})")
        self.last_wake = time.monotonic()
        if msg.get("capturing"):
            # alfredd is still transcribing the command: keep our own mic from
            # sending the same words to Gemini a second time.
            self._gate_until = time.monotonic() + 15
        self.dormant = False
        self._sleep_now = False
        if self._loop and self._wake_evt:
            self._loop.call_soon_threadsafe(self._wake_evt.set)
        try:
            if getattr(self.live, "_wake_enabled", False):
                self.live.wake(reason="Hey Alfred")
            self.live.ui.mac_on_wake()
        except Exception as e:
            print(f"[mac] wake UI: {e}")

    def _on_command(self, msg: dict) -> None:
        text = str(msg.get("text") or "").strip()
        audio = msg.get("audio") if msg.get("audio") and os.path.exists(str(msg.get("audio"))) else None
        self.last_wake = time.monotonic()
        # With a recording to replay, keep the live mic quiet until it has been
        # queued, so the two streams cannot interleave.
        self._gate_until = time.monotonic() + 30 if audio else 0.0
        if text or audio:
            self._pending.append({"text": text, "audio": audio})
            if self._loop:
                asyncio.run_coroutine_threadsafe(self._deliver(), self._loop)

    def _on_show(self) -> None:
        self.last_wake = time.monotonic()
        self.dormant = False
        if self._loop and self._wake_evt:
            self._loop.call_soon_threadsafe(self._wake_evt.set)
        try:
            self.live.ui.mac_show_main()
        except Exception as e:
            print(f"[mac] show: {e}")

    def _on_alarm(self, msg: dict) -> None:
        a = msg.get("alarm") or {}
        label = a.get("label") or ("Timer" if a.get("kind") == "timer" else "Alarm")
        try:
            self.live.ui.write_log(f"SYS: ⏰ {label} — say “stop” or “snooze”.")
        except Exception:
            pass

    def _report_state(self) -> None:
        if self.dormant:
            state = "dormant"
        elif self._session_live:
            state = "active"
        else:
            state = "starting"
        self.client.send({"type": "state", "state": state})

    # ── Hooks called by JarvisLive ────────────────────────────────────────────

    def mic_gated(self) -> bool:
        return time.monotonic() < self._gate_until

    def wake_from_text(self, text: str) -> bool:
        """Typed input while dormant: wake and send it. Returns True if handled here."""
        if not self.dormant:
            return False
        self._on_wake({"capturing": False})
        self._on_command({"text": text})
        return True

    def request_sleep(self) -> None:
        """Window closed / tray "Sleep now": go dormant at the next tick."""
        self._sleep_now = True

    async def wait_until_awake(self) -> None:
        if not self.managed or not self.dormant:
            return
        self._session_live = False
        self.live.ui.set_state("SLEEPING")
        self.client.send({"type": "state", "state": "dormant"})
        try:
            self.live.ui.mac_on_dormant()
        except Exception:
            pass
        self.live.ui.write_log("SYS: Dormant — say “Hey Alfred” to wake me.")
        assert self._wake_evt is not None
        self._wake_evt.clear()
        if self.dormant:
            try:
                if self.exit_after > 0:
                    await asyncio.wait_for(self._wake_evt.wait(), timeout=self.exit_after)
                else:
                    await self._wake_evt.wait()
            except asyncio.TimeoutError:
                # Only unload when the listener is there to bring us back.
                if self.client.connected.is_set():
                    self.exit_process("dormant too long")
                await self._wake_evt.wait()
        self.dormant = False

    def on_session_ready(self) -> None:
        self._session_live = True
        if self.managed:
            self.client.send({"type": "state", "state": "active"})
        if self._pending and self._loop:
            asyncio.run_coroutine_threadsafe(self._deliver(), self._loop)

    async def _deliver(self) -> None:
        try:
            await self._deliver_pending()
        except Exception as e:
            import traceback
            print(f"[mac] could not deliver command: {e}")
            traceback.print_exc()

    async def _deliver_pending(self) -> None:
        for _ in range(300):                       # up to 30 s for the session
            if getattr(self.live, "session", None) is not None:
                break
            await asyncio.sleep(0.1)
        session = getattr(self.live, "session", None)
        while self._pending and session is not None:
            item = self._pending.pop(0)
            text, audio = item.get("text", ""), item.get("audio")
            self.live._last_user_speech = time.monotonic()
            queue = getattr(self.live, "out_queue", None)
            if audio and queue is not None:
                # Replay what the user said after "Hey Alfred" as if the mic had
                # heard it live: Gemini transcribes it (any language) and answers.
                try:
                    with open(audio, "rb") as f:
                        pcm = f.read()
                finally:
                    try:
                        os.unlink(audio)
                    except OSError:
                        pass
                print(f"[mac] command → Gemini: {len(pcm) / 32000:.1f}s of speech (on-device heard {text!r})")
                for i in range(0, len(pcm), 2048):
                    await queue.put({"data": pcm[i:i + 2048], "mime_type": "audio/pcm"})
                silence = bytes(2048)
                for _ in range(10):                       # ~0.6 s so the turn ends promptly
                    await queue.put({"data": silence, "mime_type": "audio/pcm"})
                self._gate_until = 0.0
            elif text:
                print(f"[mac] command → Gemini: {text!r}")
                self.live.ui.write_log(f"You: {text}")
                await session.send_client_content(turns={"role": "user", "parts": [{"text": text}]},
                                                  turn_complete=True)

    async def idle_watch(self, make_signal) -> None:
        """Session task: raise `make_signal()` to unwind the session when idle.

        Idle means ALFRED hasn't spoken, run a tool or been woken/typed to for
        `dormant_after` seconds. Speech the mic merely hears doesn't count
        (a TV or a conversation in the room would keep Gemini connected all
        day); it only postpones sleep while someone is mid-sentence.
        """
        if not self.managed:
            return
        last_busy = time.monotonic()
        while True:
            await asyncio.sleep(1 if self._sleep_now else 5)
            now = time.monotonic()
            live = self.live
            with live._speaking_lock:
                speaking = live._is_speaking
            if speaking or getattr(live, "_tool_calls_active", 0) > 0 or self.mic_gated() or self._pending:
                last_busy = now
            last_activity = max(last_busy, self.last_wake,
                                getattr(live, "_last_assistant_activity", 0.0))
            idle = now - last_activity
            mid_sentence = now - getattr(live, "_last_user_speech", 0.0) < 3
            # Without the listener nothing could wake us again, so only an
            # explicit "sleep now" puts us to sleep then.
            listener_up = self.client.connected.is_set()
            if self._sleep_now or (listener_up and self.dormant_after > 0
                                   and idle > self.dormant_after and not mid_sentence):
                reason = "asked to sleep" if self._sleep_now else f"idle {int(idle)}s"
                print(f"[mac] going dormant ({reason})")
                self.dormant = True
                self._sleep_now = False
                raise make_signal()

    def exit_process(self, reason: str) -> None:
        # The session summary was already saved when the session closed.
        print(f"[mac] exiting agent ({reason}) — alfredd keeps listening")
        os._exit(0)
