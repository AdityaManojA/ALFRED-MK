"""Windows external-media suppression via SMTC, with pycaw mute fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import sys
from typing import Any

from .base import Suppressor


SUPPRESS_TIMEOUT_MS = 500


@dataclass(eq=False)
class _WindowsHandle:
    session: Any
    kind: str
    original_volume: float | None = None
    muted_by_alfred: bool = False


class WindowsSuppressor(Suppressor):
    """Keep all external identities inside this module."""

    def enumerate_players(self) -> list[Any]:
        handles = self._smtc_sessions()
        return handles or self._pycaw_sessions()

    def _smtc_sessions(self) -> list[Any]:
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus,
            )

            async def collect() -> list[Any]:
                manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
                out = []
                own_executable = os.path.basename(sys.executable).lower()
                for session in manager.get_sessions():
                    # SMTC exposes an application model id, not a public player
                    # identity. Use it only for self-exclusion and discard it.
                    app_id = str(getattr(session, "source_app_user_model_id", "") or "").lower()
                    if own_executable and own_executable in app_id:
                        continue
                    info = session.get_playback_info()
                    if info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                        out.append(_WindowsHandle(session, "smtc"))
                return out

            return asyncio.run(asyncio.wait_for(collect(), SUPPRESS_TIMEOUT_MS / 1000.0))
        except Exception:
            return []

    def _pycaw_sessions(self) -> list[Any]:
        try:
            from pycaw.pycaw import AudioUtilities
            current_pid = os.getpid()
            out = []
            for session in AudioUtilities.GetAllSessions():
                process = session.Process
                if not process or process.pid == current_pid:
                    continue
                out.append(_WindowsHandle(session, "pycaw"))
            return out
        except Exception:
            return []

    def pause(self, handle: Any) -> bool:
        if not isinstance(handle, _WindowsHandle):
            return False
        try:
            if handle.kind == "smtc":
                return bool(asyncio.run(asyncio.wait_for(
                    handle.session.try_pause_async(), SUPPRESS_TIMEOUT_MS / 1000.0
                )))
            volume = handle.session.SimpleAudioVolume
            handle.original_volume = float(volume.GetMasterVolume())
            volume.SetMasterVolume(0.0, None)
            handle.muted_by_alfred = True
            return True
        except Exception:
            return False

    def resume(self, handle: Any) -> bool:
        if not isinstance(handle, _WindowsHandle):
            return False
        try:
            if handle.kind == "smtc":
                return bool(asyncio.run(asyncio.wait_for(
                    handle.session.try_play_async(), SUPPRESS_TIMEOUT_MS / 1000.0
                )))
            if handle.muted_by_alfred and handle.original_volume is not None:
                handle.session.SimpleAudioVolume.SetMasterVolume(handle.original_volume, None)
                handle.muted_by_alfred = False
                return True
        except Exception:
            return False
        return False

    def is_playing(self, handle: Any) -> bool:
        if not isinstance(handle, _WindowsHandle):
            return False
        if handle.kind == "pycaw":
            return not handle.muted_by_alfred
        return True
