from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import psutil

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QLineF, QMimeData, QObject, QParallelAnimationGroup, QPoint, QPointF,
    QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from core.sentry.mode_manager import get_sentry_mode_manager, SentrySnapshot
from core.sentry.focus.card import FloatingFocusCard
from core.logger import install_timestamped_logging
install_timestamped_logging()
from core.gui_thread import assert_gui_thread, is_gui_thread
from PyQt6.QtWidgets import (
    QMenu,
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter,
    QStackedWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget, QProgressBar, QToolTip,
)

# Qt6 enum compatibility alias: SemiBold -> DemiBold
if not hasattr(QFont.Weight, "SemiBold") and hasattr(QFont.Weight, "DemiBold"):
    try:
        setattr(QFont.Weight, "SemiBold", QFont.Weight.DemiBold)
    except Exception:
        pass

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    _HAS_QT_MULTIMEDIA = True
except Exception:
    _HAS_QT_MULTIMEDIA = False
    QVideoWidget = None  # type: ignore[assignment,misc]



def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
ICONS_DIR  = BASE_DIR / "Icons"

_ICON_CATALOG_CACHE: tuple[tuple, list[dict]] | None = None
_SCALED_PIXMAP_CACHE: dict[tuple[str, int, int, int], QPixmap] = {}


def format_icon_display_name(filename: str) -> str:
    """Format an icon file name into an authentic, sleek tactical insignia title."""
    stem = Path(filename).stem
    custom_names = {
        "baticon_arlham_asylum": "Arkham Asylum",
        "baticon_beyond": "Batman Beyond",
        "baticon_default": "Classic Bat",
        "baticon_white": "White Knight Bat",
        "trasparent": "Stealth Insignia",
        "transparent": "Stealth Insignia",
        "batman_logo": "Wayne Crest",
        "alfred": "Alfred Crest",
        "alfred_bg": "Alfred Shield",
    }
    key = stem.lower()
    if key in custom_names:
        return custom_names[key]
    cleaned = stem
    for prefix in ("baticon_", "icon_", "bat_"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
    return cleaned.title()


def get_available_app_icons() -> list[dict]:
    """Scan Icons/ and config/ for all available badges/icons."""
    global _ICON_CATALOG_CACHE
    search_dirs = [ICONS_DIR, Path(__file__).resolve().parent / "Icons"]
    cfg_dir = BASE_DIR / "config"
    signature = tuple(
        (str(path), path.stat().st_mtime_ns if path.exists() else -1)
        for path in (*search_dirs, cfg_dir)
    )
    if _ICON_CATALOG_CACHE and _ICON_CATALOG_CACHE[0] == signature:
        return [dict(item) for item in _ICON_CATALOG_CACHE[1]]

    found = []
    seen = set()

    for idir in search_dirs:
        if idir.exists() and idir.is_dir():
            for p in sorted(idir.iterdir()):
                if p.is_file() and p.suffix.lower() in (".png", ".ico", ".jpg", ".jpeg", ".webp", ".svg"):
                    stem_key = p.stem.lower()
                    if stem_key not in seen:
                        seen.add(stem_key)
                        found.append({
                            "name": format_icon_display_name(p.name),
                            "path": str(p.resolve()),
                            "filename": p.name,
                        })

    if cfg_dir.exists():
        for name in ("batman_logo.png", "alfred.ico", "alfred.png"):
            cp = cfg_dir / name
            if cp.exists():
                stem_key = cp.stem.lower()
                if stem_key not in seen:
                    seen.add(stem_key)
                    found.append({
                        "name": format_icon_display_name(cp.name),
                        "path": str(cp.resolve()),
                        "filename": cp.name,
                    })
    _ICON_CATALOG_CACHE = (signature, found)
    return [dict(item) for item in found]


def _scaled_icon_pixmap(path: str, width: int, height: int) -> QPixmap:
    """Load and scale an icon once per file version and target size."""
    try:
        mtime = Path(path).stat().st_mtime_ns
    except OSError:
        mtime = -1
    key = (str(path), int(width), int(height), mtime)
    cached = _SCALED_PIXMAP_CACHE.get(key)
    if cached is not None:
        return QPixmap(cached)

    pixmap = QPixmap(path)
    if not pixmap.isNull():
        pixmap = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        _SCALED_PIXMAP_CACHE[key] = QPixmap(pixmap)
    return pixmap


def _plugin_settings_signature(sections: list[dict]) -> tuple:
    """Stable identity for deciding whether a settings form can be reused."""
    signature = []
    for section in sections or []:
        signature.append((
            section.get("namespace") or section.get("plugin") or "",
            json.dumps(section.get("fields", []), sort_keys=True, default=str),
            json.dumps(section.get("values", {}), sort_keys=True, default=str),
        ))
    return tuple(signature)




class TronScoreBackgroundPlayer(QObject):
    """
    Background music audio engine.
    Plays background score continuously on loop (default: 'The Son of Flynn' TRON Legacy Score).
    Default volume: 10% (0.10).
    When ALFRED speaks, automatically ducks volume to 5% (0.05).
    When ALFRED stops speaking, smoothly restores volume back to 10% (0.10).
    Supports loading, adding, switching, and updating custom music files.
    """
    NORMAL_VOL = 0.10
    TTS_DUCK_LEVEL = 0.25
    DUCK_RAMP_MS = 300
    FADE_INTERVAL_MS = 20

    track_changed          = pyqtSignal(str, str)          # (stem, path)
    playback_state_changed = pyqtSignal(bool)              # is_playing
    ducked_state_changed   = pyqtSignal(bool, float)       # (is_ducked, target_vol)
    playlist_updated       = pyqtSignal(list)              # list of track paths
    spotify_state_received = pyqtSignal(object)            # worker-thread playback snapshot

    # Thread marshaling signals for safe execution on Qt GUI thread
    _req_set_ducked        = pyqtSignal(bool)
    _req_play              = pyqtSignal()
    _req_pause             = pyqtSignal()
    _req_pause_core        = pyqtSignal()
    _req_resume_core       = pyqtSignal()
    _req_set_base_volume   = pyqtSignal(float)
    _req_load_track        = pyqtSignal(str, bool)
    _req_toggle_play       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._normal_vol         = self.NORMAL_VOL
        self._ducked_vol         = self._normal_vol * self.TTS_DUCK_LEVEL
        self._target_vol         = self._normal_vol
        self._current_vol        = self._normal_vol
        self._is_speaking_ducked = False
        self._is_paused          = True
        self._media_arbiter      = None
        self._duck_fade_start_s  = None
        self._duck_fade_start_vol = self._current_vol

        self._source_mode        = "tron"      # "tron" (local background score) | "spotify"
        self._default_tron_track: Path | None = None
        self._spotify_track: dict             = {}
        self._spotify_is_playing = False

        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None  = None
        self._current_path: Path | None   = None
        self._playlist: list[Path]        = []
        self._spotify_sync_busy = False
        self.spotify_state_received.connect(self._apply_spotify_state)
        self._req_set_ducked.connect(self._do_set_ducked)
        self._req_play.connect(self._do_play)
        self._req_pause.connect(self._do_pause)
        self._req_pause_core.connect(self._do_pause_core)
        self._req_resume_core.connect(self._do_resume_core)
        self._req_set_base_volume.connect(self._do_set_base_volume)
        self._req_load_track.connect(lambda p, a: self._do_load_track(p, a))
        self._req_toggle_play.connect(self._do_toggle_play)

        self._spotify_sync_timer = QTimer(self)
        self._spotify_sync_timer.setInterval(10000)
        self._spotify_sync_timer.timeout.connect(self._queue_spotify_sync)
        self._spotify_sync_timer.start()
        QTimer.singleShot(1200, self._queue_spotify_sync)

        if not _HAS_QT_MULTIMEDIA:
            print("[Audio] QtMultimedia not available — background score disabled.")
            return

        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(self.FADE_INTERVAL_MS)
        self._fade_timer.timeout.connect(self._step_fade)

        self._init_playlist()

    def _init_playlist(self):
        # 1. Discover default candidates
        _candidates = [
            BASE_DIR / "The Son of Flynn (From TRON Legacy Score).mp3",
            Path(__file__).resolve().parent / "The Son of Flynn (From TRON Legacy Score).mp3",
            Path.cwd() / "The Son of Flynn (From TRON Legacy Score).mp3",
            Path(r"d:\Projects\Personal-Assistant\Mark-LIV\The Son of Flynn (From TRON Legacy Score).mp3"),
            Path(r"d:\Projects\Alfred-Mark-II\The Son of Flynn (From TRON Legacy Score).mp3"),
            Path(r"d:\Projects\Alfred-Mark-III\The Son of Flynn (From TRON Legacy Score).mp3"),
            Path(r"d:\Projects\Alfred-Mark-IV\The Son of Flynn (From TRON Legacy Score).mp3"),
        ]
        default_track = next((p for p in _candidates if p.exists()), None)
        if default_track:
            self._default_tron_track = default_track
            self._playlist.append(default_track)

        # 2. Load saved playlist from config
        cfg_file = CONFIG_DIR / "music_playlist.json"
        last_track_str = None
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
                for p_str in data.get("tracks", []):
                    p = Path(p_str)
                    if p.exists() and p not in self._playlist:
                        self._playlist.append(p)
                last_track_str = data.get("current_track")
                if "base_volume" in data:
                    self._normal_vol = float(data["base_volume"])
                    self._ducked_vol = self._normal_vol * 0.5
                    self._target_vol = self._normal_vol
                    self._current_vol = self._normal_vol
            except Exception as e:
                print(f"[Audio] Error loading music_playlist.json: {e}")

        # Choose initial track
        initial_track = None
        if last_track_str:
            p = Path(last_track_str)
            if p.exists():
                initial_track = p
        if not initial_track and self._playlist:
            initial_track = self._playlist[0]

        if initial_track:
            self.load_track(initial_track, auto_play=False)

    def _save_playlist_config(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cfg_file = CONFIG_DIR / "music_playlist.json"
            data = {
                "current_track": str(self._current_path.resolve()) if self._current_path else "",
                "tracks": [str(p.resolve()) for p in self._playlist if p.exists()],
                "base_volume": self._normal_vol,
            }
            cfg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Audio] Error saving music_playlist.json: {e}")

    def base_volume(self) -> float:
        return self._normal_vol

    def set_base_volume(self, vol: float):
        """Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base."""
        if not is_gui_thread():
            self._req_set_base_volume.emit(vol)
            return
        self._do_set_base_volume(vol)

    def _do_set_base_volume(self, vol: float):
        assert_gui_thread("TronScoreBackgroundPlayer.set_base_volume")
        vol = max(0.0, min(1.0, vol))
        self._normal_vol = vol
        self._ducked_vol = vol * self.TTS_DUCK_LEVEL
        if self._is_paused:
            self._target_vol = 0.0
        else:
            self._target_vol = self._ducked_vol if self._is_speaking_ducked else self._normal_vol
        if self._audio:
            self._current_vol = self._target_vol
            self._audio.setVolume(self._current_vol)
        self.ducked_state_changed.emit(self._is_speaking_ducked, self._target_vol)
        self._save_playlist_config()

    def load_track(self, path: Path | str, auto_play: bool = True) -> bool:
        if not is_gui_thread():
            self._req_load_track.emit(str(path), auto_play)
            return True
        return self._do_load_track(path, auto_play)

    def _do_load_track(self, path: Path | str, auto_play: bool = True) -> bool:
        assert_gui_thread("TronScoreBackgroundPlayer.load_track")
        path = Path(path)
        if not path.exists():
            print(f"[Audio] Track not found: {path}")
            return False

        if path not in self._playlist:
            self._playlist.append(path)
            self.playlist_updated.emit(self._playlist)

        self._current_path = path

        try:
            if not self._player:
                self._player = QMediaPlayer(self)
                self._audio  = QAudioOutput(self)
                self._player.setAudioOutput(self._audio)
                self._player.setLoops(QMediaPlayer.Loops.Infinite)
                self._player.playbackStateChanged.connect(self._on_local_playback_state_changed)

            self._audio.setVolume(self._current_vol)
            self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            self._is_paused = not auto_play
            if auto_play:
                self._player.play()
                self.playback_state_changed.emit(True)
            else:
                self._player.pause()

            print(f"[Audio] Loaded background track ({path.name}) at {int(self._normal_vol*100)}% volume.")
            self.track_changed.emit(path.stem, str(path.resolve()))
            self._save_playlist_config()
            return True
        except Exception as e:
            print(f"[Audio] Error loading track {path.name}: {e}")
            return False

    def add_and_play(self, path: Path | str):
        p = Path(path)
        if p.exists():
            if p not in self._playlist:
                self._playlist.append(p)
                self.playlist_updated.emit(self._playlist)
            self._is_paused = False
            self.load_track(p, auto_play=True)

    def set_ducked(self, ducked: bool):
        """Duck to the media-arbiter level while TTS is active."""
        if not is_gui_thread():
            self._req_set_ducked.emit(ducked)
            return
        self._do_set_ducked(ducked)

    def _do_set_ducked(self, ducked: bool):
        assert_gui_thread("TronScoreBackgroundPlayer.set_ducked")
        self._is_speaking_ducked = ducked
        if self._is_paused:
            self._target_vol = 0.0
        else:
            self._target_vol = self._ducked_vol if ducked else self._normal_vol
        self.ducked_state_changed.emit(ducked, self._target_vol)
        self._duck_fade_start_s = time.monotonic()
        self._duck_fade_start_vol = self._current_vol
        if self._fade_timer and not self._fade_timer.isActive():
            self._fade_timer.start()

    def set_media_arbiter(self, arbiter) -> None:
        """Attach the application-owned arbiter at the playback state chokepoint."""
        if arbiter is self._media_arbiter:
            return
        self._media_arbiter = arbiter
        self.playback_state_changed.connect(self._sync_arbiter_playback)
        self._sync_arbiter_playback(self.is_playing())

    def _sync_arbiter_playback(self, is_playing: bool) -> None:
        if self._media_arbiter is None:
            return
        from core.media import AudioSource
        if is_playing:
            self._media_arbiter.claim(AudioSource.APP_PLAYER)
        else:
            self._media_arbiter.release(AudioSource.APP_PLAYER)

    def _step_fade(self):
        if not self._audio:
            if self._fade_timer:
                self._fade_timer.stop()
            return
        if self._duck_fade_start_s is not None:
            elapsed_ms = (time.monotonic() - self._duck_fade_start_s) * 1000.0
            progress = min(1.0, elapsed_ms / self.DUCK_RAMP_MS)
            self._current_vol = self._duck_fade_start_vol + (
                (self._target_vol - self._duck_fade_start_vol) * progress
            )
            self._audio.setVolume(max(0.0, min(1.0, self._current_vol)))
            if progress >= 1.0:
                self._duck_fade_start_s = None
                self._fade_timer.stop()
            return
        diff = self._target_vol - self._current_vol
        if abs(diff) < 0.002:
            self._current_vol = self._target_vol
            self._audio.setVolume(self._current_vol)
            self._fade_timer.stop()
        else:
            step = 0.005 if diff > 0 else -0.005
            self._current_vol += step
            self._audio.setVolume(max(0.0, min(1.0, self._current_vol)))

    def source_mode(self) -> str:
        return self._source_mode

    def spotify_track(self) -> dict:
        return dict(self._spotify_track)

    def set_spotify_playback(
        self, title: str, artist: str = "", uri: str = "", is_playing: bool = True
    ):
        """Called when Spotify plays a track. Pauses Tron background music, sets Spotify as active source."""
        previous = dict(self._spotify_track)
        was_playing = self._spotify_is_playing
        self._source_mode = "spotify"
        self._spotify_track = {"title": title, "artist": artist, "uri": uri}
        if self._player:
            try:
                self._player.pause()
            except Exception:
                pass
        self._spotify_is_playing = is_playing
        display_name = f"SPOTIFY: {title}" + (f" ({artist})" if artist else "")
        if previous != self._spotify_track:
            self.track_changed.emit(display_name, uri or "spotify")
        if was_playing != is_playing or previous != self._spotify_track:
            self.playback_state_changed.emit(is_playing)

    def set_spotify_playback_state(self, is_playing: bool) -> None:
        if self._source_mode != "spotify":
            return
        changed = self._spotify_is_playing != is_playing
        self._spotify_is_playing = is_playing
        if changed:
            self.playback_state_changed.emit(is_playing)

    def _queue_spotify_sync(self) -> None:
        if self._spotify_sync_busy:
            return
        try:
            from actions.spotify_control import get_spotify_client
            client = get_spotify_client()
            if not client.has_user_authorization():
                return
        except Exception:
            return

        self._spotify_sync_busy = True

        def fetch() -> None:
            try:
                state = client.get_current_playback()
            except Exception:
                state = {}
            self.spotify_state_received.emit(state)

        threading.Thread(target=fetch, daemon=True, name="SpotifyPlaybackSync").start()

    def _apply_spotify_state(self, state: object) -> None:
        self._spotify_sync_busy = False
        snapshot = state if isinstance(state, dict) else {}
        if snapshot.get("name") and (snapshot.get("is_playing") or self._source_mode == "spotify"):
            self.set_spotify_playback(
                snapshot["name"],
                snapshot.get("artist", ""),
                snapshot.get("uri", ""),
                bool(snapshot.get("is_playing")),
            )
        elif self._source_mode == "spotify" and not snapshot:
            self.set_spotify_playback_state(False)

    def _on_local_playback_state_changed(self, state) -> None:
        if self._source_mode != "tron":
            return
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._is_paused = not playing
        self.playback_state_changed.emit(playing)

    def clear_spotify_and_restore_tron(self):
        """Restores Tron legacy score as the default active audio."""
        self._source_mode = "tron"
        self._spotify_track = {}
        self._spotify_is_playing = False
        self._is_paused = False
        if self._default_tron_track and self._default_tron_track.exists():
            self.load_track(self._default_tron_track, auto_play=True)
        elif self._playlist:
            self.load_track(self._playlist[0], auto_play=True)

    def toggle_play(self):
        if not is_gui_thread():
            self._req_toggle_play.emit()
            return
        self._do_toggle_play()

    def _do_toggle_play(self):
        assert_gui_thread("TronScoreBackgroundPlayer.toggle_play")
        if self._source_mode == "spotify":
            if self._is_paused:
                self._do_play()
            else:
                self._do_pause()
            return
        if not self._player:
            return
        if self._is_paused:
            self._do_play()
        else:
            self._do_pause()

    def play(self):
        if not is_gui_thread():
            self._req_play.emit()
            return
        self._do_play()

    def _do_play(self):
        assert_gui_thread("TronScoreBackgroundPlayer.play")
        if self._source_mode == "spotify":
            try:
                from actions.spotify_control import control_playback
                success = control_playback("resume")
            except Exception:
                success = False
            if success:
                self.set_spotify_playback_state(True)
            return

        if not self._player:
            return
        self._is_paused = False
        self._player.play()
        self._target_vol = self._ducked_vol if self._is_speaking_ducked else self.NORMAL_VOL
        if self._fade_timer and not self._fade_timer.isActive():
            self._fade_timer.start()
        self.playback_state_changed.emit(True)

    def pause(self):
        if not is_gui_thread():
            self._req_pause.emit()
            return
        self._do_pause()

    def _do_pause(self):
        assert_gui_thread("TronScoreBackgroundPlayer.pause")
        if self._source_mode == "spotify":
            try:
                from actions.spotify_control import control_playback
                success = control_playback("pause")
            except Exception:
                success = False
            if success:
                self.set_spotify_playback_state(False)
            return

        if not self._player:
            return
        self._is_paused = True
        self._target_vol = 0.0
        if self._fade_timer and not self._fade_timer.isActive():
            self._fade_timer.start()
        self._player.pause()
        self.playback_state_changed.emit(False)

    def pause_core(self):
        """Specifically pause the local TRON audio core player regardless of mode."""
        if not is_gui_thread():
            self._req_pause_core.emit()
            return
        self._do_pause_core()

    def _do_pause_core(self):
        assert_gui_thread("TronScoreBackgroundPlayer.pause_core")
        self._is_paused = True
        self._target_vol = 0.0
        if self._fade_timer and self._fade_timer.isActive():
            self._fade_timer.stop()
        if self._player:
            self._player.pause()
        self.playback_state_changed.emit(False)

    def resume_core(self):
        """Specifically resume/play the local TRON audio core player."""
        if not is_gui_thread():
            self._req_resume_core.emit()
            return
        self._do_resume_core()

    def _do_resume_core(self):
        assert_gui_thread("TronScoreBackgroundPlayer.resume_core")
        self._source_mode = "tron"
        self._is_paused = False
        if not self._player and (self._default_tron_track or self._playlist):
            self._do_load_track(self._default_tron_track or self._playlist[0], auto_play=True)
        elif self._player:
            self._player.play()
            self._target_vol = self._ducked_vol if self._is_speaking_ducked else self._normal_vol
            if self._fade_timer and not self._fade_timer.isActive():
                self._fade_timer.start()
            self.playback_state_changed.emit(True)

    def next_track(self):
        if self._source_mode == "spotify":
            try:
                from actions.spotify_control import control_playback
                control_playback("skip_next")
            except Exception:
                pass
            return

        if not self._playlist:
            return
        try:
            curr_idx = self._playlist.index(self._current_path) if self._current_path in self._playlist else -1
            nxt_idx = (curr_idx + 1) % len(self._playlist)
            self.load_track(self._playlist[nxt_idx], auto_play=True)
        except Exception:
            pass

    def prev_track(self):
        if self._source_mode == "spotify":
            try:
                from actions.spotify_control import control_playback
                control_playback("skip_previous")
            except Exception:
                pass
            return

        if not self._playlist:
            return
        try:
            curr_idx = self._playlist.index(self._current_path) if self._current_path in self._playlist else 0
            prev_idx = (curr_idx - 1 + len(self._playlist)) % len(self._playlist)
            self.load_track(self._playlist[prev_idx], auto_play=True)
        except Exception:
            pass

    def is_playing(self) -> bool:
        if self._source_mode == "spotify":
            return self._spotify_is_playing
        if self._player is None:
            return False
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def current_track_name(self) -> str:
        if self._source_mode == "spotify" and self._spotify_track:
            return self._spotify_track.get("title", "Spotify Track")
        return self._current_path.name if self._current_path else "The Son of Flynn (From TRON Legacy Score).mp3"

    def current_track_stem(self) -> str:
        if self._source_mode == "spotify" and self._spotify_track:
            title = self._spotify_track.get("title", "Spotify Track")
            artist = self._spotify_track.get("artist", "")
            return f"SPOTIFY: {title} ({artist})" if artist else f"SPOTIFY: {title}"
        return self._current_path.stem if self._current_path else "The Son of Flynn"

    def playlist(self) -> list[Path]:
        return list(self._playlist)

    def stop(self):
        try:
            self._spotify_sync_timer.stop()
            if self._player:
                self._player.stop()
        except Exception:
            pass


def _read_full_config() -> dict:
    """Read api_keys.json config dict. Returns {} on any error."""
    try:
        from memory.config_manager import load_api_keys
        return load_api_keys()
    except Exception:
        return {}


# Single source of truth for the release name — the window title, the header
# badge and the readme must never disagree again.
APP_VERSION  = "MK-IV"
APP_PROTOCOL = "MK-IV"

_DEFAULT_W, _DEFAULT_H = 1120, 720
_MIN_W,     _MIN_H     = 920, 600
_LEFT_W  = 220
_RIGHT_W = 345

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


# ── Retro-Futuristic Cyber CRT Palette (Dossier / Vector / Batman Beyond) ─────────
CRT_THEMES: dict[str, dict] = {
    "dossier": {
        "name": "DEFAULT BATCAVE",
        "hex": "#8e9bff",
        "colors": {
            "BG": "#090a12",
            "PANEL": "#0d0f1e",
            "PANEL2": "#121528",
            "PANEL_BG": "rgba(13, 15, 30, 0.96)",
            "BORDER": "#222748",
            "BORDER_B": "#505bb5",
            "BORDER_A": "#343a6b",
            "PRI": "#8e9bff",
            "PRI_DIM": "#5463cc",
            "PRI_GHO": "#1a1d36",
            "ACC": "#ff7390",
            "ACC2": "#ffd166",
            "GREEN": "#4ef2bb",
            "GREEN_D": "#228562",
            "RED": "#ff2a55",
            "MUTED": "#707ab0",
            "MUTED_C": "#ff3366",
            "TEXT": "#e8ecff",
            "TEXT_DIM": "#707ab0",
            "TEXT_MED": "#a6b2f0",
            "TEXT_BRIGHT": "#ffffff",
            "WHITE": "#f4f6ff",
            "DARK": "#05060a",
            "BAR_BG": "#101222",
        },
    },
    "vector": {
        "name": "BANE MODE",
        "hex": "#a8ff3e",
        "colors": {
            "BG": "#060d07",
            "PANEL": "#09170b",
            "PANEL2": "#0f2613",
            "PANEL_BG": "rgba(9, 23, 11, 0.96)",
            "BORDER": "#1d4724",
            "BORDER_B": "#48a355",
            "BORDER_A": "#285828",
            "PRI": "#a8ff3e",
            "PRI_DIM": "#62b81d",
            "PRI_GHO": "#14290e",
            "ACC": "#ffaa33",
            "ACC2": "#ffd700",
            "GREEN": "#a8ff3e",
            "GREEN_D": "#509920",
            "RED": "#ff3838",
            "MUTED": "#588554",
            "MUTED_C": "#ff4466",
            "TEXT": "#dcfc9f",
            "TEXT_DIM": "#588554",
            "TEXT_MED": "#9de37d",
            "TEXT_BRIGHT": "#ffffff",
            "WHITE": "#f6ffea",
            "DARK": "#030804",
            "BAR_BG": "#0c1d0f",
        },
    },
    "beyond": {
        "name": "BATMAN BEYOND [NEO-GOTHAM]",
        "hex": "#ff0037",
        "colors": {
            "BG": "#070103",
            "PANEL": "#0d0205",
            "PANEL2": "#18040a",
            "PANEL_BG": "rgba(13, 2, 5, 0.96)",
            "BORDER": "#3b0813",
            "BORDER_B": "#ff0037",
            "BORDER_A": "#660d1f",
            "PRI": "#ff0037",
            "PRI_DIM": "#b80028",
            "PRI_GHO": "#33000b",
            "ACC": "#00d4ff",
            "ACC2": "#38bdf8",
            "GREEN": "#00d4ff",
            "GREEN_D": "#0284c7",
            "RED": "#ff0037",
            "MUTED": "#8a2538",
            "MUTED_C": "#ff0037",
            "TEXT": "#ffebef",
            "TEXT_DIM": "#8a2538",
            "TEXT_MED": "#ff758f",
            "TEXT_BRIGHT": "#ffffff",
            "WHITE": "#fff0f3",
            "DARK": "#040002",
            "BAR_BG": "#140308",
        },
    },
}

_ACTIVE_THEME_ID = "dossier"


class C:
    # Default initial state matches DOSSIER CRT [A-34]
    BG          = "#090a12"       # Deep CRT obsidian backing
    PANEL       = "#0d0f1e"       # CRT phosphor glass panel
    PANEL2      = "#121528"       # Elevated tactical module layer
    PANEL_BG    = "rgba(13, 15, 30, 0.96)"
    BORDER      = "#222748"       # Precision CRT frame line
    BORDER_B    = "#505bb5"       # Bright glowing phosphorescent border
    BORDER_A    = "#343a6b"       # Subtle division grid rule
    PRI         = "#8e9bff"       # Electric CRT Phosphor Lavender / Indigo
    PRI_DIM     = "#5463cc"       # Medium phosphor bloom
    PRI_GHO     = "#1a1d36"       # Phosphor ghost backdrop glow
    ACC         = "#ff7390"       # Tactical dossier alert red
    ACC2        = "#ffd166"       # Telemetry warning amber
    GREEN       = "#4ef2bb"       # Phosphor matrix emerald
    GREEN_D     = "#228562"       # Muted green bio-metric
    RED         = "#ff2a55"       # Threat assessment crimson
    CYAN        = "#00f0ff"       # High-tech focus cyan
    MUTED       = "#707ab0"       # Muted terminal readout
    MUTED_C     = "#ff3366"       # Silence protocol neon
    TEXT        = "#e8ecff"       # Crisp luminescent CRT white-blue
    TEXT_DIM    = "#707ab0"       # Muted terminal readout
    TEXT_MED    = "#a6b2f0"       # Medium high-tech CRT readout
    TEXT_MUTED  = "#707ab0"       # Muted phosphor readout alias
    TEXT_BRIGHT = "#ffffff"       # Pure laser highlight
    WHITE       = "#f4f6ff"       # Clean CRT white
    DARK        = "#05060a"       # Deep shadow floor
    BAR_BG      = "#101222"       # Metric meter channel track


# Monospaced Retro-Futuristic Terminal Typography (OCR / CRT Matrix / Cascadia)
_TECH_FONT_FAMILIES = (
    "JetBrains Mono", "Fira Code", "Consolas", "Courier New",
    "Cascadia Code", "SF Mono", "monospace"
)
_MONO_FONT_FAMILIES = (
    "JetBrains Mono", "Fira Code", "Consolas", "Courier New",
    "Cascadia Code", "SF Mono", "monospace"
)


def tech_font(size: int | float, weight: QFont.Weight = QFont.Weight.Normal, letter_spacing: float | None = None) -> QFont:
    f = QFont()
    f.setFamilies(list(_TECH_FONT_FAMILIES))
    if isinstance(size, float):
        f.setPointSizeF(size)
    else:
        f.setPointSize(int(size))
    f.setWeight(weight)
    f.setStyleHint(QFont.StyleHint.Monospace)
    if letter_spacing is not None:
        spacing = letter_spacing / 50.0 if letter_spacing > 5.0 else letter_spacing
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def mono_font(size: int | float, weight: QFont.Weight = QFont.Weight.Normal, letter_spacing: float | None = None) -> QFont:
    f = QFont()
    f.setFamilies(list(_MONO_FONT_FAMILIES))
    if isinstance(size, float):
        f.setPointSizeF(size)
    else:
        f.setPointSize(int(size))
    f.setWeight(weight)
    f.setStyleHint(QFont.StyleHint.Monospace)
    if letter_spacing is not None:
        spacing = letter_spacing / 50.0 if letter_spacing > 5.0 else letter_spacing
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


HOVER_HELP_DELAY_MS: int = 600


class TacticalHoverHelpManager(QObject):
    """
    Centralized, single-timer hover help manager for ALFRED settings and controls.
    Avoids per-control timers, manages delayed tooltips on sustained hover and keyboard focus,
    and cleanly dismisses help on leave, tab change, panel close, or rapid pointer sweeps.
    """
    _instance: TacticalHoverHelpManager | None = None

    @classmethod
    def instance(cls) -> TacticalHoverHelpManager:
        if cls._instance is None:
            cls._instance = TacticalHoverHelpManager()
        return cls._instance

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._help_map: dict[QWidget, str] = {}
        self._target_widget: QWidget | None = None

    def register(self, widget: QWidget, text: str, label_widget: QWidget | None = None) -> None:
        if not widget or not text:
            return
        clean_text = text.strip()
        widget.setToolTip(clean_text)
        widget.setAccessibleDescription(clean_text)
        self._help_map[widget] = clean_text
        widget.installEventFilter(self)

        if label_widget is not None:
            label_widget.setToolTip(clean_text)
            self._help_map[label_widget] = clean_text
            label_widget.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        etype = event.type()
        if etype in (QEvent.Type.Enter, QEvent.Type.FocusIn):
            if isinstance(obj, QWidget) and obj in self._help_map:
                if self._target_widget is not obj:
                    self.dismiss()
                self._target_widget = obj
                self._timer.stop()
                self._timer.start(HOVER_HELP_DELAY_MS)
        elif etype in (QEvent.Type.Leave, QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.MouseButtonPress):
            if self._target_widget is obj or etype == QEvent.Type.MouseButtonPress:
                self.dismiss()
        return False

    def _on_timeout(self) -> None:
        if self._target_widget is None:
            return
        try:
            if not self._target_widget.isVisible() or self._target_widget not in self._help_map:
                self.dismiss()
                return
            text = self._help_map[self._target_widget]
            pos = self._target_widget.mapToGlobal(QPoint(0, self._target_widget.height() + 4))
            QToolTip.showText(pos, text, self._target_widget)
        except Exception:
            self.dismiss()

    def dismiss(self) -> None:
        self._timer.stop()
        QToolTip.hideText()
        self._target_widget = None


def attach_hover_help(widget: QWidget, text: str, label_widget: QWidget | None = None) -> None:
    """Convenience helper to attach descriptive long-hover help to a setting widget and optional label."""
    TacticalHoverHelpManager.instance().register(widget, text, label_widget)


_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "TEXT", "TEXT_DIM", "TEXT_MED", "TEXT_BRIGHT",
    "WHITE", "DARK", "BAR_BG", "ACC", "ACC2", "GREEN", "GREEN_D", "RED", "MUTED_C", "MUTED",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = "#8e9bff"


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Applies structured theme from ThemeRegistry matching the given hex or id,
    or smoothly interpolates custom hex codes across class C while updating ThemeChrome.
    """
    global _ACTIVE_THEME_ID
    import colorsys
    from core.ui.themes import ThemeRegistry, ThemeChrome

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        # Look up by theme id
        theme = ThemeRegistry.instance().get_by_id(accent_hex)
        if theme:
            accent_hex = theme.hex.lower()
        else:
            return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    reg = ThemeRegistry.instance()
    matched_theme = reg.get_by_hex(accent_hex) or reg.get_by_id(accent_hex)
    if matched_theme is not None:
        _ACTIVE_THEME_ID = matched_theme.id
        for k, v in matched_theme.palette.to_dict().items():
            if hasattr(C, k):
                setattr(C, k, v)
        ThemeChrome.set_active(matched_theme)
        return True

    # Fallback hue shift for custom user-picked hexes from color wheel
    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h = _hsv(DEFAULT_UI_COLOR)[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08

    active_theme = ThemeChrome.get_active()
    tmpl = active_theme.palette.to_dict()

    for key in _HUE_LINKED:
        hex0 = tmpl.get(key, getattr(C, key))
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """A snapshot of the accent-linked colours currently on class C."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    LIVE full theme change. Replaces the old palette colours with the new ones
    in EVERY widget's stylesheet across the app and repaints them. This way the
    colour change applies INSTANTLY across the whole interface — panels, buttons,
    borders included — not just the painted elements. No restart needed.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ── Windows GPU via NVML DLL (no subprocess, no console window) ──────────────
_nvml_lib: object = None   # cached ctypes DLL
_nvml_ok:  object = None   # None=untested, True=works, False=unavailable


def _nvml_gpu_windows() -> float:
    """Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        import ctypes

        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            for dll_name in ("nvml", r"C:\Windows\System32\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(dll_name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        util = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util))
        _nvml_ok = True
        return float(util.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self.proc_count = 0
        self.uptime_str = "--:--"
        try:
            self._boot_time = psutil.boot_time()
        except Exception:
            self._boot_time = time.time()
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        # Probe caches — GPU (NVML) and temperature (WMI) are the expensive
        # queries; initialise their handles once and reuse them instead of
        # rebuilding a connection on every poll.
        self._slow_tick = 0            # gpu/temp refreshed every 3rd cycle
        self._pynvml    = None         # cached pynvml module + device handle
        self._pynvml_h  = None
        self._pynvml_ok = None         # None=untested, False=unavailable here
        self._nv_unix   = None         # cached (lib, dev) for Linux/macOS NVML
        self._wmi_conn  = None         # cached WMI connection (creating one is slow)
        self._wmi_ok    = None         # None=untested, False=unavailable here
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(2.0)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        # GPU and temperature change slowly and are the most expensive probes
        # (NVML / WMI) — refresh them every 3rd cycle (~6 s) instead of every
        # cycle, reusing the previous reading in between.
        self._slow_tick = (self._slow_tick + 1) % 3
        if self._slow_tick == 1:
            gpu = self._get_gpu()
            tmp = self._get_temp()
        else:
            gpu = self.gpu
            tmp = self.tmp

        # Process count & uptime (evaluated in background worker thread, NOT Qt main thread)
        try:
            proc_count = len(psutil.pids())
        except Exception:
            proc_count = getattr(self, "proc_count", 0)

        elapsed = time.time() - self._boot_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        uptime_str = f"{h:02d}:{m:02d}"

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp
            self.proc_count = proc_count
            self.uptime_str = uptime_str

    def _get_gpu(self) -> float:
        # pynvml — subprocess-free; initialise once and reuse the handle.
        # Re-initialising NVML on every poll is slow, so cache it and stop
        # retrying pynvml entirely once it proves unavailable here.
        if self._pynvml_ok is not False:
            try:
                if self._pynvml_h is None:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=FutureWarning)
                        import pynvml  # type: ignore
                    pynvml.nvmlInit()
                    self._pynvml    = pynvml
                    self._pynvml_h  = pynvml.nvmlDeviceGetHandleByIndex(0)
                    self._pynvml_ok = True
                return float(self._pynvml.nvmlDeviceGetUtilizationRates(self._pynvml_h).gpu)
            except Exception:
                self._pynvml_ok = False

        # Windows: nvml.dll via ctypes (already cached in _nvml_gpu_windows)
        if _OS == "Windows":
            return _nvml_gpu_windows()

        # Linux / macOS: libnvidia-ml shared lib via ctypes — init once, reuse
        try:
            import ctypes

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            if self._nv_unix is None:
                _lib = "libnvidia-ml.so.1" if _OS == "Linux" else "libnvidia-ml.dylib"
                nv = ctypes.CDLL(_lib)
                nv.nvmlInit_v2()
                dev = ctypes.c_void_p()
                nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
                self._nv_unix = (nv, dev)

            nv, dev = self._nv_unix
            u = _Util()
            nv.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            return float(u.gpu)
        except Exception:
            pass

        return -1.0   # N/A — zero subprocess on all platforms

    def _get_temp(self) -> float:
        # psutil — works on Linux; occasionally Windows with driver support
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                         "cpu-thermal", "zenpower", "it8688"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        # Windows: wmi module (pure Python COM, zero subprocess). Reuse a single
        # connection — building a fresh wmi.WMI() on every poll spins up a COM
        # connection each time and is very slow. Give up after one failure.
        if _OS == "Windows" and self._wmi_ok is not False:
            try:
                if self._wmi_conn is None:
                    import wmi  # type: ignore
                    self._wmi_conn = wmi.WMI(namespace="root/wmi")
                tz = self._wmi_conn.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                self._wmi_ok   = False
                self._wmi_conn = None

        return -1.0   # N/A — zero subprocess on all platforms

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
                "proc": self.proc_count,
                "uptime": self.uptime_str,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    _req_sentry_snapshot = pyqtSignal(object)
    _req_start_animations = pyqtSignal()

    def __init__(self, face_path: str, assistant_name: str = "J.A.R.V.I.S", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._req_sentry_snapshot.connect(self._apply_sentry_snapshot)
        self._req_start_animations.connect(self._do_start_animations)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = assistant_name

        # Centrepiece is always the Batcomputer Tactical Core (globe/waveform).
        self.hud_style = "reactive"
        self._core_phase = 0.0

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._step_t     = time.time()
        self._blink      = True
        self._blink_tick = 0

        # Rescaled-face cache: the smooth rescale is expensive, so we keep the
        # last result and only rebuild it when the (quantised) size changes.

        # Static HUD decoration is cached per size/theme. Rebuilding the grid,
        # scanlines and watermark in every paint consumed most of a frame on the
        # software QPainter backend and could starve the audio writer under load.
        self._static_layers: dict[tuple, QPixmap] = {}
        self._emblem_cache_key = None
        self._emblem_cache: QPixmap | None = None
        # Repaint throttle counter (idle frames drop to ~20 Hz — see _step()).
        self._paint_tick = 0

        # Live audio reactivity: _live_amp is written from the audio threads
        # (0.0–1.0), _amp_disp is the smoothed value the paint code reads.
        self._live_amp  = 0.0
        self._amp_disp  = 0.0
        # (frames, start_time, hop) posted by the playback thread — see
        # push_visemes(). None means "no schedule; use the plain level".
        self._visemes = None
        self._vis_i = None        # first schedule frame not yet handed to the mouth
        self._base_scale = 1.0    # slow "breathing" target; amp is added per-frame
        self._base_halo  = 55.0

        # Dynamic cyber-particle matrix & holographic scanline for Stark / Wayne HUD
        self._particles = [
            {
                'x': random.uniform(0.01, 0.99),
                'y': random.uniform(0.01, 0.99),
                'vx': random.uniform(-0.0006, 0.0006),
                'vy': random.uniform(-0.0008, 0.0008),
                'vx0': 0.0,  # base velocity stored for wake-burst recovery
                'vy0': 0.0,
                'size': random.uniform(1.2, 2.5),
                'alpha': random.uniform(0.20, 0.65),
                'phase': random.uniform(0, math.pi * 2),
            }
            for _ in range(24)
        ]
        # Store base velocities for wake-burst recovery
        for _pt in self._particles:
            _pt['vx0'] = _pt['vx']
            _pt['vy0'] = _pt['vy']
        self._scanline_y = 0.0

        # Speech-reactive animation state (Phase A/B/C)
        # Plosive flash: brightens globe wires on MBP/FV closures for 2 frames
        self._plosive_flash = 0.0      # 0.0–1.0, decays per step
        # Wake-burst: one-shot radial velocity kick when SLEEPING→LISTENING
        self._wake_burst_t  = 0.0      # wall-clock time of last burst
        self._last_state    = "INITIALISING"  # tracks state transitions
        # Viseme values exposed to paint methods (written in _step, read in paint)
        self._vis_open  = 0.0   # 0.0=closed, 1.0=fully open (vowel AA)
        self._vis_wide  = 0.0   # -1.0=rounded (O/U), +1.0=wide smile (E/I)
        self._vis_close = 0.0   # 1.0=plosive closure (M/B/P), else 0.0
        self._vis_level = 0.0   # audio level at current viseme frame
        self._speech_energy = 0.0
        self._speech_started_at = 0.0
        self._particle_visibility = 1.0
        self._state_transition_from = self.state
        self._state_transition_at = time.time()
        self.on_visual_level = None
        self._sentry_snapshot: SentrySnapshot | None = None
        self._paint_error_logged = False
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(33)

    def _start_animations(self) -> None:
        """Guarantee the HUD animation step timer is started unconditionally."""
        if not is_gui_thread():
            self._req_start_animations.emit()
            return
        self._do_start_animations()

    def _do_start_animations(self) -> None:
        assert_gui_thread("HudCanvas._do_start_animations")
        if not hasattr(self, "_tmr") or self._tmr is None:
            self._tmr = QTimer(self)
            self._tmr.timeout.connect(self._step)
        if not self._tmr.isActive():
            self._tmr.start(16)

    def set_sentry_snapshot(self, snapshot: SentrySnapshot | None) -> None:
        """Update Sentry Mode (FOCUS / MONITOR) state on the HUD canvas."""
        if not is_gui_thread():
            self._req_sentry_snapshot.emit(snapshot)
            return
        self._apply_sentry_snapshot(snapshot)

    def _apply_sentry_snapshot(self, snapshot: SentrySnapshot | None) -> None:
        assert_gui_thread("HudCanvas.set_sentry_snapshot")
        self._sentry_snapshot = snapshot
        if self._on_screen():
            self.update()
        if self._tmr is None or not self._tmr.isActive():
            self._do_start_animations()

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """No-op: gaze tracking removed (face renderer removed)."""
        pass

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: hand over a schedule of (level, openness, width) frames.

        The playback thread writes up to 200 ms of audio in one go, so a single
        averaged level would only move the mouth five times a second — enough to
        flap, nowhere near enough to articulate. It instead posts the whole
        slice's worth of 20 ms frames here and `_step()` plays them out against
        the wall clock, in step with the audio going to the speakers.

        `at` is the wall-clock time this batch will *begin to sound*, which the
        caller tracks as a playback cursor. It is not the time of the call, and
        the difference is the whole point: `stream.write` returns once the buffer
        accepts the samples, so consecutive batches are handed over far faster
        than they play. Anchoring each one to "now" made every batch start while
        its predecessor was still sounding, so each schedule replaced the last
        after a couple of frames and the mouth only ever played the opening
        instant of every 200 ms — the reason it did not match the words.

        Successive batches are therefore *appended* into one continuous
        timeline, not swapped in. A paragraph is one schedule; the mouth stops
        falling into a gap at every chunk boundary and having to climb back out.
        """
        try:
            if not frames:
                return
            hop = max(1e-3, float(hop))
            at = float(at)
            new = list(frames)
            cur = self._visemes
            if cur is not None:
                old, t0, ohop = cur
                if abs(ohop - hop) < 1e-6:
                    # Where in the existing timeline does this batch land?
                    i = int(round((at - t0) / hop))
                    if 0 <= i <= len(old) + 1:
                        # Continues (or slightly overlaps) what is already
                        # queued: extend rather than restart. Drop whatever has
                        # already been played so the list cannot grow without
                        # bound over a long reply.
                        merged = old[:i] + new
                        played = int((time.time() - t0) / hop) - 2
                        if played > 60:
                            merged = merged[played:]
                            t0 += played * hop
                            if self._vis_i is not None:
                                self._vis_i = max(0, self._vis_i - played)
                        self._visemes = (merged, t0, hop)
                        return
            self._visemes = (new, at, hop)
            self._vis_i = None
        except Exception:
            pass

    def set_audio_level(self, level: float) -> None:
        """Thread-safe entry point for the audio threads. Stores the louder of
        the incoming level and the current value so brief gaps between chunks
        don't make the waveform stutter; _step() decays it back down."""
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        if lv < 0.0:
            lv = 0.0
        elif lv > 1.0:
            lv = 1.0
        if lv > self._live_amp:
            self._live_amp = lv

    def _make_grid(self, W: int, H: int) -> QPixmap:
        """Pre-render the static grid-dot background into a transparent pixmap so
        paintEvent can blit it once per frame instead of running a nested
        drawPoint() loop across the whole widget every 16 ms."""
        pm = QPixmap(max(1, W), max(1, H))
        pm.fill(Qt.GlobalColor.transparent)
        gp = QPainter(pm)
        gp.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                gp.drawPoint(x, y)
        gp.end()
        return pm

    def _remember_static_layer(self, key: tuple, layer: QPixmap) -> None:
        """Keep a small LRU-like set of full-canvas layers."""
        self._static_layers.pop(key, None)
        self._static_layers[key] = layer
        while len(self._static_layers) > 8:
            oldest = next(iter(self._static_layers))
            self._static_layers.pop(oldest, None)

    def _step(self):
        self._tick += 1
        now = time.time()

        # ── Live audio reactivity ────────────────────────────────────────────
        # A viseme schedule, if one is playing, gives both the level and the
        # mouth shape for this exact instant; otherwise fall back to the peak
        # level the audio threads pushed in.
        v_open = v_wide = v_level = None
        v_seq = None
        sched = self._visemes
        if sched is not None:
            frames, t0, hop = sched
            i = int((now - t0) / hop)
            if 0 <= i < len(frames):
                # Hand over *every* frame since the last tick, not just the one
                # under the cursor. This timer runs at 60 Hz but the paint is
                # throttled and the machine may be busy, so a tick can span two
                # or three 20 ms frames — and a consonant closure is only two
                # frames long. Sampling one and discarding the rest is how the
                # closures between words went missing.
                j = self._vis_i if self._vis_i is not None else i
                v_seq = frames[max(0, j):i + 1]
                self._vis_i = max(j, i + 1)
                v_level, v_open, v_wide = frames[i]
                if v_seq:
                    peak = max(f[0] for f in v_seq)
                    if peak > self._live_amp:
                        self._live_amp = peak
            elif i >= len(frames):
                self._visemes = None        # schedule spent
                self._vis_i = None

        # Audio threads push peaks into _live_amp; decay it toward silence so
        # gaps between chunks fade out instead of freezing, then smooth it.
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        amp = self._amp_disp

        # The avatar animates off the very same smoothed level the waveform
        # uses — one audio source, so the mouth can never drift out of sync.
        dt = now - self._step_t
        self._step_t = now
        # Keep speech energy after playback ends so the globe coasts back to its
        # idle speed instead of snapping there on the final audio frame.
        if self.speaking:
            if self._speech_started_at <= 0.0:
                self._speech_started_at = now
            _speech_target = max(amp, float(v_level or 0.0))
            self._speech_energy += (_speech_target - self._speech_energy) * 0.42
        else:
            self._speech_started_at = 0.0
            self._speech_energy *= math.exp(-min(0.10, max(0.0, dt)) / 0.45)

        # Phase A: integrate speech acceleration here so every globe element
        # shares one smooth phase and never jumps when the state changes.
        _rate = 1.0 + self._speech_energy * 3.5
        if self.state in ("THINKING", "PROCESSING"):
            _rate += 2.2
        self._core_phase += min(0.10, max(0.0, dt)) * _rate

        # Globe/waveform core: slow "breathing" base target, lifted by the level.
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._base_scale = 1.03
                self._base_halo  = 122.0
            elif self.muted:
                self._base_scale = random.uniform(0.998, 1.002)
                self._base_halo  = random.uniform(15, 28)
            else:
                self._base_scale = random.uniform(1.001, 1.008)
                self._base_halo  = random.uniform(48, 68)
            self._last_t = now

        if self.muted:
            self._tgt_scale, self._tgt_halo = self._base_scale, self._base_halo
        elif self.speaking:
            self._tgt_scale = self._base_scale + amp * 0.13
            # Viseme level tracks phonemes more tightly than the smoothed peak.
            self._tgt_halo = self._base_halo + max(amp, self._vis_level) * 95.0
        else:
            self._tgt_scale = self._base_scale + amp * 0.06
            self._tgt_halo  = self._base_halo  + amp * 75.0

        sp = 0.38 if self.speaking else (0.30 if amp > 0.02 else 0.15)
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        # ── Phase A: Plosive flash decay ─────────────────────────────────────
        # When the current viseme is a hard closure (M, B, P, F, V), we set a
        # plosive_flash value that decays over ~4 frames and brightens globe
        # wireframe lines for a percussive visual pop in sync with the consonant.
        if v_open is not None:
            self._vis_open  = float(v_open)
            self._vis_wide  = float(v_wide or 0.0)
            self._vis_level = float(v_level or 0.0)
            # Detect plosive: v_open < 0.05 means lips are pressed shut
            if v_open < 0.05:
                self._vis_close = 1.0
                self._plosive_flash = 1.0
            else:
                self._vis_close = 0.0
        else:
            # No viseme schedule — smoothly drift back to resting position
            self._vis_open  += (0.0 - self._vis_open)  * 0.12
            self._vis_wide  += (0.0 - self._vis_wide)  * 0.12
            self._vis_close += (0.0 - self._vis_close) * 0.18
            self._vis_level += (0.0 - self._vis_level) * 0.18
        # Decay plosive flash regardless (lasts ~3-4 frames)
        self._plosive_flash = max(0.0, self._plosive_flash - 0.28)

        # ── Phase C: Particle energy driven by state ─────────────────────────
        _prev_state = self._last_state
        _cur_state  = self.state

        if _prev_state != _cur_state:
            self._state_transition_from = _prev_state
            self._state_transition_at = now

        # Detect SLEEPING→LISTENING wake-up transition → radial burst
        if _prev_state == "SLEEPING" and _cur_state not in ("SLEEPING", "INITIALISING"):
            self._wake_burst_t = now
            for _pt in self._particles:
                # Kick each particle radially outward from center
                _dx = _pt['x'] - 0.5
                _dy = _pt['y'] - 0.5
                _d = max(0.01, math.sqrt(_dx*_dx + _dy*_dy))
                _pt['vx'] = (_dx / _d) * 0.012
                _pt['vy'] = (_dy / _d) * 0.009
        self._last_state = _cur_state

        _burst_age = now - self._wake_burst_t
        _in_burst  = _burst_age < 0.55  # burst lasts 0.55 s then particles settle

        for pt in self._particles:
            if _in_burst:
                # Gradually recover to resting velocity over burst window
                _settle = min(1.0, _burst_age / 0.55)
                pt['vx'] += (pt['vx0'] - pt['vx']) * _settle * 0.08
                pt['vy'] += (pt['vy0'] - pt['vy']) * _settle * 0.08
            elif _cur_state == "SLEEPING" or getattr(self, 'muted', False):
                # Sleep: slow fade — particles drift to minimal alpha & speed
                pt['vx'] *= 0.97
                pt['vy'] *= 0.97
            elif _cur_state in ("THINKING", "PROCESSING"):
                # Thinking: pull inward while following a clockwise tangent.
                _dx = pt['x'] - 0.5
                _dy = pt['y'] - 0.5
                _target_vx = -_dy * 0.0018 - _dx * 0.00045
                _target_vy =  _dx * 0.0018 - _dy * 0.00045
                pt['vx'] += (_target_vx - pt['vx']) * 0.08
                pt['vy'] += (_target_vy - pt['vy']) * 0.08
            elif self.speaking and not getattr(self, 'muted', False):
                # Speaking: velocity boosted by audio amplitude
                _spk_boost = 1.0 + amp * 3.8
                pt['vx'] = pt['vx0'] * _spk_boost
                pt['vy'] = pt['vy0'] * _spk_boost
            else:
                # Listening idle: drift back toward base velocity
                pt['vx'] += (pt['vx0'] - pt['vx']) * 0.04
                pt['vy'] += (pt['vy0'] - pt['vy']) * 0.04

            pt['x'] = (pt['x'] + pt['vx']) % 1.0
            pt['y'] = (pt['y'] + pt['vy']) % 1.0
            pt['phase'] = (pt['phase'] + 0.04) % (math.pi * 2)
        _particle_target = 0.12 if (_cur_state == "SLEEPING" or self.muted) else 1.0
        self._particle_visibility += (
            _particle_target - self._particle_visibility
        ) * (1.0 - math.exp(-min(0.10, max(0.0, dt)) / 0.55))
        self._scanline_y = (self._scanline_y + 0.0028) % 1.0

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
            _blinked = True
        else:
            _blinked = False

        # Repaint throttling — advancing the animation state above is cheap at
        # 60 Hz, but the paint is heavy. Active (speaking, audio, thinking) runs
        # at ~30 Hz, which is the frame rate animation has used for talking
        # characters forever and is indistinguishable here; idle drops to ~20 Hz
        # so a sleeping HUD stops pinning a CPU core. The visuals stay smooth
        # either way because the animation state keeps stepping at 60 Hz.
        self._paint_tick = (self._paint_tick + 1) % 6
        active = (self.speaking or amp > 0.02
                  or self.state in ("THINKING", "PROCESSING"))
        if _blinked or (self._paint_tick % 2 == 0 if active
                        else self._paint_tick % 3 == 0):
            if self.on_visual_level is not None:
                try:
                    self.on_visual_level(
                        amp,
                        self.state == "LISTENING" and not self.muted,
                    )
                except Exception:
                    pass
            # Nothing is on screen when the window is hidden or minimised, so
            # rendering the avatar into it is pure waste — and this app is meant
            # to sit running all day. The animation state above keeps stepping,
            # so it picks up mid-motion instead of snapping when you come back.
            if self._on_screen():
                self.update()

    def _on_screen(self) -> bool:
        """True only when this canvas can actually be seen by the user."""
        try:
            if not self.isVisible():
                return False
            win = self.window()
            return not (win.isMinimized() or win.isHidden())
        except Exception:
            return True      # never let a visibility check stop the HUD drawing

    # ── reactor core ─────────────────────────────────────────────────────────
    # The centrepiece for anyone who did not want a face looking back at them.
    # Built from the same budget as the head — software QPainter, no GPU — and
    # from the same principle: everything on it means something. The rings turn
    # at a rate the state sets, the spectrum ring is the real audio level, and
    # the core brightens with the voice. Nothing here is decoration that moves
    # for its own sake, which is what made the old glowing orb feel dead.

    def _core_colours(self):
        if self.muted:
            return qcol(C.MUTED_C), qcol(C.MUTED_C)
        if self.speaking:
            return qcol(C.PRI), qcol(C.ACC)
        if self.state in ("THINKING", "PROCESSING"):
            return qcol(C.PRI), qcol(C.ACC2)
        if self.state == "LISTENING":
            return qcol(C.PRI), qcol(C.GREEN)
        return qcol(C.PRI), qcol(C.PRI_DIM)

    def _paint_core(self, p: QPainter, cx: float, cy: float, r: float,
                    W: float = 0.0, H: float = 0.0):
        """Draw the Avengers: Endgame Stark Arc Reactor at (cx, cy) with outer radius r."""
        main, acc = self._core_colours()
        bg = qcol(C.BG)
        amp = self._amp_disp
        t = self._core_phase
        live = (self.speaking or amp > 0.04) and not self.muted

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        p.setBrush(Qt.BrushStyle.NoBrush)

        # 1. Quantum Arc Energy Atmosphere (Deep radial multi-layer bloom)
        lift = 1.0 + 0.95 * amp + (0.40 if self.speaking else 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        for gr, a0 in ((r * 0.90, 0.22), (r * 0.60, 0.35), (r * 0.38, 0.55), (r * 0.20, 0.70)):
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0.00, blend(main, min(0.95, a0 * lift)))
            g.setColorAt(0.35, blend(main, min(0.95, a0 * lift * 0.55)))
            g.setColorAt(0.70, blend(main, min(0.95, a0 * lift * 0.18)))
            g.setColorAt(1.00, blend(main, 0.0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Precision Stark Corner Reticles & Telemetry Badges
        if W > 60 and H > 60:
            m, arm = min(W, H) * 0.035, min(W, H) * 0.06
            p.setPen(QPen(blend(main, 0.45), 1.4))
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                x = cx + sx * (W / 2 - m)
                y = cy + sy * (H / 2 - m)
                p.drawLine(QLineF(x, y, x - sx * arm, y))
                p.drawLine(QLineF(x, y, x, y - sy * arm))
                p.setPen(QPen(blend(main, 0.25), 1.0))
                p.drawLine(QLineF(x - sx * 4, y, x - sx * 8, y))
                p.drawLine(QLineF(x, y - sy * 4, x, y - sy * 8))

            # Corner micro telemetry tags
            f_tele = tech_font(7, QFont.Weight.Medium, letter_spacing=1.0)
            p.setFont(f_tele)
            p.setPen(QPen(blend(main, 0.40), 1))
            p.drawText(QRectF(cx - W / 2 + m + 6, cy - H / 2 + m, 120, 14),
                       Qt.AlignmentFlag.AlignLeft, "MK-IV // ARC-GEN")
            p.drawText(QRectF(cx + W / 2 - m - 126, cy - H / 2 + m, 120, 14),
                       Qt.AlignmentFlag.AlignRight, "FREQ 142.8MHz")
            p.drawText(QRectF(cx - W / 2 + m + 6, cy + H / 2 - m - 14, 120, 14),
                       Qt.AlignmentFlag.AlignLeft, "FLUX: 99.8%")
            p.drawText(QRectF(cx + W / 2 - m - 126, cy + H / 2 - m - 14, 120, 14),
                       Qt.AlignmentFlag.AlignRight, "WAYNE ENTERPRISES")

        # 3. Holographic Reticle Crosshairs with Precision Target Gaps
        p.setPen(QPen(blend(main, 0.16), 1))
        gap = r * 0.58
        if W > 40:
            p.drawLine(QLineF(cx - W / 2, cy, cx - gap, cy))
            p.drawLine(QLineF(cx + gap, cy, cx + W / 2, cy))
        if H > 40:
            p.drawLine(QLineF(cx, cy - H / 2, cx, cy - gap))
            p.drawLine(QLineF(cx, cy + gap, cx, cy + H / 2))

        # 4. Concentric High-Tech Outer Rings
        for rr, a, wid in ((1.00, 0.35, 1.2), (0.94, 0.20, 1.0), (0.86, 0.15, 1.0)):
            rad = r * rr
            p.setPen(QPen(blend(main, a), wid))
            p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # 5. Laser Calibration Graduations (72 radial ticks with 12 primary markers)
        major, minor = [], []
        for i in range(72):
            ang = math.radians(i * 5.0)
            ca, sa = math.cos(ang), math.sin(ang)
            if i % 6 == 0:
                major.append(QLineF(cx + ca * r * 0.88, cy + sa * r * 0.88,
                                    cx + ca * r * 0.99, cy + sa * r * 0.99))
            else:
                minor.append(QLineF(cx + ca * r * 0.94, cy + sa * r * 0.94,
                                    cx + ca * r * 0.99, cy + sa * r * 0.99))
        p.setPen(QPen(blend(main, 0.55), 1.4))
        p.drawLines(major)
        p.setPen(QPen(blend(main, 0.22), 1.0))
        p.drawLines(minor)

        # 6. Cardinal Telemetry Digits [000, 090, 180, 270] on outer calibration band
        f_card = tech_font(7, QFont.Weight.Bold, letter_spacing=0.5)
        p.setFont(f_card)
        p.setPen(QPen(blend(main, 0.50), 1))
        p.drawText(QRectF(cx - 15, cy - r * 1.06, 30, 12), Qt.AlignmentFlag.AlignCenter, "000")
        p.drawText(QRectF(cx + r * 1.01, cy - 6, 26, 12), Qt.AlignmentFlag.AlignLeft, "090")
        p.drawText(QRectF(cx - 15, cy + r * 1.00, 30, 12), Qt.AlignmentFlag.AlignCenter, "180")
        p.drawText(QRectF(cx - r * 1.01 - 26, cy - 6, 26, 12), Qt.AlignmentFlag.AlignRight, "270")

        # 7. Segmented Rotating Nano-Aperture Ring (36 interlocking gear notches)
        n_teeth = 36
        aperture_r = r * 0.77
        tooth_lines = []
        base_rot = (t * 8.0) % 360.0
        for i in range(n_teeth):
            ang = math.radians(i * (360.0 / n_teeth) + base_rot)
            ca, sa = math.cos(ang), math.sin(ang)
            tooth_lines.append(QLineF(cx + ca * (aperture_r - 2.5), cy + sa * (aperture_r - 2.5),
                                      cx + ca * (aperture_r + 2.5), cy + sa * (aperture_r + 2.5)))
        p.setPen(QPen(blend(main, 0.28), 1.2))
        p.drawLines(tooth_lines)

        # 8. Smooth Kinetic Energy Arcs (Endgame Counter-Rotating Holo-Rings)
        arc_layers = (
            (0.965, 95,  3, +1, 14.0, acc,  0.80, 2.2),
            (0.895, 140, 2, -1, 10.0, main, 0.50, 1.8),
            (0.820, 60,  4, +1, 20.0, acc,  0.65, 1.5),
            (0.740, 110, 2, -1, 15.0, main, 0.40, 1.4),
            (0.640, 45,  5, +1, 28.0, main, 0.35, 1.2),
            (0.560, 120, 2, -1, 18.0, acc,  0.55, 1.6),
        )

        for rr, span, count, dirn, spd, col, a, wid in arc_layers:
            rad = r * rr
            p.setPen(QPen(blend(col, a), wid))
            box = QRectF(cx - rad, cy - rad, rad * 2, rad * 2)
            base = (t * spd * dirn) % 360.0
            step = 360.0 / count
            for sgm in range(count):
                start_deg = base + sgm * step
                p.drawArc(box, int(start_deg * 16), int(span * 16))

                # Glowing Orbital Nano-Pips on leading edges of primary arcs
                if rr > 0.80:
                    lead_rad = math.radians(start_deg + (span if dirn > 0 else 0))
                    px = cx + math.cos(lead_rad) * rad
                    py = cy + math.sin(lead_rad) * rad
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(blend(qcol(C.WHITE), 0.9)))
                    p.drawEllipse(QPointF(px, py), 2.2, 2.2)
                    p.setBrush(Qt.BrushStyle.NoBrush)

        # 9. Quantum Audio Burst / Frequency Reactor Needles
        n_spikes = 64
        ring_spk = r * 0.44
        spikes = []
        for i in range(n_spikes):
            ang = math.radians(i * (360.0 / n_spikes) + t * 8.0)
            ca, sa = math.cos(ang), math.sin(ang)
            wob = 0.5 + 0.5 * math.sin(t * 3.2 + i * 0.5)
            idle = 0.02 + 0.015 * math.sin(t * 1.5 + i * 0.8)
            h = r * (idle + (amp * 0.22 * wob if live else 0.0))
            spikes.append(QLineF(cx + ca * ring_spk, cy + sa * ring_spk,
                                 cx + ca * (ring_spk + h), cy + sa * (ring_spk + h)))
        p.setPen(QPen(blend(acc if live else main, 0.40 + 0.55 * amp), 1.5))
        p.drawLines(spikes)

        # 10. Reactor Core Triad Magnetic Containment Nodes (Iconic Mark 85 Arc Triad)
        tri_r = r * 0.38
        p.setPen(QPen(blend(main, 0.65), 1.8))
        for i in range(3):
            c_ang = math.radians(i * 120.0 + t * 4.0)
            ca, sa = math.cos(c_ang), math.sin(c_ang)
            # Dual containment rails
            p.drawLine(QLineF(cx + ca * (tri_r - 5), cy + sa * (tri_r - 5),
                              cx + ca * (tri_r + 9), cy + sa * (tri_r + 9)))
            # Glowing power capacitor
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(blend(acc, 0.90)))
            p.drawEllipse(QPointF(cx + ca * (tri_r + 10), cy + sa * (tri_r + 10)), 3.0, 3.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(blend(main, 0.65), 1.8))

        # 6 Secondary Flux Nodes
        coil_r = r * 0.38
        p.setPen(QPen(blend(main, 0.40), 1.2))
        for i in range(6):
            if i % 2 != 0:
                c_ang = math.radians(i * 60.0 + t * 4.0)
                ca, sa = math.cos(c_ang), math.sin(c_ang)
                p.drawLine(QLineF(cx + ca * (coil_r - 3), cy + sa * (coil_r - 3),
                                  cx + ca * (coil_r + 5), cy + sa * (coil_r + 5)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(blend(main, 0.70)))
                p.drawEllipse(QPointF(cx + ca * (coil_r + 6), cy + sa * (coil_r + 6)), 1.8, 1.8)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(blend(main, 0.40), 1.2))

        # 11. Inner Central Quantum Core Lens
        inner_r = r * 0.34
        core_box = QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        # Multi-stop Obsidian Glass Lens Gradient with rich inner glow
        core_grad = QRadialGradient(cx, cy, inner_r)
        core_grad.setColorAt(0.00, blend(main, 0.32 + 0.58 * amp))
        core_grad.setColorAt(0.50, blend(main, 0.14 + 0.28 * amp))
        core_grad.setColorAt(0.85, blend(qcol(C.DARK), 0.95))
        core_grad.setColorAt(1.00, blend(main, 0.65 + 0.35 * amp))
        p.setBrush(QBrush(core_grad))
        p.setPen(QPen(blend(acc if live else main, 0.85), 2.0))
        p.drawEllipse(core_box)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Internal Quantum Hexagon Emitter Grid (faint cyber lattice inside the lens)
        hex_pts = []
        hex_r = inner_r * 0.65
        for h in range(6):
            h_ang = math.radians(h * 60.0 - t * 3.0)
            hex_pts.append(QPointF(cx + math.cos(h_ang) * hex_r, cy + math.sin(h_ang) * hex_r))
        p.setPen(QPen(blend(main, 0.18 + 0.15 * amp), 1.0))
        for h in range(6):
            p.drawLine(hex_pts[h], hex_pts[(h + 1) % 6])
            p.drawLine(hex_pts[h], QPointF(cx, cy))

        # Specular 3D glass reflection arc at top of lens
        p.setPen(QPen(blend(qcol(C.WHITE), 0.42), 1.5))
        p.drawArc(core_box, 35 * 16, 110 * 16)

        # 12. The Assistant Designation (Crisp Laser-White Typography with Emissive Glow)
        name = self._assistant_name or ""
        if name:
            space = max(1.2, inner_r * 0.05)
            fsz = max(9, int(min(inner_r * 0.26, (inner_r * 1.8) / max(1, len(name)) * 1.5 - space)))
            f = tech_font(fsz, QFont.Weight.Bold, letter_spacing=space)
            p.setFont(f)

            # Glow shadow for laser typography
            p.setPen(QPen(blend(main, 0.55 + 0.40 * amp), 2))
            p.drawText(QRectF(cx - inner_r + 1, cy - fsz + 1, inner_r * 2, fsz * 2),
                       Qt.AlignmentFlag.AlignCenter, name)

            # Laser crisp text
            p.setPen(QPen(blend(qcol(C.WHITE), 0.92 + 0.08 * min(1.0, amp * 2)), 1))
            p.drawText(QRectF(cx - inner_r, cy - fsz, inner_r * 2, fsz * 2),
                       Qt.AlignmentFlag.AlignCenter, name)

    def _paint_crt_grid(self, p: QPainter, W: float, H: float):
        """Draw subtle background CRT coordinate grid with + crosshairs (Screenshot 2)."""
        main, _ = self._core_colours()
        bg = qcol(C.BG)

        width, height = max(1, int(W)), max(1, int(H))
        key = ("crt-grid", width, height, int(main.rgba()), int(bg.rgba()))
        cached = self._static_layers.get(key)
        if cached is not None:
            p.drawPixmap(0, 0, cached)
            return

        layer = QPixmap(width, height)
        layer.fill(Qt.GlobalColor.transparent)
        lp = QPainter(layer)
        lp.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        step = 44
        lp.setPen(QPen(blend(main, 0.07), 1))
        for x in range(0, width + step, step):
            lp.drawLine(x, 0, x, height)
        for y in range(0, height + step, step):
            lp.drawLine(0, y, width, y)

        # Crosshairs at intersections
        lp.setPen(QPen(blend(main, 0.18), 1))
        crosshairs = []
        for x in range(0, width + step, step):
            for y in range(0, height + step, step):
                crosshairs.append(QLineF(x - 3, y, x + 3, y))
                crosshairs.append(QLineF(x, y - 3, x, y + 3))
        lp.drawLines(crosshairs)
        lp.end()

        self._static_layers = {
            cache_key: pixmap for cache_key, pixmap in self._static_layers.items()
            if cache_key[1:3] == (width, height)
        }
        self._remember_static_layer(key, layer)
        p.drawPixmap(0, 0, layer)

    def _paint_3d_vector_globe(self, p: QPainter, cx: float, cy: float, r: float, W: float, H: float):
        """
        3D Rotating Vector Wireframe Globe (Matching Screenshot 2: WAKU CRT Globe).
        Features:
          - Real-time 3D coordinate projection with continuous yaw rotation and pitch tilt.
          - 7 Latitude parallel rings (Equator dashed DashLine as in Screenshot 2).
          - 12 Longitude meridians rotating smoothly around the sphere.
          - Depth-based illumination (bright front side with glow, attenuated back side).
          - Tilted Orbital Satellite Ring (35 deg tilt) with 4 numbered satellite nodes
            ('24', '25', '34', '09') and radial connection tethers.
          - 8 Polar radiating coordinate rays with calibration tick marks.
          - Outer horizon boundary circle with glowing specular rim.
        """
        amp = self._amp_disp
        live = (self.speaking or amp > 0.03) and not self.muted
        main, acc = self._core_colours()
        bg = qcol(C.BG)

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        from core.hud.visuals.central import get_central_skin
        from core.ui.themes import ThemeChrome
        skin = get_central_skin(ThemeChrome.get_active().id)

        t = self._core_phase
        # _core_phase already carries state/audio acceleration from _step().
        yaw = (t * 0.30) % (math.pi * 2)
        # Orbital tilt gently oscillates ±4° in sync with core phase for alive idle motion
        pitch = math.radians(22.0 + 4.0 * math.sin(t * 0.18))  # Axial tilt with breathing

        cos_p, sin_p = math.cos(pitch), math.sin(pitch)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)

        def project(lat_rad: float, lon_rad: float) -> tuple[float, float, float]:
            clat = math.cos(lat_rad)
            slat = math.sin(lat_rad)
            clon = math.cos(lon_rad)
            slon = math.sin(lon_rad)

            x0 = r * clat * slon
            y0 = -r * slat
            z0 = r * clat * clon

            # Rotate yaw around Y
            x1 = x0 * cos_y + z0 * sin_y
            y1 = y0
            z1 = -x0 * sin_y + z0 * cos_y

            # Rotate pitch around X
            x2 = x1
            y2 = y1 * cos_p - z1 * sin_p
            z2 = y1 * sin_p + z1 * cos_p

            return (cx + x2, cy + y2, z2)

        p.setBrush(Qt.BrushStyle.NoBrush)

        # ── 1. Outer Horizon Circle ──────────────────────────────────────────
        # Phase A: Plosive flash brightens the outer ring for one moment
        _pf = getattr(self, '_plosive_flash', 0.0)
        _halo_boost = 0.28 * amp + _pf * 0.45
        p.setPen(QPen(blend(main, 0.38 + _halo_boost), 2.2 + _pf * 1.8))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        p.setPen(QPen(blend(main, min(1.0, 0.88 + _pf * 0.12)), 1.2))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ── 2. Latitude Parallel Rings ───────────────────────────────────────
        n_rings = max(3, skin.ring_count)
        lat_step = 140.0 / max(1, n_rings - 1)
        lat_angles = [-70.0 + i * lat_step for i in range(n_rings)]
        lat_front: list[QLineF] = []
        lat_back: list[QLineF] = []
        equator_front: list[QLineF] = []
        equator_back: list[QLineF] = []
        for deg in lat_angles:
            is_equator = (abs(deg) < (lat_step * 0.45))
            lat_r = math.radians(deg)
            n_samples = 64
            pts = [project(lat_r, math.radians(k * (360.0 / n_samples))) for k in range(n_samples + 1)]

            for k in range(n_samples):
                p1, p2 = pts[k], pts[k + 1]
                mid_z = (p1[2] + p2[2]) / 2.0
                line = QLineF(p1[0], p1[1], p2[0], p2[1])
                if is_equator:
                    (equator_front if mid_z >= 0 else equator_back).append(line)
                else:
                    (lat_front if mid_z >= 0 else lat_back).append(line)

        _wire_a = 0.70 + 0.30 * amp + _pf * 0.40
        p.setPen(QPen(blend(main, min(1.0, _wire_a)), 1.3 + _pf * 0.8))
        p.drawLines(lat_front)
        p.setPen(QPen(blend(main, 0.15), 0.9))
        p.drawLines(lat_back)
        p.setPen(QPen(blend(main, min(1.0, _wire_a)), 1.6 + _pf * 0.8, Qt.PenStyle.DashLine))
        p.drawLines(equator_front)
        p.setPen(QPen(blend(main, 0.15), 0.9, Qt.PenStyle.DotLine))
        p.drawLines(equator_back)

        # ── 3. Longitude Meridians (Rotating smoothly) ───────────────────────
        n_meridians = max(4, skin.meridian_count)
        meridian_front: list[QLineF] = []
        meridian_back: list[QLineF] = []
        for m in range(n_meridians):
            base_lon = math.radians(m * (360.0 / n_meridians))
            n_samples = 48
            pts = []
            for k in range(n_samples + 1):
                lat = math.radians(-85.0 + k * (170.0 / n_samples))
                pts.append(project(lat, base_lon))

            for k in range(n_samples):
                p1, p2 = pts[k], pts[k + 1]
                mid_z = (p1[2] + p2[2]) / 2.0
                line = QLineF(p1[0], p1[1], p2[0], p2[1])
                (meridian_front if mid_z >= 0 else meridian_back).append(line)

        p.setPen(QPen(blend(main, min(1.0, 0.65 + 0.30 * amp + _pf * 0.35)), 1.2 + _pf * 0.6))
        p.drawLines(meridian_front)
        p.setPen(QPen(blend(main, 0.12), 0.8))
        p.drawLines(meridian_back)

        # ── 4. Tilted Orbital Satellite Node Ring (Screenshot 2 Feature!) ────
        orb_r = r * 1.15
        orb_tilt = math.radians(skin.orbit_tilt_deg + 5.0 * math.sin(t * 0.22))
        cos_ot, sin_ot = math.cos(orb_tilt), math.sin(orb_tilt)

        def project_orbit(ang: float) -> tuple[float, float, float]:
            ox0 = orb_r * math.cos(ang)
            oy0 = 0.0
            oz0 = orb_r * math.sin(ang)

            # Tilted orbit around X
            ox1 = ox0
            oy1 = oy0 * cos_ot - oz0 * sin_ot
            oz1 = oy0 * sin_ot + oz0 * cos_ot

            # Apply sphere pitch
            ox2 = ox1
            oy2 = oy1 * cos_p - oz1 * sin_p
            oz2 = oy1 * sin_p + oz1 * cos_p

            return (cx + ox2, cy + oy2, oz2)

        # Draw orbital ring track
        n_orb_pts = 64
        orb_pts = [project_orbit(math.radians(k * (360.0 / n_orb_pts))) for k in range(n_orb_pts + 1)]
        orbit_front: list[QLineF] = []
        orbit_back: list[QLineF] = []
        for k in range(n_orb_pts):
            p1, p2 = orb_pts[k], orb_pts[k + 1]
            mid_z = (p1[2] + p2[2]) / 2.0
            line = QLineF(p1[0], p1[1], p2[0], p2[1])
            (orbit_front if mid_z >= 0 else orbit_back).append(line)
        p.setPen(QPen(blend(main, 0.45), 1.0, Qt.PenStyle.DashLine))
        p.drawLines(orbit_front)
        p.setPen(QPen(blend(main, 0.14), 1.0, Qt.PenStyle.DashLine))
        p.drawLines(orbit_back)

        # Satellite numbered node markers with skin-defined tags
        sat_tags = skin.orbit_nodes or ("01", "02", "03", "04")
        sat_count = len(sat_tags)
        sat_data = [
            (sat_tags[i], (i / max(1, sat_count)) * (math.pi * 2.0))
            for i in range(sat_count)
        ]
        sat_font = mono_font(6, QFont.Weight.Bold)
        p.setFont(sat_font)

        for sat_id, sat_offset in sat_data:
            node_ang = (t * 0.65 + sat_offset) % (math.pi * 2)
            nx, ny, nz = project_orbit(node_ang)
            if nz >= -r * 0.4:
                p.setPen(QPen(blend(main, 0.28), 1, Qt.PenStyle.DotLine))
                p.drawLine(QLineF(nx, ny, cx, cy))

                node_r = 7.5
                p.setBrush(QBrush(blend(bg, 0.92)))
                p.setPen(QPen(blend(acc if live else main, 0.95), 1.4))
                p.drawEllipse(QRectF(nx - node_r, ny - node_r, node_r * 2, node_r * 2))

                p.setPen(QPen(blend(qcol(C.WHITE), 0.95), 1))
                p.drawText(QRectF(nx - node_r, ny - node_r, node_r * 2, node_r * 2),
                           Qt.AlignmentFlag.AlignCenter, sat_id)
                p.setBrush(Qt.BrushStyle.NoBrush)

        # ── 5. Polar Radiating Coordinate Rays (Screenshot 2 Feature!) ───────
        px_north, py_north, _ = project(math.radians(90.0), 0.0)
        p.setPen(QPen(blend(main, 0.45), 1.0, Qt.PenStyle.DashLine))
        for i in range(8):
            ray_ang = math.radians(i * 45.0 + t * 4.0)
            rx = px_north + math.cos(ray_ang) * 26.0
            ry = py_north + math.sin(ray_ang) * 18.0
            p.drawLine(QLineF(px_north, py_north, rx, ry))

    def _paint_globe_waveforms(self, p: QPainter, cx: float, cy: float, W: float, H: float):
        """Futuristic Oscilloscope Waveforms spanning across the globe (Screenshot 1 & 2 synthesis)."""
        amp = self._amp_disp
        live = (self.speaking or amp > 0.03) and not self.muted
        main, acc = self._core_colours()
        if self.state in ("THINKING", "PROCESSING"):
            main = qcol(C.ACC2)
            acc = qcol(C.ACC)
        bg = qcol(C.BG)

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        vw = min(W - 40, 560.0)
        vx0 = cx - vw / 2.0
        vx1 = cx + vw / 2.0
        t = self._tick * 0.08

        # Guideline with calibration tick marks
        p.setPen(QPen(blend(main, 0.22), 1))
        p.drawLine(QLineF(vx0, cy, vx1, cy))
        ticks = []
        for step in range(0, int(vw), 20):
            tx = vx0 + step
            ticks.append(QLineF(tx, cy - 3, tx, cy + 3))
        p.setPen(QPen(blend(main, 0.35), 1))
        p.drawLines(ticks)

        # Telemetry Labels above the baseline
        f_tele = mono_font(7, QFont.Weight.Bold)
        p.setFont(f_tele)
        p.setPen(QPen(blend(main, 0.70), 1))
        p.drawText(QRectF(vx0, cy - 18, 160, 14), Qt.AlignmentFlag.AlignLeft,
                   f"FREQ // {142.8 + amp * 12.4:.1f} MHz")
        p.drawText(QRectF(vx1 - 160, cy - 18, 160, 14), Qt.AlignmentFlag.AlignRight,
                   f"LEVEL // {-28.0 + amp * 26.5:.1f} dB")

        # Phase B: Viseme-driven waveform lip-sync
        # v_open (0–1) scales waveform height — closed during plosives, fully
        # open on wide vowels (AA=0.92). v_wide (-1..+1) modulates frequency:
        # wide smiles (E, I, w>0) give a tighter, higher-frequency ripple;
        # rounded vowels (O, U, w<0) give a broad, slower wave.
        _v_open  = getattr(self, '_vis_open',  0.0)
        _v_wide  = getattr(self, '_vis_wide',  0.0)
        _v_close = getattr(self, '_vis_close', 0.0)
        _v_live  = getattr(self, '_vis_level', 0.0)

        # Blend viseme-driven level with smoothed amp for a natural feel
        _eff_amp = 0.65 * amp + 0.35 * _v_live if _v_live > 0.0 else amp

        # Height: scaled by openness, clamped to zero on plosive closure
        _open_scale = _v_open * (1.0 - _v_close)  # 0 when lips shut, full when open
        # Frequency: wide smile (E/I) → higher frequency; round (O/U) → lower
        _freq_scale = 1.0 + _v_wide * 0.55  # range 0.45 – 1.55

        # Multi-harmonic spline points. Longer replies gradually acquire one
        # extra harmonic without increasing point count or paint complexity.
        n_pts = 64
        _speech_age = (
            max(0.0, time.time() - self._speech_started_at)
            if self.speaking and self._speech_started_at > 0.0 else 0.0
        )
        _complexity = min(1.0, _speech_age / 8.0)
        # Idle waveform stays subtle; speech waveform reacts to openness
        _vis_active = _v_open > 0.04 or _v_close > 0.1
        if self.muted or self.state == "SLEEPING":
            h_max = 0.0
        elif _vis_active:
            h_max = 4.0 + _eff_amp * 42.0 * _open_scale + (1.5 * math.sin(t * 1.6))
        else:
            h_max = 5.0 + amp * 38.0 + (2.0 * math.sin(t * 1.6))
        pts_wave1 = []
        pts_wave2 = []

        for i in range(n_pts + 1):
            norm = i / float(n_pts)
            x = vx0 + norm * vw
            bell = math.sin(norm * math.pi) ** 1.35
            # Modulate sine frequency by _freq_scale (viseme width)
            _f1 = 14.0 * _freq_scale
            _f2 = 7.0  * _freq_scale
            w1 = (
                math.sin(norm * _f1 - t * 2.4) * 0.65
                + math.cos(norm * _f2 + t * 1.5) * 0.35
                + math.sin(norm * 27.0 + t * 3.2) * 0.16 * _complexity
            )
            y1 = cy - bell * w1 * h_max
            pts_wave1.append(QPointF(x, y1))

            _f3 = 16.0 * _freq_scale
            _f4 = 9.0  * _freq_scale
            w2 = (
                math.cos(norm * _f3 + t * 2.7) * 0.55
                + math.sin(norm * _f4 - t * 1.8) * 0.45
                + math.cos(norm * 24.0 - t * 2.9) * 0.13 * _complexity
            )
            y2 = cy + bell * w2 * (h_max * 0.75)
            pts_wave2.append(QPointF(x, y2))

        # Audio ribbon glow fill
        poly = QPainterPath()
        poly.moveTo(pts_wave1[0])
        for pt in pts_wave1[1:]:
            poly.lineTo(pt)
        for pt in reversed(pts_wave2):
            poly.lineTo(pt)
        poly.closeSubpath()

        fill_grad = QLinearGradient(0, cy - h_max, 0, cy + h_max)
        fill_grad.setColorAt(0.0, blend(main, min(0.38, 0.08 + amp * 0.45)))
        fill_grad.setColorAt(0.5, blend(main, min(0.18, 0.03 + amp * 0.22)))
        fill_grad.setColorAt(1.0, blend(acc,  min(0.32, 0.05 + amp * 0.38)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fill_grad))
        p.drawPath(poly)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Counter wave spline
        path2 = QPainterPath()
        path2.moveTo(pts_wave2[0])
        for pt in pts_wave2[1:]:
            path2.lineTo(pt)
        p.setPen(QPen(blend(acc, 0.60 + amp * 0.40), 1.3))
        p.drawPath(path2)

        # Primary wave spline
        path1 = QPainterPath()
        path1.moveTo(pts_wave1[0])
        for pt in pts_wave1[1:]:
            path1.lineTo(pt)
        p.setPen(QPen(blend(main, 0.45), 3.4))  # bloom
        p.drawPath(path1)
        p.setPen(QPen(blend(qcol(C.WHITE) if live else main, 0.95), 1.6))
        p.drawPath(path1)

        # Photon nodes on peaks
        p.setPen(Qt.PenStyle.NoPen)
        for k in (10, 21, 32, 43, 54):
            if k < len(pts_wave1):
                pt = pts_wave1[k]
                p.setBrush(QBrush(blend(qcol(C.WHITE), 0.95)))
                p.drawEllipse(pt, 2.2, 2.2)
                p.setBrush(QBrush(blend(main, 0.40 + 0.50 * amp)))
                p.drawEllipse(pt, 5.0, 5.0)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_hex_matrix_stream(self, p: QPainter, cx: float, cy: float, W: float, H: float):
        """Live cycling Hexadecimal & Telemetry stream (directly from Screenshot 1)."""
        main, _ = self._core_colours()
        bg = qcol(C.BG)

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        vw = min(W - 40, 540.0)
        vx0 = cx - vw / 2.0
        p.setFont(mono_font(6, QFont.Weight.Medium))
        p.setPen(QPen(blend(main, 0.48), 1))

        shift = (self._tick // 18) % 10
        r1 = f"49 08 89044 78 03877 00  23414 43 46291 {0x2A + shift:02X}  33418 90 10244"
        r2 = f"01 03 05689 27 30001 70  34107 10120 40 75111 {0x81 - shift:02X}  12904 55 98120"
        r3 = f"10 34 33913 79 00161 57  88911 00080 55 78972 {0x4F + shift:02X}  89765 12 40019"

        p.drawText(QRectF(vx0, cy, vw, 11), Qt.AlignmentFlag.AlignCenter, r1)
        p.drawText(QRectF(vx0, cy + 12, vw, 11), Qt.AlignmentFlag.AlignCenter, r2)
        p.drawText(QRectF(vx0, cy + 24, vw, 11), Qt.AlignmentFlag.AlignCenter, r3)

    def _paint_status_highlight_banner(self, p: QPainter, cx: float, cy: float, W: float, H: float):
        """High-Impact Inverted Phosphor Status Banner (Screenshot 2: 'PROTECTING YOUR PRIVACY IS WAKU'S GOAL')."""
        main, acc = self._core_colours()
        bg = qcol(C.BG)

        sentry_snap = self._sentry_snapshot
        foc = sentry_snap.focus if sentry_snap else None
        mon = sentry_snap.monitor if sentry_snap else None

        if foc and foc.active:
            mins = max(0, foc.remaining_s) // 60
            secs = max(0, foc.remaining_s) % 60
            time_str = f"{mins:02d}:{secs:02d}"

            if foc.paused:
                txt = f"⏸  FOCUS PAUSED [{time_str}] // RESUME WHEN READY"
                bar_col = qcol(C.MUTED_C)
            elif foc.drifting:
                txt = f"⚠  FOCUS DRIFTING [{time_str}] // RETURN TO TARGET SURFACE"
                bar_col = qcol(C.RED)
            elif foc.deferred_lock:
                txt = f"◉  FOCUS INITIALIZED [{time_str}] // AWAITING TARGET LOCK"
                bar_col = qcol(C.CYAN)
            else:
                txt = f"◉  FOCUS MODE ACTIVE [{time_str}] // ON TARGET"
                bar_col = qcol(C.CYAN)

        elif mon and mon.active:
            if mon.waiting_for_answer:
                txt = "◈  SENTRY MONITOR ACTIVE // AWAITING TARGET SPECIFICATION"
                bar_col = qcol(C.ACC2)
            else:
                label_txt = f" ({mon.label})" if mon.label else ""
                txt = f"◈  SCREEN MONITOR ACTIVE{label_txt.upper()}"
                bar_col = qcol(C.GREEN)

        elif self.muted:
            txt = "⊘  SILENCE PROTOCOL ENGAGED // ACOUSTICS MUTED"
            bar_col = qcol(C.MUTED_C)
        elif self.speaking:
            txt = "●  REACTIVE HUD // VOCAL SYNTHESIS ACTIVE // ALFRED MK-IV"
            bar_col = main
        elif self.state in ("THINKING", "PROCESSING"):
            txt = "NEURAL INFERENCE ACTIVE // PROCESSING DIRECTIVE"
            bar_col = qcol(C.ACC2)
        elif self.state == "LISTENING":
            txt = "●  REACTIVE HUD // LISTENING ACTIVE // DIRECTIVE READY"
            bar_col = main
        else:
            txt = "PROTECTING YOUR PRIVACY IS ALFRED'S DIRECTIVE."
            bar_col = main

        # Cross-fade state colour inside the existing HUD timer. This avoids a
        # second animation object/timer and keeps rapid state changes coherent.
        fade = min(1.0, max(0.0, (time.time() - self._state_transition_at) / 0.28))
        if fade < 1.0:
            old_state = self._state_transition_from
            if old_state == "MUTED":
                old_col = qcol(C.MUTED_C)
            elif old_state in ("THINKING", "PROCESSING"):
                old_col = qcol(C.ACC2)
            elif old_state == "LISTENING":
                old_col = qcol(C.PRI)
            else:
                old_col = qcol(C.PRI)
            bar_col = QColor(
                int(old_col.red() + (bar_col.red() - old_col.red()) * fade),
                int(old_col.green() + (bar_col.green() - old_col.green()) * fade),
                int(old_col.blue() + (bar_col.blue() - old_col.blue()) * fade),
            )

        bw = min(W - 48, 540.0)
        bx = cx - bw / 2.0
        by = cy
        bh = 22.0

        p.fillRect(QRectF(bx, by, bw, bh), bar_col)
        p.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.0))
        p.setPen(QPen(bg, 1))
        text_rect = QRectF(bx + 24.0, by, bw - 32.0, bh)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, txt)

        icon_cx = bx + 14.0
        icon_cy = by + bh / 2.0
        if self.state in ("THINKING", "PROCESSING") and not self.muted:
            spinner = QRectF(icon_cx - 5.0, icon_cy - 5.0, 10.0, 10.0)
            p.setPen(QPen(bg, 1.8))
            p.drawArc(spinner, int((-self._core_phase * 150.0) % 360.0) * 16, 250 * 16)
        else:
            pulse_level = self._vis_level if self.speaking else self._amp_disp
            radius = 2.5 + min(1.0, pulse_level) * 3.5
            p.setPen(QPen(bg, 1.2))
            p.setBrush(QBrush(bg))
            p.drawEllipse(QPointF(icon_cx, icon_cy), 2.4, 2.4)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(icon_cx, icon_cy), radius, radius)

    def _paint_crt_scanlines_and_reticles(self, p: QPainter, W: float, H: float):
        """Authentic CRT Scanlines, Corner Brackets, and Viewport Telemetry."""
        main, _ = self._core_colours()
        width, height = max(1, int(W)), max(1, int(H))
        key = ("crt-overlay", width, height, int(main.rgba()))
        cached = self._static_layers.get(key)
        if cached is not None:
            p.drawPixmap(0, 0, cached)
            return

        layer = QPixmap(width, height)
        layer.fill(Qt.GlobalColor.transparent)
        lp = QPainter(layer)
        lp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        arm = 14.0
        m = 10.0
        lp.setPen(QPen(main, 1.6))
        # Top-Left
        lp.drawLine(QLineF(m, m, m + arm, m))
        lp.drawLine(QLineF(m, m, m, m + arm))
        # Top-Right
        lp.drawLine(QLineF(W - m, m, W - m - arm, m))
        lp.drawLine(QLineF(W - m, m, W - m, m + arm))
        # Bottom-Left
        lp.drawLine(QLineF(m, H - m, m + arm, H - m))
        lp.drawLine(QLineF(m, H - m, m, H - m - arm))
        # Bottom-Right
        lp.drawLine(QLineF(W - m, H - m, W - m - arm, H - m))
        lp.drawLine(QLineF(W - m, H - m, W - m, H - m - arm))

        # Viewport micro telemetry
        f_badge = mono_font(6, QFont.Weight.Bold)
        lp.setFont(f_badge)
        lp.setPen(QPen(QColor(main.red(), main.green(), main.blue(), 160), 1))
        lp.drawText(QRectF(m + 4, m + 2, 180, 12), Qt.AlignmentFlag.AlignLeft, "SUBJECT ALFRED.MK-IV // VECTOR HUD")
        lp.drawText(QRectF(W - m - 184, m + 2, 180, 12), Qt.AlignmentFlag.AlignRight, "ORBITAL MATRIX: 4 ACTIVE")
        lp.drawText(QRectF(m + 4, H - m - 14, 180, 12), Qt.AlignmentFlag.AlignLeft, "COORDS: 42°19'N 71°05'W")
        lp.drawText(QRectF(W - m - 184, H - m - 14, 180, 12), Qt.AlignmentFlag.AlignRight, "WAYNE TECH PROTOCOL MK-IV")

        # Subtle CRT scanlines every 3px
        scan_col = QColor(main.red(), main.green(), main.blue(), 12)
        lp.setPen(QPen(scan_col, 1))
        scan_lines = [QLineF(0, y, W, y) for y in range(0, int(H), 3)]
        lp.drawLines(scan_lines)
        lp.end()
        self._remember_static_layer(key, layer)
        p.drawPixmap(0, 0, layer)

    def _paint_holographic_audio_display(self, p: QPainter, cx: float, cy: float, W: float, H: float):
        """Secondary audio display fallback if needed."""
        self._paint_globe_waveforms(p, cx, cy, W, H)

    def _draw_custom_emblem(self, p: QPainter, cx: float, cy: float, max_w: float, max_h: float) -> bool:
        """Always draw the authentic Wayne Crest watermark behind the Batcomputer UI."""
        cfg_dir = Path(__file__).resolve().parent / "config"
        # The background watermark is always the Wayne Crest (batman_logo.png / alfred_bg.png)
        candidates = [cfg_dir / "batman_logo.png", cfg_dir / "alfred_bg.png"]

        for fp in candidates:
            if fp.exists():
                try:
                    key = (str(fp), max(1, int(max_w)), max(1, int(max_h)))
                    if self._emblem_cache_key != key or self._emblem_cache is None:
                        source = QPixmap(str(fp))
                        self._emblem_cache = source.scaled(
                            key[1], key[2],
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self._emblem_cache_key = key
                    pm = self._emblem_cache
                    if not pm.isNull():
                        nw = pm.width()
                        nh = pm.height()
                        if nw > 0 and nh > 0:
                            p.save()
                            p.setOpacity(0.35 + 0.10 * math.sin(self._tick * 0.05))
                            p.drawPixmap(int(cx - nw / 2), int(cy - nh / 2), pm)
                            p.restore()
                            return True
                except Exception:
                    pass
                break
        return False


    def paintEvent(self, _):
        try:
            W, H = self.width(), self.height()
            if W <= 1 or H <= 1:
                return
            p = QPainter(self)
            if not p.isActive():
                return
            try:
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.fillRect(self.rect(), qcol(C.BG))

                cx, cy = W / 2, H / 2
                fw = min(W, H)
                amp = self._amp_disp
                main, acc = self._core_colours()
                bg = qcol(C.BG)

                def blend(col: QColor, a: float) -> QColor:
                    k = max(0.0, min(1.0, a))
                    return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                                  int(bg.green() + (col.green() - bg.green()) * k),
                                  int(bg.blue()  + (col.blue()  - bg.blue())  * k))

                # 1. Subtle CRT coordinate background grid with crosshairs (Screenshot 2)
                self._paint_crt_grid(p, W, H)

                # 2. Dynamic particles & constellation links
                p.setPen(Qt.PenStyle.NoPen)
                pts_coords = []
                _is_sleeping = (self.state == "SLEEPING")
                _is_thinking = (self.state in ("THINKING", "PROCESSING"))
                _in_wake_burst = (time.time() - getattr(self, '_wake_burst_t', 0.0)) < 0.55
                for pt in self._particles:
                    px = pt['x'] * W
                    py = pt['y'] * H
                    pts_coords.append((px, py))
                    pulse = 0.6 + 0.4 * math.sin(pt['phase'] + self._tick * 0.05)
                    # Phase C: alpha driven by state. The shared visibility value eases
                    # over two seconds, so entering or leaving sleep never pops.
                    if _in_wake_burst:
                        _alpha_scale = 1.0    # full bright during burst
                    elif _is_thinking:
                        _alpha_scale = 0.70   # slight dim, focus inward
                    elif self.speaking:
                        _alpha_scale = 0.85 + 0.15 * amp  # brighter on speech
                    else:
                        _alpha_scale = 0.65
                    _alpha_scale *= self._particle_visibility
                    a = min(255, max(0, int(pt['alpha'] * pulse * 140 * _alpha_scale)))
                    p.setBrush(QBrush(blend(main, a / 255.0)))
                    # Phoneme level gives a tighter particle pulse than smoothed amp.
                    _level = max(amp, self._vis_level)
                    _sz_boost = (1.0 + _level * 0.60) if self.speaking else (1.0 + amp * 0.20)
                    sz = pt['size'] * _sz_boost
                    p.drawEllipse(QPointF(px, py), sz, sz)

                # Micro links
                p.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(len(pts_coords)):
                    px1, py1 = pts_coords[i]
                    for j in range(i + 1, min(i + 4, len(pts_coords))):
                        px2, py2 = pts_coords[j]
                        d2 = (px1 - px2)**2 + (py1 - py2)**2
                        if d2 < 3600:
                            dist = math.sqrt(d2)
                            p.setPen(QPen(blend(main, (1.0 - dist / 60.0) * 0.15), 1))
                            p.drawLine(QLineF(px1, py1, px2, py2))

                # 3. Always Wayne Crest background watermark emblem
                self._draw_custom_emblem(p, cx, cy * 0.65, fw * 0.42, fw * 0.42)

                # 4. Centerpiece Rendering: Batcomputer Tactical Core (Globe + Waveforms + Matrix)
                globe_r  = min(fw * 0.35, 175.0)
                globe_cy = cy * 0.72
                self._paint_3d_vector_globe(p, cx, globe_cy, globe_r, W, H)
                self._paint_globe_waveforms(p, cx, globe_cy + globe_r * 0.78, W, H)
                self._paint_hex_matrix_stream(p, cx, globe_cy + globe_r * 0.78 + 36.0, W, H)


                # 5. High-Impact Status Banner (Screenshot 2)
                self._paint_status_highlight_banner(p, cx, H - 34.0, W, H)

                # 6. CRT Screen Scanlines & Corner Brackets
                self._paint_crt_scanlines_and_reticles(p, W, H)
            finally:
                p.end()
        except Exception as exc:
            if not getattr(self, "_paint_error_logged", False):
                self._paint_error_logged = True
                import traceback
                print(f"[HUD] paintEvent exception: {exc}\n{traceback.format_exc()}")


# ── Tactical Theme-Aware Slot Host Widgets ──────────────────────────────────
class SlotHostWidget(QWidget):
    """
    Host container for a single themed HUD visual slot (0, 1, or 2).
    Features:
      - Dynamic theme-based visual resolution via core.hud.visuals.instantiate_visual()
      - Zero allocations in paintEvent: delegates to SlotVisual.paint() with prebuilt geometry
      - Performance watchdog: drops LOD if paint budget exceeded
      - Error isolation: fails gracefully to static glyph after VISUAL_MAX_ERRORS
      - Smooth crossfade on theme change
    """
    def __init__(self, slot_index: int, height: int = 120, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.setFixedHeight(height)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        from core.hud.visuals import instantiate_visual, HudSignals
        from core.ui.themes import ThemeChrome

        self._active_theme_id = ThemeChrome.get_active().id
        self._visual = instantiate_visual(self._active_theme_id, self.slot_index)
        self._last_t = time.monotonic()
        self._prepared = False

        # Register for theme updates
        ThemeChrome.add_listener(self._on_theme_changed)

        # Step timer for continuous animation (~20 Hz)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(50)

    def _on_theme_changed(self, theme) -> None:
        from core.hud.visuals import instantiate_visual
        if theme.id != self._active_theme_id:
            self._active_theme_id = theme.id
            if self._visual:
                self._visual.dispose()
            self._visual = instantiate_visual(theme.id, self.slot_index)
            self._prepared = False
            if self.isVisible():
                self.update()

    def _step(self) -> None:
        if not self.isVisible():
            return
        now = time.monotonic()
        dt = min(0.1, max(0.001, now - self._last_t))
        self._last_t = now

        if self._visual and not self._visual.disabled:
            # Build signals snapshot from system metrics & audio
            from core.hud.visuals import HudSignals
            signals = HudSignals()
            self._visual.tick(dt, signals)
            self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._prepared = False

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = float(self.width()), float(self.height())
        rect = QRectF(0.0, 0.0, W, H)

        from core.ui.themes import ThemeChrome
        theme = ThemeChrome.get_active()
        pal = theme.palette

        # Background panel fill
        p.fillRect(rect, qcol(pal.panel))

        if not self._prepared and self._visual:
            self._visual.prepare(pal, rect)
            self._prepared = True

        if self._visual and not self._visual.disabled:
            t0 = time.perf_counter()
            try:
                self._visual.paint(p, rect)
                cost_ms = (time.perf_counter() - t0) * 1000.0
                self._visual.record_paint_time(cost_ms)
            except Exception as exc:
                self._visual.error_count += 1
                if self._visual.error_count >= 3:
                    self._visual.disabled = True
                    print(f"[HUD] Visual disabled in slot {self.slot_index} due to repeated errors: {exc}")
                p.setPen(qcol(pal.pri))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"[SLOT {self.slot_index + 1} OFFLINE]")
        else:
            p.setPen(qcol(pal.text_dim))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"[SLOT {self.slot_index + 1} STANDBY]")


# Convenience Aliases for Left Panel Slots
class CRTReconWidget(SlotHostWidget):
    def __init__(self, parent=None):
        super().__init__(slot_index=0, height=132, parent=parent)


class BiometricFingerprintWidget(SlotHostWidget):
    def __init__(self, parent=None):
        super().__init__(slot_index=1, height=115, parent=parent)


class WireframePoseWidget(SlotHostWidget):
    def __init__(self, parent=None):
        super().__init__(slot_index=2, height=98, parent=parent)


class SubjectDossierCard(QWidget):
    """
    Tactical Dossier Card Widget (Screenshot 1: Exact recreation of SUBJECT A-34 metadata dossier).
    """
    def __init__(self, assistant_name="ALFRED.MK-IV", parent=None):
        super().__init__(parent)
        self.setFixedHeight(152)
        self._asst_name = assistant_name
        self._threat_state = "critical"

    def set_name(self, name: str):
        self._asst_name = name.upper()
        self.update()

    def set_threat_state(self, state: str):
        self._threat_state = (state or "critical").lower()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        main = qcol(C.PRI)
        bg = qcol(C.BG)

        def blend(col: QColor, a: float) -> QColor:
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        p.fillRect(self.rect(), qcol(C.PANEL))
        p.setPen(QPen(blend(main, 0.40), 1))
        p.drawRect(QRectF(1, 1, W - 2, H - 2))

        # Corner brackets ┌ ┐ └ ┘
        arm = 10.0
        p.setPen(QPen(blend(main, 0.95), 1.5))
        p.drawLine(QLineF(4, 4, 4 + arm, 4))
        p.drawLine(QLineF(4, 4, 4, 4 + arm))
        p.drawLine(QLineF(W - 4, 4, W - 4 - arm, 4))
        p.drawLine(QLineF(W - 4, 4, W - 4, 4 + arm))
        p.drawLine(QLineF(4, H - 4, 4 + arm, H - 4))
        p.drawLine(QLineF(4, H - 4, 4, H - 4 - arm))
        p.drawLine(QLineF(W - 4, H - 4, W - 4 - arm, H - 4))
        p.drawLine(QLineF(W - 4, H - 4, W - 4, H - 4 - arm))

        from core.ui.themes import ThemeChrome, SubjectValueMode
        ident = ThemeChrome.identity()

        # Subject name display according to theme mode
        if ident.subject_value_mode == SubjectValueMode.THEMATIC_CODENAME:
            subj_val = ident.codename
        elif ident.subject_value_mode == SubjectValueMode.HIDE:
            subj_val = "████████"
        else:
            subj_val = self._asst_name

        # Header Row
        p.setFont(mono_font(8, QFont.Weight.Bold))
        p.setPen(QPen(blend(main, 0.95), 1))
        p.drawText(QRectF(12, 7, 180, 14), Qt.AlignmentFlag.AlignLeft, ident.subject_label)
        p.setPen(QPen(blend(qcol(C.ACC), 0.95), 1))
        p.drawText(QRectF(W - 88, 7, 76, 14), Qt.AlignmentFlag.AlignRight, "[■■■■■]")

        p.setPen(QPen(blend(main, 0.25), 1))
        p.drawLine(QLineF(8, 24, W - 8, 24))

        threat_val = getattr(ident.threat_levels, getattr(self, "_threat_state", "critical"), ident.threat_levels.critical)
        rows = [
            ("NAME", subj_val),
            ("INCEPT DATE", ident.incept_date),
            ("FUNCTION", ident.function_line),
            ("MENTAL STATE", ident.mental_state),
            ("LAST KNOWN LOC", ident.location_line),
            (ident.threat_header, threat_val),
            ("SPECIAL SKILLS", ident.special_skills),
        ]

        f_key = mono_font(7, QFont.Weight.Bold)
        f_val = mono_font(7, QFont.Weight.DemiBold)
        sy = 30
        for k, v in rows:
            p.setFont(f_key)
            p.setPen(QPen(blend(main, 0.55), 1))
            p.drawText(QRectF(12, sy, 115, 14), Qt.AlignmentFlag.AlignLeft, k)
            p.setFont(f_val)
            if k == ident.threat_header:
                p.setPen(QPen(blend(qcol(C.ACC), 0.95), 1))
            elif k == "MENTAL STATE":
                p.setPen(QPen(blend(qcol(C.GREEN), 0.95), 1))
            else:
                p.setPen(QPen(blend(qcol(C.WHITE), 0.92), 1))
            p.drawText(QRectF(130, sy, W - 142, 14), Qt.AlignmentFlag.AlignLeft, v)
            sy += 16

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(40)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        v = max(0.0, min(100.0, pct))
        if v == self._value and text == self._text:
            return          # unchanged — skip the repaint
        self._value = v
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Apple iOS Glass Card backplate with Stark holographic tint
        card_rect = QRectF(1, 1, W - 2, H - 2)
        card_grad = QLinearGradient(0, 0, 0, H)
        card_grad.setColorAt(0.0, QColor(255, 255, 255, 12))
        card_grad.setColorAt(0.15, QColor(7, 22, 38, 210))
        card_grad.setColorAt(1.0, QColor(3, 12, 22, 230))
        p.setBrush(QBrush(card_grad))
        p.setPen(QPen(QColor(0, 240, 255, 38), 1))
        p.drawRoundedRect(card_rect, 8, 8)

        # Subtle nano-tech corner light pip (top-left)
        p.setPen(QPen(QColor(0, 240, 255, 120), 1))
        p.drawLine(QPointF(6, 2), QPointF(14, 2))

        bar_h   = 4.5
        bar_y   = H - bar_h - 7
        bar_w   = W - 16
        bar_x   = 8
        fill_w  = max(0.0, min(bar_w, bar_w * self._value / 100))

        # Pill Track background
        p.setBrush(QBrush(QColor(2, 10, 18, 220)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2.25, 2.25)

        if self._value > 85:
            bar_col = qcol(C.RED)
            bar_col2 = qcol("#ff5577")
        elif self._value > 65:
            bar_col = qcol(C.ACC)
            bar_col2 = qcol(C.ACC2)
        else:
            bar_col = qcol(self._color)
            bar_col2 = qcol(C.PRI)

        if fill_w > 0:
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, bar_col)
            grad.setColorAt(1.0, bar_col2)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2.25, 2.25)

        # Label - Clean modern SF Pro typography
        p.setFont(tech_font(8, QFont.Weight.DemiBold, letter_spacing=0.8))
        p.setPen(QPen(QColor(160, 220, 240), 1))
        p.drawText(QRectF(9, 4, 55, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        # Numeric readout - crisp laser typography
        p.setFont(mono_font(9, QFont.Weight.Bold))
        val_pen = QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1)
        p.setPen(val_pen)
        p.drawText(QRectF(0, 4, W - 9, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

# ── Tactical Audio Player Widgets (Bottom-Left Cyber Media Deck) ──────────────

class _EqualizerBarsWidget(QWidget):
    """Mini animated cyber audio wave visualizer."""
    def __init__(self, engine: TronScoreBackgroundPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self.setFixedSize(18, 14)
        self._tick = 0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(50)

    def _step(self):
        if self._engine.is_playing() and self.isVisible():
            self._tick += 1
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        bar_w = 2.5
        spacing = 1.2
        is_p = self._engine.is_playing()
        main_c = qcol(C.PRI)

        for i in range(4):
            x = 1.0 + i * (bar_w + spacing)
            if is_p:
                h = 3.0 + 8.0 * abs(math.sin(self._tick * 0.25 + i * 1.1))
            else:
                h = 2.5
            y = H - h - 1.0
            p.fillRect(QRectF(x, y, bar_w, h), QBrush(main_c))


class _VolumeSliderPopup(QFrame):
    """
    Sleek tactical cyber popup for adjusting master background music volume.
    Contains digital percentage readout, speech ducking indicator,
    horizontal gain slider, and quick-preset gain pills.
    """
    def __init__(self, engine: TronScoreBackgroundPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(194, 150)

        container = QWidget(self)
        container.setGeometry(0, 0, 194, 150)
        container.setStyleSheet(f"""
            QWidget {{
                background: {C.PANEL};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
        """)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # Header Row
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("◈ MASTER GAIN MATRIX")
        lbl.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.8))
        lbl.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        hdr_row.addWidget(lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setFont(mono_font(7, QFont.Weight.Bold))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; border: none; background: transparent;
            }}
            QPushButton:hover {{ color: #ff5577; }}
        """)
        close_btn.clicked.connect(self.close)
        hdr_row.addWidget(close_btn)
        lay.addLayout(hdr_row)

        # Large Readout Row
        self._val_lbl = QLabel(f"{int(self._engine.base_volume() * 100)}%")
        self._val_lbl.setFont(mono_font(13, QFont.Weight.Bold))
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val_lbl.setStyleSheet(f"color: {C.GREEN}; border: none; background: transparent;")
        lay.addWidget(self._val_lbl)

        # Ducking note
        self._duck_lbl = QLabel(f"SPEECH DUCK LEVEL: {int(self._engine.base_volume() * 50)}%")
        self._duck_lbl.setFont(mono_font(6, QFont.Weight.Normal))
        self._duck_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._duck_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
        lay.addWidget(self._duck_lbl)

        # QSlider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(self._engine.base_volume() * 100))
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {C.GREEN};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 1px solid {C.GREEN};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {C.GREEN};
            }}
        """)
        self._slider.valueChanged.connect(self._on_slider_moved)
        lay.addWidget(self._slider)

        # Presets Row [ 5% ] [ 10% ] [ 20% ] [ 50% ]
        p_row = QHBoxLayout()
        p_row.setContentsMargins(0, 0, 0, 0)
        p_row.setSpacing(3)
        for pct in (5, 10, 20, 50):
            pb = QPushButton(f"{pct}%")
            pb.setFixedHeight(18)
            pb.setFont(mono_font(6, QFont.Weight.DemiBold))
            pb.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2};
                    color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A};
                    border-radius: 2px;
                    padding: 0 2px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    border-color: {C.PRI};
                    background: rgba(142, 155, 255, 0.15);
                }}
            """)
            pb.clicked.connect(lambda _, v=pct: self._set_preset(v))
            p_row.addWidget(pb)
        lay.addLayout(p_row)

    def _on_slider_moved(self, val: int):
        self._val_lbl.setText(f"{val}%")
        self._duck_lbl.setText(f"SPEECH DUCK LEVEL: {int(val * 0.5)}%")
        self._engine.set_base_volume(val / 100.0)

    def _set_preset(self, val: int):
        self._slider.setValue(val)


class CyberGraphicLineButton(QPushButton):
    """
    Tactical button rendered strictly with vector graphic lines,
    sharp 2px border radius, and HUD theme glow instead of generic emoji text.
    """
    def __init__(self, mode: str = "play", parent=None):
        super().__init__(parent)
        self._mode = mode  # "prev" | "play" | "pause" | "next" | "loop"
        self._hovered = False
        self._pressed = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_mode(self, mode: str):
        if self._mode != mode:
            self._mode = mode
            self.update()

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0

        if self._mode in ("play", "pause"):
            active_col = qcol(C.GREEN)
            bg_col = QColor(active_col.red(), active_col.green(), active_col.blue(), 38) if self._hovered else QColor(active_col.red(), active_col.green(), active_col.blue(), 16)
            bdr_col = active_col if self._hovered else QColor(active_col.red(), active_col.green(), active_col.blue(), 90)
            line_col = QColor("#ffffff") if self._hovered else active_col
        else:
            active_col = qcol(C.PRI)
            bg_col = QColor(active_col.red(), active_col.green(), active_col.blue(), 30) if self._hovered else qcol(C.PANEL)
            bdr_col = active_col if self._hovered else qcol(C.BORDER_A)
            line_col = QColor("#ffffff") if self._hovered else (active_col if self._hovered else qcol(C.TEXT_MED))

        if self._pressed:
            bg_col = QColor(active_col.red(), active_col.green(), active_col.blue(), 60)

        # Draw cyber button background box
        p.fillRect(QRectF(1, 1, W - 2, H - 2), bg_col)
        p.setPen(QPen(bdr_col, 1))
        p.drawRect(QRectF(1, 1, W - 2, H - 2))

        # Setup crisp line pen
        pen = QPen(line_col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self._mode == "prev":
            # Left stop line
            p.drawLine(QLineF(cx - 5.0, cy - 5.5, cx - 5.0, cy + 5.5))
            # Leftward graphic chevron
            path = QPainterPath()
            path.moveTo(cx + 4.5, cy - 5.0)
            path.lineTo(cx - 2.5, cy)
            path.lineTo(cx + 4.5, cy + 5.0)
            path.closeSubpath()
            p.drawPath(path)
            if self._hovered:
                p.fillPath(path, QBrush(QColor(line_col.red(), line_col.green(), line_col.blue(), 50)))

        elif self._mode == "next":
            # Rightward graphic chevron
            path = QPainterPath()
            path.moveTo(cx - 4.5, cy - 5.0)
            path.lineTo(cx + 2.5, cy)
            path.lineTo(cx - 4.5, cy + 5.0)
            path.closeSubpath()
            p.drawPath(path)
            if self._hovered:
                p.fillPath(path, QBrush(QColor(line_col.red(), line_col.green(), line_col.blue(), 50)))
            # Right stop line
            p.drawLine(QLineF(cx + 5.0, cy - 5.5, cx + 5.0, cy + 5.5))

        elif self._mode == "play":
            # Sharp vector triangle
            path = QPainterPath()
            path.moveTo(cx - 3.5, cy - 5.5)
            path.lineTo(cx + 5.0, cy)
            path.lineTo(cx - 3.5, cy + 5.5)
            path.closeSubpath()
            p.drawPath(path)
            if self._hovered or self._pressed:
                p.fillPath(path, QBrush(QColor(line_col.red(), line_col.green(), line_col.blue(), 70)))

        elif self._mode == "pause":
            # Two crisp vertical graphic bars
            p.drawLine(QLineF(cx - 3.0, cy - 5.5, cx - 3.0, cy + 5.5))
            p.drawLine(QLineF(cx + 3.0, cy - 5.5, cx + 3.0, cy + 5.5))

        elif self._mode == "loop":
            # Vector loop bracket lines
            p.drawLine(QLineF(cx - 5.0, cy - 1.5, cx - 5.0, cy - 3.5))
            p.drawLine(QLineF(cx - 5.0, cy - 3.5, cx + 4.0, cy - 3.5))
            p.drawLine(QLineF(cx + 1.5, cy - 6.0, cx + 4.0, cy - 3.5))
            p.drawLine(QLineF(cx + 1.5, cy - 1.0, cx + 4.0, cy - 3.5))
            p.drawLine(QLineF(cx + 5.0, cy + 1.5, cx + 5.0, cy + 3.5))
            p.drawLine(QLineF(cx + 5.0, cy + 3.5, cx - 4.0, cy + 3.5))
            p.drawLine(QLineF(cx - 1.5, cy + 1.0, cx - 4.0, cy + 3.5))
            p.drawLine(QLineF(cx - 1.5, cy + 6.0, cx - 4.0, cy + 3.5))


class TacticalAudioPlayerWidget(QWidget):
    """
    Bottom-Left Cyber Tactical Audio Player Widget.
    Styled matching the HUD / Batcave / Beyond UI theme with sharp 2px corners,
    live visualizer equalizer bars, volume badge button with popup slider,
    track dropdown, and graphic line vector playback buttons.
    """
    def __init__(self, audio_engine: TronScoreBackgroundPlayer, parent=None):
        super().__init__(parent)
        self._engine = audio_engine
        self._vol_popup: _VolumeSliderPopup | None = None
        self.setFixedHeight(126)
        self.setMinimumWidth(160)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # ── 1. Top Header Row: Animated EQ + Title + Clickable Volume Pill ─
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._eq_widget = _EqualizerBarsWidget(self._engine)
        top_row.addWidget(self._eq_widget)

        self._hdr_lbl = QLabel("AUDIO CORE")
        self._hdr_lbl.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
        self._hdr_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        top_row.addWidget(self._hdr_lbl)

        top_row.addStretch()

        self._vol_btn = QPushButton("10%")
        self._vol_btn.setFont(mono_font(7, QFont.Weight.Bold))
        self._vol_btn.setFixedHeight(18)
        self._vol_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vol_btn.setToolTip("Click to adjust audio gain slider")
        self._vol_btn.clicked.connect(self._toggle_volume_popup)
        self._update_badge(False, self._engine.base_volume())
        top_row.addWidget(self._vol_btn)

        lay.addLayout(top_row)

        # ── 2. Track Title Row ─────────────────────────────────────────────
        self._track_lbl = QLabel(self._engine.current_track_stem())
        self._track_lbl.setFont(mono_font(7, QFont.Weight.Bold))
        self._track_lbl.setWordWrap(True)
        self._track_lbl.setMinimumHeight(36)
        self._track_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._track_lbl.setStyleSheet(f"""
            QLabel {{
                color: {C.TEXT};
                background: rgba(0, 0, 0, 0.25);
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 2px 4px;
            }}
        """)
        self._track_lbl.setToolTip(self._engine.current_track_name())
        lay.addWidget(self._track_lbl)

        # ── 3. Track Selector Dropdown + [ + LOAD ] Row ───────────────────
        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 0, 0, 0)
        sel_row.setSpacing(4)

        self._combo = QComboBox()
        self._combo.setFont(mono_font(6, QFont.Weight.Normal))
        self._combo.setFixedHeight(22)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._refresh_combo()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        sel_row.addWidget(self._combo)

        self._load_btn = QPushButton("+ LOAD")
        self._load_btn.setFont(mono_font(6, QFont.Weight.Bold))
        self._load_btn.setFixedHeight(22)
        self._load_btn.setFixedWidth(50)
        self._load_btn.setToolTip("Add or update music files (MP3, WAV, OGG, M4A, FLAC)")
        self._load_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 240, 255, 0.08);
                color: {C.PRI};
                border: 1px solid {C.BORDER_B};
                border-radius: 2px;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: #05060a;
                border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: #ffffff;
            }}
        """)
        self._load_btn.clicked.connect(self._on_load_clicked)
        sel_row.addWidget(self._load_btn)

        lay.addLayout(sel_row)

        # ── 4. Playback Graphic Line Controls: [ ⏮ ] [ ⏯ ] [ ⏭ ] [ 🔁 ] ─────
        ctl_row = QHBoxLayout()
        ctl_row.setContentsMargins(0, 0, 0, 0)
        ctl_row.setSpacing(4)

        self._btn_prev = CyberGraphicLineButton("prev")
        self._btn_prev.setFixedHeight(24)
        self._btn_prev.setMinimumWidth(32)
        self._btn_prev.setToolTip("Previous track")
        self._btn_prev.clicked.connect(self._engine.prev_track)
        ctl_row.addWidget(self._btn_prev)

        self._btn_play = CyberGraphicLineButton("pause" if self._engine.is_playing() else "play")
        self._btn_play.setFixedHeight(24)
        self._btn_play.setMinimumWidth(34)
        self._btn_play.setToolTip("Play / Pause background music")
        self._btn_play.clicked.connect(self._on_toggle_play)
        ctl_row.addWidget(self._btn_play)

        self._btn_next = CyberGraphicLineButton("next")
        self._btn_next.setFixedHeight(24)
        self._btn_next.setMinimumWidth(32)
        self._btn_next.setToolTip("Next track")
        self._btn_next.clicked.connect(self._engine.next_track)
        ctl_row.addWidget(self._btn_next)

        self._btn_loop = CyberGraphicLineButton("loop")
        self._btn_loop.setFixedHeight(24)
        self._btn_loop.setMinimumWidth(28)
        self._btn_loop.setToolTip("Continuous Loop (Always Active)")
        ctl_row.addWidget(self._btn_loop)

        lay.addLayout(ctl_row)

        # Connect signals
        self._engine.track_changed.connect(self._on_track_changed)
        self._engine.playback_state_changed.connect(self._on_playback_state_changed)
        self._engine.ducked_state_changed.connect(self._on_ducked_state_changed)
        self._engine.playlist_updated.connect(self._on_playlist_updated)

    def _toggle_volume_popup(self):
        if self._vol_popup is None:
            self._vol_popup = _VolumeSliderPopup(self._engine, self)

        if self._vol_popup.isVisible():
            self._vol_popup.close()
            return

        pt = self.mapToGlobal(QPoint(0, 0))
        pop_x = pt.x()
        pop_y = pt.y() - self._vol_popup.height() - 4
        if pop_y < 40:
            pop_y = pt.y() + self.height() + 4
        self._vol_popup.move(pop_x, pop_y)
        self._vol_popup.show()
        self._vol_popup.raise_()
        self._vol_popup.activateWindow()

    def _update_badge(self, is_ducked: bool, vol: float):
        if self._engine.source_mode() == "spotify":
            self._vol_btn.setEnabled(False)
            self._vol_btn.setText("LIVE" if self._engine.is_playing() else "PAUSED")
            self._vol_btn.setToolTip("Spotify volume is controlled by the active Connect device")
            self._vol_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {C.GREEN if self._engine.is_playing() else C.TEXT_DIM};
                    background: rgba(78, 242, 187, 0.08);
                    border: 1px solid rgba(78, 242, 187, 0.45);
                    border-radius: 2px;
                    padding: 1px 4px;
                }}
            """)
            return

        self._vol_btn.setEnabled(True)
        self._vol_btn.setToolTip("Click to adjust Audio Core gain")
        if not self._engine.is_playing():
            self._vol_btn.setText("PAUSED")
            self._vol_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {C.TEXT_DIM};
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid {C.BORDER};
                    border-radius: 2px;
                    padding: 1px 4px;
                }}
                QPushButton:hover {{
                    border-color: {C.PRI};
                    color: #ffffff;
                }}
            """)
        elif is_ducked:
            self._vol_btn.setText(f"DUCK {int(self._engine.base_volume() * 50)}%")
            self._vol_btn.setStyleSheet("""
                QPushButton {{
                    color: #ff5577;
                    background: rgba(255, 85, 119, 0.15);
                    border: 1px solid #ff5577;
                    border-radius: 2px;
                    padding: 1px 4px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 85, 119, 0.25);
                }}
            """)
        else:
            pct = int(self._engine.base_volume() * 100)
            self._vol_btn.setText(f"{pct}%")
            self._vol_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {C.GREEN};
                    background: rgba(78, 242, 187, 0.08);
                    border: 1px solid rgba(78, 242, 187, 0.45);
                    border-radius: 2px;
                    padding: 1px 4px;
                }}
                QPushButton:hover {{
                    border-color: {C.GREEN};
                    background: rgba(78, 242, 187, 0.20);
                }}
            """)

    def _refresh_combo(self):
        self._combo.blockSignals(True)
        self._combo.clear()

        # If Spotify is active, add it to the top of the selector
        if self._engine.source_mode() == "spotify" and self._engine.spotify_track():
            stitle = self._engine.current_track_stem()
            self._combo.addItem(f"◈ {stitle}", "spotify:current")

        plist = self._engine.playlist()
        curr_idx = 0
        for idx, p in enumerate(plist):
            label = "◈ TRON Legacy Score" if "The Son of Flynn" in p.stem else p.stem
            self._combo.addItem(label, str(p.resolve()))
            if self._engine.source_mode() != "spotify" and self._engine._current_path and p.resolve() == self._engine._current_path.resolve():
                curr_idx = self._combo.count() - 1

        if self._engine.source_mode() == "spotify":
            self._combo.setCurrentIndex(0)
        elif plist:
            self._combo.setCurrentIndex(curr_idx)

        self._combo.setStyleSheet(f"""
            QComboBox {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 1px 4px;
            }}
            QComboBox:hover {{ border-color: {C.PRI}; }}
            QComboBox::drop-down {{ border: none; width: 12px; }}
            QComboBox QAbstractItemView {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER_A};
                selection-background-color: {C.PRI_DIM};
                selection-color: #ffffff;
            }}
        """)
        self._combo.blockSignals(False)

    def _on_combo_changed(self, idx: int):
        data = self._combo.itemData(idx)
        if not data:
            return
        if data == "spotify:current":
            return
        # If user switches to TRON / local playlist track from combo
        p = Path(data)
        if p.exists():
            self._engine._source_mode = "tron"
            self._engine.load_track(p, auto_play=True)

    def _on_load_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File (Looping Background Score)",
            str(Path.cwd()),
            "Audio Files (*.mp3 *.wav *.ogg *.m4a *.flac);;All Files (*.*)",
        )
        if file_path:
            self._engine._source_mode = "tron"
            self._engine.add_and_play(file_path)

    def _on_track_changed(self, stem: str, path: str):
        if self._engine.source_mode() == "spotify":
            track = self._engine.spotify_track()
            title = track.get("title", "Spotify Track")
            artist = track.get("artist", "")
            self._hdr_lbl.setText("SPOTIFY // LIVE")
            self._track_lbl.setText(title + (f"\n{artist}" if artist else ""))
            self._track_lbl.setToolTip(self._engine.current_track_stem())
        else:
            self._hdr_lbl.setText("AUDIO CORE")
            self._track_lbl.setText(stem)
            self._track_lbl.setToolTip(path)
        self._refresh_combo()
        self._update_badge(self._engine._is_speaking_ducked, self._engine.base_volume())
        if hasattr(self, "_btn_play"):
            self._btn_play.set_mode("pause" if self._engine.is_playing() else "play")

    def _on_playback_state_changed(self, is_playing: bool):
        self._btn_play.set_mode("pause" if is_playing else "play")
        self._update_badge(self._engine._is_speaking_ducked, self._engine.base_volume())
        if hasattr(self, "_eq_widget") and self._eq_widget:
            self._eq_widget.update()

    def _on_ducked_state_changed(self, is_ducked: bool, target_vol: float):
        self._update_badge(is_ducked, target_vol)

    def _on_playlist_updated(self, _):
        self._refresh_combo()

    def _on_toggle_play(self):
        self._engine.toggle_play()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.fillRect(self.rect(), qcol(C.PANEL2))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRect(QRectF(1, 1, W - 2, H - 2))

        # Cyber corner brackets
        arm = 5.0
        p.setPen(QPen(qcol(C.PRI), 1.2))
        p.drawLine(QLineF(3, 3, 3 + arm, 3))
        p.drawLine(QLineF(3, 3, 3, 3 + arm))
        p.drawLine(QLineF(W - 3, 3, W - 3 - arm, 3))
        p.drawLine(QLineF(W - 3, 3, W - 3, 3 + arm))
        p.drawLine(QLineF(3, H - 3, 3 + arm, H - 3))
        p.drawLine(QLineF(3, H - 3, 3, H - 3 - arm))
        p.drawLine(QLineF(W - 3, H - 3, W - 3 - arm, H - 3))
        p.drawLine(QLineF(W - 3, H - 3, W - 3, H - 3 - arm))


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # Cap scrollback so an hours-long session can't grow the document
        # without bound — keeps memory flat and every insert cheap. Oldest
        # lines drop off the top automatically.
        self.document().setMaximumBlockCount(600)
        self.setFont(mono_font(9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(3, 14, 26, 0.88);
                color: {C.TEXT};
                border: 1px solid rgba(0, 240, 255, 0.16);
                border-radius: 10px;
                padding: 10px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 240, 255, 0.28);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 240, 255, 0.65);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._ai_name_lc = "alfred"   # updated when assistant name changes
        self.show_thinking = False    # set by MainWindow's thinking toggle
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        # Filter cognitive-trace lines unless the toggle is active
        if not self.show_thinking and text.startswith("THINK:"):
            return
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        _ai_pfx = f"{self._ai_name_lc}:"
        if   tl.startswith("you:"):                              self._tag = "you"
        elif tl.startswith(_ai_pfx) or tl.startswith("alfred:") or tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("think:"):                            self._tag = "think"
        elif tl.startswith("file:"):                             self._tag = "file"
        elif "err" in tl:                                        self._tag = "err"
        else:                                                    self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            # Dynamic chunking: drain quickly when backlog exists or line is long,
            # reducing QTextEdit layout recalculations and paint events by 50-80%
            chunk_size = 8 if len(self._queue) > 1 else (4 if (len(self._text) - self._pos) > 60 else 2)
            chunk = self._text[self._pos : self._pos + chunk_size]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":   qcol(C.WHITE),
                "ai":    qcol(C.PRI),
                "think": qcol(C.MUTED),
                "err":   qcol(C.RED),
                "file":  qcol(C.GREEN),
                "sys":   qcol(C.TEXT_MED),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            if self._tag == "think":
                fmt.setFontItalic(True)
            else:
                fmt.setFontItalic(False)
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(chunk, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += len(chunk)
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

    def clear_log(self):
        """Cancel any in-flight typing animation, drain the queue, and clear the display."""
        self._tmr.stop()
        self._queue.clear()
        self._typing = False
        self._text = ""
        self._pos = 0
        self.clear()


class MinimizedHudOverlay(QWidget):
    """Small independent transcript window shown while the main HUD is minimized."""

    _POSITION_FILE = "hud_overlay_pos.json"

    def __init__(self, main_window, log_signal, assistant_name: str):
        super().__init__(None)
        self._main_window = main_window
        self._lines: deque[str] = deque(maxlen=10)
        self._assistant_name = ""
        self._ai_tags: tuple[str, ...] = ()
        self._drag_offset: QPoint | None = None
        self._user_closed = False
        self._shutting_down = False

        # This must be a real top-level Window, rather than Qt.Tool, so its
        # minimize control creates an independently restorable taskbar item.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(420, 230)
        from core.ui.themes import ThemeChrome
        self.setWindowTitle(f"ALFRED MK-IV // {ThemeChrome.chrome().window_title_suffix}")
        self.setObjectName("minimizedHudOverlay")
        self._build_ui()
        self.set_assistant_name(assistant_name)
        self._load_position()
        log_signal.connect(self._on_log)

    def _build_ui(self) -> None:
        shell = QFrame(self)
        shell.setObjectName("overlayShell")
        shell.setStyleSheet(f"""
            QFrame#overlayShell {{
                background: rgba(3, 14, 26, 238);
                border: 1px solid rgba(0, 240, 255, 112);
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; color: #b8c9ff; }}
            QTextEdit {{
                background: rgba(3, 14, 26, 210);
                color: #f2f7ff;
                border: none;
                padding: 4px 8px 8px 8px;
            }}
            QPushButton {{
                background: transparent;
                color: {C.TEXT_MED};
                border: none;
                min-width: 26px;
                max-width: 26px;
                min-height: 24px;
                max-height: 24px;
            }}
            QPushButton:hover {{ color: {C.WHITE}; background: rgba(0, 240, 255, 28); }}
            QPushButton#closeButton:hover {{ color: {C.RED}; background: rgba(255, 61, 87, 28); }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(10, 7, 8, 8)
        layout.setSpacing(4)

        self._header = QWidget(shell)
        self._header.setFixedHeight(28)
        header = QHBoxLayout(self._header)
        header.setContentsMargins(4, 0, 0, 0)
        header.setSpacing(2)

        header_font = self._readable_monospace_font(9)
        header_font.setWeight(QFont.Weight.Bold)
        self._title = QLabel()
        self._title.setFont(header_font)
        header.addWidget(self._title)
        header.addStretch()

        button_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        button_font.setPointSize(10)
        button_font.setWeight(QFont.Weight.Bold)

        self._sentry_btn = QPushButton("S")
        self._sentry_btn.setObjectName("sentryButton")
        self._sentry_btn.setToolTip("Sentry Mode (Monitor & Focus)")
        self._sentry_btn.clicked.connect(self._show_sentry_menu)

        minimize = QPushButton("−")
        minimize.setToolTip("Minimize overlay")
        minimize.clicked.connect(self.showMinimized)
        restore = QPushButton("↗")
        restore.setToolTip("Restore full ALFRED window")
        restore.clicked.connect(self._restore_main_window)
        close = QPushButton("×")
        close.setObjectName("closeButton")
        close.setToolTip("Hide overlay")
        close.clicked.connect(self.close)

        for button in (self._sentry_btn, minimize, restore, close):
            button.setFont(button_font)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            header.addWidget(button)
        layout.addWidget(self._header)

        self._transcript = QTextEdit(shell)
        self._transcript.setObjectName("overlayTranscript")
        self._transcript.setReadOnly(True)
        self._transcript.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        transcript_font = self._readable_monospace_font(10)
        transcript_font.setWeight(QFont.Weight.Medium)
        self._transcript.setFont(transcript_font)
        self._transcript.setAccessibleName("Recent Alfred replies")
        self._transcript.document().setMaximumBlockCount(20)
        from core.ui.themes import ThemeChrome
        self._transcript.setPlaceholderText(ThemeChrome.chrome().mini_hud_placeholder)
        layout.addWidget(self._transcript, stretch=1)

    @staticmethod
    def _readable_monospace_font(point_size: int) -> QFont:
        installed = set(QFontDatabase.families())
        preferred = (
            "Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono",
            "SF Mono", "DejaVu Sans Mono",
        )
        family = next((name for name in preferred if name in installed), None)
        font = (
            QFont(family)
            if family
            else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        font.setPointSize(point_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font

    def _show_sentry_menu(self) -> None:
        if self._main_window and hasattr(self._main_window, "_show_sentry_menu"):
            self._main_window._show_sentry_menu(anchor=self._sentry_btn)

    def update_sentry_indicator(
        self,
        mon_active: bool,
        foc_active: bool,
        waiting_for_answer: bool = False,
        foc_remaining_s: int = 0,
        drifting: bool = False,
    ) -> None:
        if not hasattr(self, "_sentry_btn"):
            return
        if foc_active:
            mins = max(0, foc_remaining_s) // 60
            secs = max(0, foc_remaining_s) % 60
            self._sentry_btn.setText(f"FOC {mins:02d}:{secs:02d}")
            if drifting:
                self._sentry_btn.setStyleSheet(f"QPushButton#sentryButton {{ color: {C.RED}; font-weight: bold; min-width: 80px; max-width: 90px; border: 1px solid {C.RED}; }}")
            else:
                self._sentry_btn.setStyleSheet(f"QPushButton#sentryButton {{ color: {C.CYAN}; font-weight: bold; min-width: 80px; max-width: 90px; border: 1px solid rgba(0, 240, 255, 80); }}")
            self._sentry_btn.setToolTip(f"FOCUS Mode: {mins:02d}:{secs:02d} remaining" + (" (DRIFTING)" if drifting else ""))
        elif mon_active:
            dot_color = "#ffcc00" if waiting_for_answer else "#00ff88"
            self._sentry_btn.setText("MON ●")
            self._sentry_btn.setStyleSheet(f"QPushButton#sentryButton {{ color: {dot_color}; font-weight: bold; min-width: 60px; max-width: 70px; }}")
            self._sentry_btn.setToolTip("Sentry Screen Monitoring Active" if not waiting_for_answer else "Sentry Monitor: Awaiting Target")
        else:
            self._sentry_btn.setText("S")
            self._sentry_btn.setStyleSheet(f"QPushButton#sentryButton {{ color: {C.TEXT_MED}; font-weight: bold; min-width: 26px; max-width: 26px; border: none; }}")

    def set_assistant_name(self, name: str) -> None:
        self._assistant_name = (name or "Alfred").strip()
        tags = (f"{self._assistant_name.lower()}:", "alfred:", "jarvis:")
        self._ai_tags = tuple(dict.fromkeys(tags))
        self.refresh_thematic_chrome()

    def refresh_thematic_chrome(self) -> None:
        from core.ui.themes import ThemeChrome
        chrome = ThemeChrome.chrome()
        disp = self._assistant_name.upper() if self._assistant_name else "ALFRED"
        self.setWindowTitle(f"{disp} // {chrome.window_title_suffix}")
        if hasattr(self, "_title") and self._title:
            self._title.setText(f"●  {disp} // {chrome.window_title_suffix}")
        if hasattr(self, "_transcript") and self._transcript:
            self._transcript.setPlaceholderText(chrome.mini_hud_placeholder)
        self.update()

    def _on_log(self, text: str) -> None:
        clean = str(text or "").strip()
        if not clean or not clean.lower().startswith(self._ai_tags):
            return
        self._lines.append(clean)
        self._transcript.setPlainText("\n".join(self._lines))
        bar = self._transcript.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _sync_sentry_state(self) -> None:
        """Immediately populate active Sentry monitor/focus status from the mode manager."""
        try:
            from core.sentry.mode_manager import get_sentry_mode_manager
            mgr = get_sentry_mode_manager()
            snap = mgr.get_snapshot()
            waiting = getattr(snap.monitor, "waiting_for_answer", False)
            if hasattr(mgr, "is_waiting_for_answer"):
                try:
                    waiting = bool(waiting or mgr.is_waiting_for_answer())
                except Exception:
                    pass
            self.update_sentry_indicator(
                mon_active=snap.monitor.active,
                foc_active=snap.focus.active,
                waiting_for_answer=waiting,
                foc_remaining_s=snap.focus.remaining_s,
                drifting=snap.focus.drifting,
            )
        except Exception:
            pass

    def begin_minimize_session(self) -> None:
        self._user_closed = False
        self.setWindowState(Qt.WindowState.WindowNoState)
        self._load_position()
        self._sync_sentry_state()
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self._save_position()
        self.hide()

    def _restore_main_window(self) -> None:
        self.hide_overlay()
        self._main_window.showNormal()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def shutdown(self) -> None:
        self._shutting_down = True
        self._save_position()
        self.close()

    def closeEvent(self, event) -> None:
        self._save_position()
        if self._shutting_down:
            event.accept()
            return
        self._user_closed = True
        self.hide()
        event.ignore()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 42:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    @property
    def _position_path(self) -> Path:
        return CONFIG_DIR / self._POSITION_FILE

    def _save_position(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._position_path.write_text(
                json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8"
            )
        except OSError:
            pass

    def _load_position(self) -> None:
        position: QPoint | None = None
        try:
            saved = json.loads(self._position_path.read_text(encoding="utf-8"))
            position = QPoint(int(saved["x"]), int(saved["y"]))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass

        screen = QApplication.screenAt(position) if position is not None else None
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            if position is not None:
                self.move(position)
            return
        bounds = screen.availableGeometry()
        if position is None:
            position = QPoint(bounds.right() - self.width() - 24, bounds.bottom() - self.height() - 24)
        x = max(bounds.left(), min(position.x(), bounds.right() - self.width() + 1))
        y = max(bounds.top(), min(position.y(), bounds.bottom() - self.height() + 1))
        self.move(x, y)


class NotesTerminalWidget(QWidget):
    """
    Dedicated terminal view exclusively for notes, links, code snippets,
    and structured intelligence provided by Alfred.
    Keeps URLs and research distinct from the conversational chat stream.
    Features clickable links, copy-all, clear, and persistence.
    """
    note_added = pyqtSignal(int)  # emits updated count

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes_file = CONFIG_DIR / "intel_notes.json"
        self._notes: list[dict] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Top control bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(4, 2, 4, 2)
        top_bar.setSpacing(6)

        self._count_lbl = QLabel("0 ENTRIES")
        self._count_lbl.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.8))
        self._count_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        top_bar.addWidget(self._count_lbl)
        top_bar.addStretch()

        _BTN_SM = f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.04);
                color: {C.TEXT_MED};
                border: 1px solid rgba(0, 240, 255, 0.15);
                border-radius: 5px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background: rgba(0, 240, 255, 0.15);
                color: #ffffff;
                border-color: {C.PRI};
            }}
            QPushButton:pressed {{
                background: rgba(0, 240, 255, 0.25);
            }}
        """

        self._copy_btn = QPushButton("📋 COPY")
        self._copy_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._copy_btn.setFixedHeight(22)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setStyleSheet(_BTN_SM)
        attach_hover_help(self._copy_btn, "Copy all notes and links in the Intel vault to your clipboard.")
        self._copy_btn.clicked.connect(self.copy_all)
        top_bar.addWidget(self._copy_btn)

        self._clear_btn = QPushButton("🗑 CLEAR")
        self._clear_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._clear_btn.setFixedHeight(22)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(_BTN_SM)
        attach_hover_help(self._clear_btn, "Clear all saved notes and research links from the Intel vault.")
        self._clear_btn.clicked.connect(self.clear_notes)
        top_bar.addWidget(self._clear_btn)

        lay.addLayout(top_bar)

        # Main browser
        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setOpenExternalLinks(True)
        self._browser.document().setMaximumBlockCount(800)
        self._browser.setFont(mono_font(9))
        self._browser.setStyleSheet(f"""
            QTextBrowser {{
                background: rgba(3, 14, 26, 0.88);
                color: {C.TEXT};
                border: 1px solid rgba(0, 240, 255, 0.16);
                border-radius: 10px;
                padding: 8px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 240, 255, 0.28);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 240, 255, 0.65);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._browser, stretch=1)

        self._load_stored_notes()

    def count(self) -> int:
        return len(self._notes)

    def _load_stored_notes(self):
        if not self._notes_file.exists():
            self._render_empty()
            return
        try:
            items = json.loads(self._notes_file.read_text(encoding="utf-8"))
            if isinstance(items, list):
                self._notes = items
                self._render_all()
            else:
                self._render_empty()
        except Exception:
            self._render_empty()

    def _render_empty(self):
        self._count_lbl.setText("0 ENTRIES")
        self._browser.setHtml(f"""
            <div style="font-family: sans-serif; color: rgba(0, 240, 255, 0.45); text-align: center; margin-top: 40px;">
                <div style="font-size: 22px; margin-bottom: 8px;">📝</div>
                <div style="font-size: 11px; font-weight: bold; letter-spacing: 1px;">INTEL & NOTES VAULT READY</div>
                <div style="font-size: 10px; color: rgba(255,255,255,0.4); margin-top: 6px; line-height: 1.4;">
                    Special notes, research links, URLs, and code snippets provided by Alfred will appear here directly.
                </div>
            </div>
        """)

    def _render_all(self):
        if not self._notes:
            self._render_empty()
            return
        self._count_lbl.setText(f"{len(self._notes)} ENTRIES")
        html = self._build_notes_html(self._notes)
        self._browser.setHtml(html)
        cur = self._browser.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self._browser.setTextCursor(cur)

    def _build_notes_html(self, notes: list[dict]) -> str:
        blocks = []
        for n in notes:
            blocks.append(self._format_card(n))
        return f"""
        <html>
        <head>
        <style>
            body {{ font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace; background: transparent; margin: 0; padding: 2px; }}
            a {{ color: #00f0ff; text-decoration: underline; }}
            a:hover {{ color: #ffffff; text-decoration: none; }}
            pre {{ background: rgba(0, 0, 0, 0.45); border: 1px solid rgba(0, 240, 255, 0.15); border-radius: 6px; padding: 8px; color: #a5f3fc; font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size: 11px; white-space: pre-wrap; }}
        </style>
        </head>
        <body>
            {''.join(blocks)}
        </body>
        </html>
        """

    def _format_card(self, item: dict) -> str:
        import html as _html
        import re as _re
        ntype = str(item.get("type", "note")).lower()
        title = item.get("title", "Untitled")
        content = item.get("content", "")
        t_str = item.get("time", "")

        type_cfg = {
            "link": ("🔗 LINK", "#00f0ff", "rgba(0, 240, 255, 0.15)"),
            "data": ("📊 DATA", "#00ff9d", "rgba(0, 255, 157, 0.15)"),
            "code": ("💻 CODE", "#c084fc", "rgba(192, 132, 252, 0.15)"),
            "note": ("📌 NOTE", "#ffb800", "rgba(255, 184, 0, 0.15)"),
        }
        badge, b_col, border_col = type_cfg.get(ntype, ("📌 NOTE", "#ffb800", "rgba(255, 184, 0, 0.15)"))

        esc_content = _html.escape(content)
        url_re = _re.compile(r"(https?://[^\s<>\"']+)")
        def _repl_url(match):
            u = match.group(1)
            return f'<a href="{u}" style="color: #00f0ff; font-weight: bold; text-decoration: underline;">{u}</a>'
        formatted_content = url_re.sub(_repl_url, esc_content)

        if ntype == "code" or "```" in content:
            body_html = f"<pre>{formatted_content}</pre>"
        else:
            body_html = formatted_content.replace("\n", "<br>")

        return f"""
        <div style="background: rgba(4, 18, 32, 0.85); border-left: 3px solid {b_col}; border-top: 1px solid rgba(255,255,255,0.06); border-right: 1px solid rgba(255,255,255,0.06); border-bottom: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 10px; margin-bottom: 10px;">
            <div style="display: flex; margin-bottom: 6px;">
                <span style="background: {border_col}; color: {b_col}; font-size: 9px; font-weight: bold; padding: 2px 6px; border-radius: 4px; margin-right: 8px;">{badge}</span>
                <span style="color: rgba(255, 255, 255, 0.40); font-size: 9px;">{t_str}</span>
            </div>
            <div style="color: #ffffff; font-weight: bold; font-size: 11px; margin-bottom: 6px;">{_html.escape(title)}</div>
            <div style="color: rgba(255, 255, 255, 0.85); font-size: 10px; line-height: 1.45;">{body_html}</div>
        </div>
        """

    def add_note(self, title: str, content: str, note_type: str = "note"):
        timestamp = time.strftime("%H:%M:%S")
        date_str = time.strftime("%Y-%m-%d")
        entry = {
            "title": title or "Intel Entry",
            "content": content,
            "type": note_type or "note",
            "time": timestamp,
            "date": date_str,
        }
        self._notes.append(entry)
        if len(self._notes) > 200:
            self._notes = self._notes[-200:]
        
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._notes_file.write_text(json.dumps(self._notes, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[NotesWidget] Persist failed: {e}")

        self._render_all()
        self.note_added.emit(len(self._notes))

    def clear_notes(self):
        self._notes = []
        try:
            if self._notes_file.exists():
                self._notes_file.unlink()
        except Exception:
            pass
        self._render_empty()
        self.note_added.emit(0)

    def copy_all(self):
        if not self._notes:
            return
        lines = []
        for n in self._notes:
            lines.append(f"[{n.get('type', 'note').upper()}] {n.get('title', 'Untitled')} ({n.get('time', '')})")
            lines.append(f"{n.get('content', '')}\n{'-'*40}")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        old_txt = self._copy_btn.text()
        self._copy_btn.setText("✓ COPIED")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText(old_txt))


_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        # The marching-ants dashed border is only meaningful while the user is
        # hovering or dragging a file over the zone. When idle, skip the repaint
        # entirely instead of redrawing the whole zone 25×/s forever — that idle
        # repaint held the GIL and stole time from the audio/response threads.
        if not (self._hovering or self._drag_over):
            return
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for ALFRED", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol(C.PANEL2, 220) if z._drag_over else (qcol(C.PANEL, 200) if z._hovering else qcol(C.BG, 200))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 2, 2)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER_A, 160)

        pen = QPen(border_col, 1.2, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 2, 2)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

        p.end()

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI if hover else C.PRI_DIM)
        p.setPen(QPen(col, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # High-tech cyber ingest arrow
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 3))
        p.drawLine(QPointF(cx - 7, cy - 7), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 7, cy - 7), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 12, cy + 3), QPointF(cx + 12, cy + 3))

        # Precision corner brackets
        bracket_len = 10
        p.setPen(QPen(qcol(C.PRI if hover else C.BORDER_B, 180), 1.2))
        # Top-left
        p.drawLine(QPointF(12, 12), QPointF(12 + bracket_len, 12))
        p.drawLine(QPointF(12, 12), QPointF(12, 12 + bracket_len))
        # Top-right
        p.drawLine(QPointF(W - 12, 12), QPointF(W - 12 - bracket_len, 12))
        p.drawLine(QPointF(W - 12, 12), QPointF(W - 12, 12 + bracket_len))
        # Bottom-left
        p.drawLine(QPointF(12, H - 12), QPointF(12 + bracket_len, H - 12))
        p.drawLine(QPointF(12, H - 12), QPointF(12, H - 12 - bracket_len))
        # Bottom-right
        p.drawLine(QPointF(W - 12, H - 12), QPointF(W - 12 - bracket_len, H - 12))
        p.drawLine(QPointF(W - 12, H - 12), QPointF(W - 12, H - 12 - bracket_len))

        p.setFont(tech_font(8, QFont.Weight.DemiBold, letter_spacing=0.8))
        p.setPen(QPen(qcol(C.TEXT if hover else C.TEXT_MED), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "INGEST DIRECTIVE  //  DROP FILE OR BROWSE")
        p.setFont(tech_font(7, letter_spacing=0.5))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "IMAGES · CODE · DOCUMENTS · MEDIA · TELEMETRY")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(tech_font(18, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⇲")
        p.setFont(tech_font(9, QFont.Weight.Bold, letter_spacing=1.0))
        p.setPen(QPen(qcol(C.WHITE), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "RELEASE TO INGEST DATA")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(tech_font(9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(mono_font(8))
        p.setPen(QPen(qcol(C.TEXT_MED), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(mono_font(7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(tech_font(9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class _CameraPreview(QWidget):
    """Floating overlay that briefly shows what the camera captured."""

    _W, _H = 244, 188

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _CameraPreview {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("◈  OPTICAL SENSOR FEED")
        title.setFont(tech_font(8, QFont.Weight.Bold, 60))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setFont(mono_font(8, QFont.Weight.Bold))
        close_btn.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: transparent; border: none;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            max_w = self._W - 12
            scaled = px.scaled(
                max_w, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setFixedSize(scaled.width(), scaled.height())
            self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(6_000)   # auto-dismiss after 6 s


class SetupOverlay(QWidget):
    done = pyqtSignal(object)  # emits config dict
    _probe_done = pyqtSignal(str, bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._probe_done.connect(self._on_probe_done)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        cur_cfg = _read_full_config()
        self._provider = cur_cfg.get("llm_provider", "gemini").lower()
        if self._provider not in ("gemini", "ollama", "openai", "openrouter"):
            self._provider = "gemini"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(7)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(tech_font(font_size,
                                QFont.Weight.Bold if bold else QFont.Weight.Medium,
                                50 if bold else 20))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        # Common input field styling
        _inp_style = f"""
            QLineEdit {{
                background: {C.PANEL2}; color: {C.TEXT_BRIGHT};
                border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """

        # Header with Title and Close Button
        hdr_row = QHBoxLayout()
        hdr_box = QVBoxLayout(); hdr_box.setSpacing(2)
        hdr_box.addWidget(_lbl("◈  SYSTEM INITIALISATION // OPERATOR & NEURAL CONFIG", 11, True, align=Qt.AlignmentFlag.AlignLeft))
        hdr_box.addWidget(_lbl("Configure operator designation, neural interface backend, and credentials.", 8, color=C.PRI_DIM, align=Qt.AlignmentFlag.AlignLeft))
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(tech_font(9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: {C.RED};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;"); layout.addWidget(sep)
        layout.addSpacing(2)

        # ── Operator Designation & Identity ─────────────────────────────
        ident_row = QHBoxLayout(); ident_row.setSpacing(8)
        user_box = QVBoxLayout(); user_box.setSpacing(2)
        user_box.addWidget(_lbl("OPERATOR CALLSIGN / USER DESIGNATION", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(cur_cfg.get("user_name", ""))
        self._user_input.setPlaceholderText("e.g. Master Wayne, Sir, or your name")
        self._user_input.setFont(mono_font(8))
        self._user_input.setFixedHeight(26)
        self._user_input.setStyleSheet(_inp_style)
        user_box.addWidget(self._user_input)
        ident_row.addLayout(user_box, stretch=3)

        asst_box = QVBoxLayout(); asst_box.setSpacing(2)
        asst_box.addWidget(_lbl("ASSISTANT CALLSIGN", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._asst_input = QLineEdit(cur_cfg.get("assistant_name", "Alfred") or "Alfred")
        self._asst_input.setFont(mono_font(8))
        self._asst_input.setFixedHeight(26)
        self._asst_input.setStyleSheet(_inp_style)
        asst_box.addWidget(self._asst_input)
        ident_row.addLayout(asst_box, stretch=2)
        layout.addLayout(ident_row)
        layout.addSpacing(2)

        # ── Backend Mode Selector ───────────────────────────────────────
        layout.addWidget(_lbl("INTELLIGENCE BACKEND // MULTI-ROUTE ARCHITECTURE", 8, bold=True, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        mode_row = QHBoxLayout(); mode_row.setSpacing(6)
        self._mode_btns: dict[str, QPushButton] = {}
        for m_key, m_label in [
            ("gemini", "◈  GEMINI LIVE"),
            ("ollama", "🦙  LOCAL OLLAMA"),
            ("openai", "⚡  LM STUDIO"),
            ("openrouter", "🌐  OPENROUTER API"),
        ]:
            b = QPushButton(m_label)
            b.setFont(tech_font(8, QFont.Weight.Bold, 30))
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, k=m_key: self._set_backend(k))
            self._mode_btns[m_key] = b
            mode_row.addWidget(b)
        layout.addLayout(mode_row)
        layout.addSpacing(2)

        # ── Provider Stack ──────────────────────────────────────────────
        self._provider_stack = QStackedWidget()

        # 1. Gemini Stack Page
        gemini_w = QWidget(); gemini_lay = QVBoxLayout(gemini_w)
        gemini_lay.setContentsMargins(0, 0, 0, 0); gemini_lay.setSpacing(4)
        gemini_lay.addWidget(_lbl("GEMINI API DIRECTIVE KEY", 8, bold=True, color=C.TEXT_DIM,
                                  align=Qt.AlignmentFlag.AlignLeft))
        existing_key = (cur_cfg.get("gemini_api_key") or cur_cfg.get("GEMINI_API_KEY")
                        or cur_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY", ""))
        self._key_input = QLineEdit(existing_key)
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIzaSy... (key from Google AI Studio)")
        self._key_input.setFont(mono_font(9))
        self._key_input.setFixedHeight(30)
        self._key_input.setStyleSheet(_inp_style)
        gemini_lay.addWidget(self._key_input)
        gemini_hint = QLabel("⚡ Cloud Multimodal WebSocket — Zero local compute/Ollama required. Recommended for macOS & all platforms.")
        gemini_hint.setFont(tech_font(7))
        gemini_hint.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        gemini_lay.addWidget(gemini_hint)
        gemini_lay.addStretch()
        self._provider_stack.addWidget(gemini_w)

        # 2. Ollama Stack Page
        ollama_w = QWidget(); ollama_lay = QVBoxLayout(ollama_w)
        ollama_lay.setContentsMargins(0, 0, 0, 0); ollama_lay.setSpacing(4)
        
        ollama_url_row = QHBoxLayout(); ollama_url_row.setSpacing(6)
        ollama_url_box = QVBoxLayout(); ollama_url_box.setSpacing(2)
        ollama_url_box.addWidget(_lbl("OLLAMA HOST URL", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._ollama_url = QLineEdit(cur_cfg.get("llm_url", "http://localhost:11434"))
        self._ollama_url.setFont(mono_font(9))
        self._ollama_url.setFixedHeight(28)
        self._ollama_url.setStyleSheet(_inp_style)
        ollama_url_box.addWidget(self._ollama_url)
        ollama_url_row.addLayout(ollama_url_box, stretch=2)

        ollama_model_box = QVBoxLayout(); ollama_model_box.setSpacing(2)
        ollama_model_box.addWidget(_lbl("MODEL TAG", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._ollama_model = QLineEdit(cur_cfg.get("llm_model", "llama3.2"))
        self._ollama_model.setFont(mono_font(9))
        self._ollama_model.setFixedHeight(28)
        self._ollama_model.setStyleSheet(_inp_style)
        ollama_model_box.addWidget(self._ollama_model)
        ollama_url_row.addLayout(ollama_model_box, stretch=2)
        ollama_lay.addLayout(ollama_url_row)

        chip_row = QHBoxLayout(); chip_row.setSpacing(4)
        for chip_name in ["llama3.2", "qwen2.5:7b", "deepseek-coder-v2"]:
            cb = QPushButton(chip_name)
            cb.setFixedHeight(20)
            cb.setFont(mono_font(7, letter_spacing=0.2))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 0 6px;
                }}
                QPushButton:hover {{ border-color: {C.PRI}; color: #ffffff; background: rgba(142, 155, 255, 0.10); }}
            """)
            cb.clicked.connect(lambda _, m=chip_name: self._ollama_model.setText(m))
            chip_row.addWidget(cb)
        chip_row.addStretch()
        ollama_lay.addLayout(chip_row)

        probe_row = QHBoxLayout(); probe_row.setSpacing(8)
        self._probe_btn = QPushButton("◈  PROBE STATUS")
        self._probe_btn.setFixedHeight(24)
        self._probe_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._probe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._probe_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 2px; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        self._probe_btn.clicked.connect(self._probe_ollama)
        probe_row.addWidget(self._probe_btn)

        self._probe_status = QLabel("100% offline, zero network egress")
        self._probe_status.setFont(tech_font(7))
        self._probe_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        probe_row.addWidget(self._probe_status, stretch=1)
        ollama_lay.addLayout(probe_row)
        ollama_lay.addStretch()
        self._provider_stack.addWidget(ollama_w)

        # 3. LM Studio Stack Page
        lm_w = QWidget(); lm_lay = QVBoxLayout(lm_w)
        lm_lay.setContentsMargins(0, 0, 0, 0); lm_lay.setSpacing(4)
        lm_url_row = QHBoxLayout(); lm_url_row.setSpacing(6)
        lm_url_box = QVBoxLayout(); lm_url_box.setSpacing(2)
        lm_url_box.addWidget(_lbl("SERVER ENDPOINT", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._lm_url = QLineEdit(cur_cfg.get("llm_url", "http://localhost:1234/v1"))
        self._lm_url.setFont(mono_font(9))
        self._lm_url.setFixedHeight(28)
        self._lm_url.setStyleSheet(_inp_style)
        lm_url_box.addWidget(self._lm_url)
        lm_url_row.addLayout(lm_url_box, stretch=2)

        lm_model_box = QVBoxLayout(); lm_model_box.setSpacing(2)
        lm_model_box.addWidget(_lbl("MODEL IDENTIFIER", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._lm_model = QLineEdit(cur_cfg.get("llm_model", "local-model"))
        self._lm_model.setFont(mono_font(9))
        self._lm_model.setFixedHeight(28)
        self._lm_model.setStyleSheet(_inp_style)
        lm_model_box.addWidget(self._lm_model)
        lm_url_row.addLayout(lm_model_box, stretch=2)
        lm_lay.addLayout(lm_url_row)
        lm_hint = QLabel("Compatible with LM Studio, Jan, LocalAI, vLLM, and llama.cpp server.")
        lm_hint.setFont(tech_font(7))
        lm_hint.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        lm_lay.addWidget(lm_hint)
        lm_lay.addStretch()
        self._provider_stack.addWidget(lm_w)

        # 4. OpenRouter Stack Page
        or_w = QWidget(); or_lay = QVBoxLayout(or_w)
        or_lay.setContentsMargins(0, 0, 0, 0); or_lay.setSpacing(4)

        or_key_box = QVBoxLayout(); or_key_box.setSpacing(2)
        or_key_box.addWidget(_lbl("OPENROUTER DIRECTIVE API KEY", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        existing_or_key = (cur_cfg.get("openrouter_api_key") or cur_cfg.get("OPENROUTER_API_KEY")
                           or os.environ.get("OPENROUTER_API_KEY", ""))
        self._or_key_input = QLineEdit(existing_or_key)
        self._or_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_key_input.setPlaceholderText("sk-or-v1-... (from openrouter.ai/keys)")
        self._or_key_input.setFont(mono_font(9))
        self._or_key_input.setFixedHeight(28)
        self._or_key_input.setStyleSheet(_inp_style)
        or_key_box.addWidget(self._or_key_input)
        or_lay.addLayout(or_key_box)

        or_model_box = QVBoxLayout(); or_model_box.setSpacing(2)
        or_model_box.addWidget(_lbl("TARGET NEURAL MODEL IDENTIFIER", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        default_or_model = cur_cfg.get("openrouter_model") or cur_cfg.get("llm_model") or "anthropic/claude-3.5-sonnet"
        self._or_model = QLineEdit(default_or_model)
        self._or_model.setFont(mono_font(9))
        self._or_model.setFixedHeight(28)
        self._or_model.setStyleSheet(_inp_style)
        or_model_box.addWidget(self._or_model)
        or_lay.addLayout(or_model_box)

        # Quick-pick model chips
        or_chip_row = QHBoxLayout(); or_chip_row.setSpacing(4)
        for chip_label, model_id in [
            ("claude-3.5-sonnet", "anthropic/claude-3.5-sonnet"),
            ("gemini-2.0-flash", "google/gemini-2.0-flash-001"),
            ("llama-3.3-70b", "meta-llama/llama-3.3-70b-instruct"),
            ("deepseek-r1", "deepseek/deepseek-r1"),
            ("gpt-4o", "openai/gpt-4o"),
            ("auto", "openrouter/auto"),
        ]:
            cb = QPushButton(chip_label)
            cb.setFixedHeight(20)
            cb.setFont(mono_font(7, letter_spacing=0.2))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 0 5px;
                }}
                QPushButton:hover {{ border-color: {C.PRI}; color: #ffffff; background: rgba(142, 155, 255, 0.10); }}
            """)
            cb.clicked.connect(lambda _, m=model_id: self._or_model.setText(m))
            or_chip_row.addWidget(cb)
        or_chip_row.addStretch()
        or_lay.addLayout(or_chip_row)

        or_probe_row = QHBoxLayout(); or_probe_row.setSpacing(8)
        self._or_probe_btn = QPushButton("◈  PROBE ROUTE")
        self._or_probe_btn.setFixedHeight(24)
        self._or_probe_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._or_probe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._or_probe_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 2px; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        self._or_probe_btn.clicked.connect(self._probe_openrouter)
        or_probe_row.addWidget(self._or_probe_btn)

        self._or_probe_status = QLabel("Unified gateway to 200+ frontier models")
        self._or_probe_status.setFont(tech_font(7))
        self._or_probe_status.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        or_probe_row.addWidget(self._or_probe_status, stretch=1)
        or_lay.addLayout(or_probe_row)
        or_lay.addStretch()
        self._provider_stack.addWidget(or_w)

        layout.addWidget(self._provider_stack)
        layout.addSpacing(2)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;"); layout.addWidget(sep2)
        layout.addSpacing(2)

        layout.addWidget(_lbl("TARGET OPERATING SYSTEM", 8, bold=True, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected Environment: {det_name}", 7, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","◈  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(tech_font(8, QFont.Weight.Bold, 30))
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel_os_btn(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel_os_btn(detected)
        self._set_backend(self._provider)
        layout.addSpacing(4)

        # Validation error banner
        self._err_lbl = QLabel("")
        self._err_lbl.setFont(tech_font(7, QFont.Weight.Bold))
        self._err_lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")
        self._err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err_lbl.hide()
        layout.addWidget(self._err_lbl)

        # Bottom action bar (Initialise Systems + Discard)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.2))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        btn_row.addWidget(init_btn, stretch=2)

        cancel_btn = QPushButton("DISCARD")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFont(mono_font(8, letter_spacing=0.8))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {C.PRI};
                background: rgba(142, 155, 255, 0.10);
            }}
            QPushButton:pressed {{
                background: rgba(142, 155, 255, 0.20);
            }}
        """)
        cancel_btn.clicked.connect(self.hide)
        btn_row.addWidget(cancel_btn, stretch=1)

        layout.addLayout(btn_row)

    def _set_backend(self, key: str):
        self._provider = key
        idx_map = {"gemini": 0, "ollama": 1, "openai": 2, "openrouter": 3}
        self._provider_stack.setCurrentIndex(idx_map.get(key, 0))
        for k, btn in self._mode_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT_BRIGHT}; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    def _sel_os_btn(self, key: str):
        self._sel_os = key
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT_BRIGHT}; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    def _probe_ollama(self):
        self._probe_status.setText("Probing Ollama...")
        self._probe_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        url = self._ollama_url.text().strip() or "http://localhost:11434"

        def _check():
            import urllib.request
            try:
                req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", headers={"User-Agent": "ALFRED"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        models = [m.get("name", "") for m in data.get("models", [])]
                        return True, models
            except Exception:
                pass
            return False, []

        def _worker():
            ok, models = _check()
            self._probe_done.emit("ollama", ok, models)

        threading.Thread(target=_worker, daemon=True).start()

    def _probe_openrouter(self):
        key = self._or_key_input.text().strip()
        if not key:
            self._or_probe_status.setText("▲ ENTER API KEY FIRST")
            self._or_probe_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            return
        self._or_probe_status.setText("Probing OpenRouter gateway...")
        self._or_probe_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")

        def _check():
            import urllib.request
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "ALFRED-Mark-IV",
                    }
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8")).get("data", {})
                        usage = data.get("usage")
                        if usage is not None:
                            return True, f"● ONLINE // Key Valid (Usage: ${usage:.2f})"
                        return True, "● ONLINE // Gateway Verified"
            except Exception as e:
                err_msg = str(e)
                if "401" in err_msg or "403" in err_msg:
                    return False, "▲ INVALID API KEY (401 Unauthorized)"
                return False, f"▲ CONNECTION FAILED ({type(e).__name__})"
            return False, "▲ PROBE FAILED"

        def _worker():
            ok, message = _check()
            self._probe_done.emit("openrouter", ok, message)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_probe_done(self, backend: str, ok: bool, payload) -> None:
        """Update probe widgets on the Qt thread via a queued signal."""
        if backend == "ollama":
            models = list(payload or [])
            if ok:
                found = ", ".join(models[:3]) if models else "server reachable"
                self._probe_status.setText(f"● ONLINE // Models: {found}")
                self._probe_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
            else:
                hint = "Run 'ollama serve' in terminal"
                if self._sel_os == "mac":
                    hint = "Run 'brew install ollama && ollama serve' (CLI works on macOS 11+)"
                self._probe_status.setText(f"▲ OFFLINE — {hint}")
                self._probe_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            return

        self._or_probe_status.setText(str(payload))
        self._or_probe_status.setStyleSheet(
            f"color: {C.GREEN if ok else C.RED}; background: transparent;"
        )

    def _submit(self):
        self._err_lbl.hide()
        prov = self._provider
        os_name = self._sel_os
        u_name = self._user_input.text().strip()
        a_name = self._asst_input.text().strip() or "Alfred"

        if prov == "gemini":
            key = self._key_input.text().strip()
            if not key:
                self._key_input.setStyleSheet(
                    self._key_input.styleSheet() +
                    f" QLineEdit {{ border: 1px solid {C.RED}; }}"
                )
                self._err_lbl.setText("GEMINI KEY REQUIRED FOR CLOUD. OR SELECT OPENROUTER / LOCAL.")
                self._err_lbl.show()
                return
            config_dict = {
                "llm_provider": "gemini",
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        elif prov == "ollama":
            url = self._ollama_url.text().strip() or "http://localhost:11434"
            model = self._ollama_model.text().strip() or "llama3.2"
            key = self._key_input.text().strip()
            config_dict = {
                "llm_provider": "ollama",
                "llm_url": url,
                "llm_model": model,
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        elif prov == "openrouter":
            or_key = self._or_key_input.text().strip()
            or_model = self._or_model.text().strip() or "anthropic/claude-3.5-sonnet"
            if not or_key:
                self._or_key_input.setStyleSheet(
                    self._or_key_input.styleSheet() +
                    f" QLineEdit {{ border: 1px solid {C.RED}; }}"
                )
                self._err_lbl.setText("OPENROUTER API KEY REQUIRED FOR ROUTING.")
                self._err_lbl.show()
                return
            config_dict = {
                "llm_provider": "openrouter",
                "openrouter_api_key": or_key,
                "openrouter_model": or_model,
                "llm_model": or_model,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        else:  # openai / lmstudio
            url = self._lm_url.text().strip() or "http://localhost:1234/v1"
            model = self._lm_model.text().strip() or "local-model"
            key = self._key_input.text().strip()
            config_dict = {
                "llm_provider": "openai",
                "llm_url": url,
                "llm_model": model,
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }

        self.done.emit(config_dict)


class ImagePopupOverlay(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            ImagePopupOverlay {
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Image label
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale image to fit reasonably, max width/height 400px while keeping aspect ratio
            scaled = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText(f"[Image not found: {image_path}]")
            self._image_label.setStyleSheet(f"color: {C.TEXT_MED};")
        layout.addWidget(self._image_label)

        # Dismiss button
        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setFont(tech_font(9, QFont.Weight.Bold))
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setFixedHeight(28)
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
        """)
        dismiss_btn.clicked.connect(self.hide)
        dismiss_btn.clicked.connect(self.dismissed.emit)
        layout.addWidget(dismiss_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_centered(self, parent: QWidget):
        """Show the popup centered over the parent widget."""
        if parent:
            self.move(
                parent.x() + (parent.width() - self.width()) // 2,
                parent.y() + (parent.height() - self.height()) // 2,
            )
        self.show()
        self.raise_()
        self.activateWindow


class HueWheel(QWidget):
    """
    Circular colour picker. The user drags the handle (small white circle)
    around the wheel to choose from ALL hues. The filled circle in the centre
    is a live preview of the selected colour.
    """

    hue_picked    = pyqtSignal(str)   # while dragging (live)
    hue_committed = pyqtSignal(str)   # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        # draggable handle
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── mouse events ─────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(QWidget):
    """
    Floating glassmorphic overlay for configuring Assistant Persona,
    Commander Designation, Vocal Profile, and Chromatic Matrix.
    Built with a responsive, scrollable core so controls never clip on any display.
    """
    saved = pyqtSignal(str, str, str, str)   # assistant_name, user_name, ui_color, voice
    setup_api_requested = pyqtSignal()
    _OW, _OH = 560, 680

    def __init__(self, assistant_name="Alfred", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", current_icon="", voice_engine=None, parent=None):
        super().__init__(parent)
        self._current_icon = (current_icon or "").strip()
        self._initial_icon = self._current_icon
        self.on_icon_change = None
        self.on_preview_voice = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(4, 12, 22, 0.96);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 16px;
            }}
        """)
        outer_lay = QVBoxLayout(self)
        outer_lay.setContentsMargins(20, 18, 20, 18)
        outer_lay.setSpacing(10)

        # Header with Title and Close Button
        hdr_row = QHBoxLayout()
        hdr_box = QVBoxLayout(); hdr_box.setSpacing(2)
        title = QLabel("⚙  RECONFIGURE BATCOMPUTER MATRIX")
        title.setFont(tech_font(11, QFont.Weight.Bold, letter_spacing=1.8))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr_box.addWidget(title)

        sub = QLabel("PERSONA PROFILES // NEURAL VOCAL SYNTHESIS // CHROMATICS")
        sub.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=1.0))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr_box.addWidget(sub)
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(tech_font(10, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.TEXT_MED};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: #ff2a55;
            }}
        """)
        close_btn.clicked.connect(self._cancel)
        attach_hover_help(close_btn, "Discard changes and close the reconfiguration window.")
        hdr_row.addWidget(close_btn)
        outer_lay.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(0, 240, 255, 0.16); margin: 2px 0;")
        outer_lay.addWidget(sep)

        # Scrollable container for all settings so it never overflows or clips
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(0, 0, 0, 0.2);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 240, 255, 0.35);
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 240, 255, 0.65);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        body_widget = QWidget()
        body_widget.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(body_widget)
        lay.setContentsMargins(4, 4, 10, 4)
        lay.setSpacing(10)

        def _lbl(txt, fs=8, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignLeft):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(tech_font(fs,
                                QFont.Weight.Bold if bold else QFont.Weight.Medium,
                                letter_spacing=0.8 if bold else 0.3))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: {C.PANEL2}; color: {C.WHITE}; "
               f"border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 6px 12px; font-size: 13px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.08); }}")

        # ── Codename & Designation ───────────────────────────────────────
        lbl_codename = _lbl("ASSISTANT CODENAME", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_codename)
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(mono_font(10, QFont.Weight.DemiBold, letter_spacing=0.5))
        self._name_input.setFixedHeight(34)
        self._name_input.setStyleSheet(_fs)
        attach_hover_help(self._name_input, "The codename ALFRED uses when speaking and displaying system status headers.", lbl_codename)
        lay.addWidget(self._name_input)

        lbl_designation = _lbl("COMMANDER DESIGNATION  (e.g. Master Wayne, Sir)", 8,
                               bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_designation)
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g.  Master Wayne   (leave blank for default)")
        self._user_input.setFont(mono_font(10, letter_spacing=0.3))
        self._user_input.setFixedHeight(34)
        self._user_input.setStyleSheet(_fs)
        attach_hover_help(self._user_input, "How the assistant addresses you during conversations and briefings (e.g. Master Wayne, Sir).", lbl_designation)
        lay.addWidget(self._user_input)

        # ── Tactical Bat-Insignia & Application Icon ─────────────────────
        lbl_insignia = _lbl("TACTICAL BAT-INSIGNIA & APPLICATION ICON", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_insignia)
        icon_sub = QLabel("SELECT CHASSIS BADGE // SYSTEM TRAY & TASKBAR ICON // REALTIME UPLINK")
        icon_sub.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=0.8))
        icon_sub.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; margin-bottom: 2px;")
        lay.addWidget(icon_sub)

        self._icon_cards: dict[str, QPushButton] = {}
        icon_grid = QGridLayout()
        icon_grid.setSpacing(8)
        icon_grid.setContentsMargins(0, 0, 0, 4)

        avail_icons = get_available_app_icons()
        if not self._current_icon and avail_icons:
            self._current_icon = avail_icons[0]["path"]

        cols = 3
        for idx, ic in enumerate(avail_icons):
            row = idx // cols
            col = idx % cols

            btn = QPushButton()
            btn.setFixedHeight(58)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(8, 6, 8, 6)
            btn_lay.setSpacing(8)

            ico_lbl = QLabel()
            ico_lbl.setFixedSize(36, 36)
            ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico_lbl.setStyleSheet("background: transparent;")
            pm = _scaled_icon_pixmap(ic["path"], 32, 32)
            if not pm.isNull():
                ico_lbl.setPixmap(pm)
            btn_lay.addWidget(ico_lbl)

            txt_box = QVBoxLayout()
            txt_box.setSpacing(2)
            txt_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            name_lbl = QLabel(ic["name"])
            name_lbl.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
            txt_box.addWidget(name_lbl)

            file_lbl = QLabel(ic["filename"][:22])
            file_lbl.setFont(tech_font(6, letter_spacing=0.2))
            file_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
            txt_box.addWidget(file_lbl)

            btn_lay.addLayout(txt_box)
            btn_lay.addStretch()

            btn.clicked.connect(lambda _=False, p=ic["path"]: self._on_icon_picked(p))
            attach_hover_help(btn, f"Select '{ic['name']}' chassis insignia for HUD, taskbar, and tray badge.")
            self._icon_cards[ic["path"]] = btn
            icon_grid.addWidget(btn, row, col)

        lay.addLayout(icon_grid)
        self._refresh_icon_cards()

        # ── Assistant voice — Gemini prebuilt voices ─────────────────────
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lbl_voice = _lbl("VOCAL SYNTHESIS PROFILE", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_voice)
        self._sel_voice = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns: dict[str, QPushButton] = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(6)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(29)
            b.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            attach_hover_help(b, f"Use the neural vocal profile '{_v}' for spoken responses.", lbl_voice)
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay.addLayout(voice_row)
        self._refresh_voice_btns()

        # ── Voice Engine Architecture (Standard vs Jarvis VoxCPM2) ──────────
        from memory.config_manager import (
            get_voice_engine, save_voice_engine,
            get_jarvis_allow_cpu, save_jarvis_allow_cpu,
        )
        from core.tts.capability import check_jarvis_capability, Capability

        lbl_engine = _lbl("TTS SYNTHESIS ENGINE", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_engine)

        self._sel_voice_engine = (voice_engine or get_voice_engine() or "default").lower()
        if self._sel_voice_engine not in ("default", "jarvis"):
            self._sel_voice_engine = "default"

        self._engine_btns: dict[str, QPushButton] = {}
        engine_row = QHBoxLayout()
        engine_row.setSpacing(6)
        engines = [
            ("default", "STANDARD / DEFAULT"),
            ("jarvis", "JARVIS (VOXCPM2 LORA)"),
        ]
        for eng_id, eng_label in engines:
            eb = QPushButton(eng_label)
            eb.setCheckable(True)
            eb.setFixedHeight(29)
            eb.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            eb.setCursor(Qt.CursorShape.PointingHandCursor)
            eb.clicked.connect(lambda _=False, eid=eng_id: self._on_engine_pick(eid))
            attach_hover_help(eb, f"Select '{eng_label}' backend architecture for local vocal synthesis.", lbl_engine)
            self._engine_btns[eng_id] = eb
            engine_row.addWidget(eb)
        lay.addLayout(engine_row)

        # Status Line & Preview Button Row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._lbl_engine_status = QLabel("")
        self._lbl_engine_status.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=0.3))
        self._lbl_engine_status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._lbl_engine_status.setWordWrap(True)
        status_row.addWidget(self._lbl_engine_status, stretch=3)

        self._btn_preview_voice = QPushButton("▶ PREVIEW VOICE")
        self._btn_preview_voice.setFixedHeight(26)
        self._btn_preview_voice.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.5))
        self._btn_preview_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_preview_voice.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: rgba(0, 240, 255, 0.15);
                border-color: {C.PRI};
                color: #ffffff;
            }}
        """)
        self._btn_preview_voice.clicked.connect(self._preview_voice)
        attach_hover_help(self._btn_preview_voice, "Speak a fixed tactical verification phrase using the active voice engine.", lbl_engine)
        status_row.addWidget(self._btn_preview_voice, stretch=1)
        lay.addLayout(status_row)

        self._refresh_engine_ui()

        # ── Single Authentic CRT Themes Selector // Chromatics ─────────────
        from core.ui.themes import ThemeRegistry
        lbl_theme = _lbl("AUTHENTIC CRT THEMES // CHROMATICS", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_theme)
        swatch_grid = QGridLayout()
        swatch_grid.setSpacing(6)
        swatch_grid.setContentsMargins(0, 0, 0, 0)

        all_themes = ThemeRegistry.instance().list_themes()
        self._theme_btns: dict[str, QPushButton] = {}
        for idx, th in enumerate(all_themes):
            r = idx // 2
            c = idx % 2
            sb = QPushButton(th.display_name)
            sb.setFixedHeight(30)
            sb.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.5))
            sb.setCursor(Qt.CursorShape.PointingHandCursor)
            sb.clicked.connect(lambda _, h=th.hex: self._set_color(h, update_wheel=True, preview=True))
            attach_hover_help(sb, f"{th.display_name} ({th.hex}) — {th.tagline}", lbl_theme)
            self._theme_btns[th.display_name] = sb
            swatch_grid.addWidget(sb, r, c)
        lay.addLayout(swatch_grid)

        # ── HueWheel & Hex input ─────────────────────────────────────────
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)
        attach_hover_help(self._wheel, "Drag the color wheel to interactively tune custom HUD accent colors in real time.")

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#ff0037   (custom hex colour)")
        self._hex_input.setFont(mono_font(10))
        self._hex_input.setFixedHeight(30)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        attach_hover_help(self._hex_input, "Enter a custom 6-digit hex color code (e.g. #8e9bff, #00f0ff) for HUD styling.")
        lay.addWidget(self._hex_input)

        lay.addSpacing(6)
        lbl_api = _lbl("INTELLIGENCE BACKEND // API CREDENTIALS", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_api)
        api_btn = QPushButton("◈  SETUP API KEYS & NEURAL BACKEND")
        api_btn.setFixedHeight(32)
        api_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.8))
        api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        api_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                padding: 0 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
            }}
        """)
        api_btn.clicked.connect(lambda: self.setup_api_requested.emit())
        attach_hover_help(api_btn, "Open the API key configuration window to set up Gemini and OpenRouter credentials.", lbl_api)
        lay.addWidget(api_btn)

        scroll.setWidget(body_widget)
        outer_lay.addWidget(scroll, stretch=1)

        # Fixed Bottom Action Bar (ALWAYS visible!)
        sep_bottom = QFrame(); sep_bottom.setFrameShape(QFrame.Shape.HLine)
        sep_bottom.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;")
        outer_lay.addWidget(sep_bottom)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        save_btn = QPushButton("▸  COMMIT DIRECTIVE")
        save_btn.setFixedHeight(36)
        save_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.0))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
            }}
        """)
        save_btn.clicked.connect(self._save)
        attach_hover_help(save_btn, "Save and apply all persona, voice, insignia, and theme changes to your configuration.")
        btn_row.addWidget(save_btn, stretch=2)

        cancel_btn = QPushButton("DISCARD")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFont(mono_font(8, letter_spacing=0.8))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
            }}
            QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.12); }}
            QPushButton:pressed {{ background: rgba(142, 155, 255, 0.05); }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        attach_hover_help(cancel_btn, "Discard all unsaved changes and close the reconfiguration window.")
        btn_row.addWidget(cancel_btn, stretch=1)
        outer_lay.addLayout(btn_row)

    def _apply_preset(self, name: str, user: str, color: str, voice: str):
        self._name_input.setText(name)
        self._user_input.setText(user)
        self._sel_voice = voice
        self._refresh_voice_btns()
        self._set_color(color, update_wheel=True, preview=True)

    def reset_values(self, assistant_name: str, user_name: str, ui_color: str,
                     voice: str, current_icon: str, voice_engine: str | None = None) -> None:
        """Refresh reusable controls from persisted settings before showing."""
        self._name_input.setText(assistant_name or "Alfred")
        self._user_input.setText(user_name or "")
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._set_color(self._initial_color, update_wheel=True, preview=False)
        self._sel_voice = voice if voice in self._voice_btns else next(iter(self._voice_btns), self._sel_voice)
        self._refresh_voice_btns()
        self._current_icon = (current_icon or "").strip()
        self._initial_icon = self._current_icon
        self._refresh_icon_cards()
        if voice_engine:
            self._sel_voice_engine = voice_engine.lower()
        else:
            from memory.config_manager import get_voice_engine
            self._sel_voice_engine = get_voice_engine()
        self._refresh_engine_ui()

    # ── voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        """Highlight the selected voice pill; dim the rest."""
        for name, b in self._voice_btns.items():
            on = (name == self._sel_voice)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px; }}
                    QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    # ── voice engine selection & verification ────────────────────────────────
    def _on_engine_pick(self, eid: str):
        from core.tts.capability import check_jarvis_capability, Capability
        from memory.config_manager import get_jarvis_allow_cpu

        if eid == "jarvis":
            allow_cpu = get_jarvis_allow_cpu()
            cap = check_jarvis_capability(allow_cpu=allow_cpu)
            if not cap.is_usable(allow_cpu=allow_cpu):
                # Selecting jarvis when unavailable must not flip the setting into a broken state:
                # show why (from Capability), keep default active.
                self._sel_voice_engine = "default"
                self._refresh_engine_ui(warning_reason=cap.display_status())
                return
        self._sel_voice_engine = eid
        self._refresh_engine_ui()

    def _refresh_engine_ui(self, warning_reason: str | None = None):
        from core.tts.capability import check_jarvis_capability, Capability
        from memory.config_manager import get_jarvis_allow_cpu

        for eid, b in self._engine_btns.items():
            on = (eid == self._sel_voice_engine)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px; }}
                    QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

        allow_cpu = get_jarvis_allow_cpu()
        cap = check_jarvis_capability(allow_cpu=allow_cpu)

        if warning_reason:
            self._lbl_engine_status.setText(f"⚠ JARVIS BLOCKED: {warning_reason}")
            self._lbl_engine_status.setStyleSheet("color: #ffaa00; background: transparent;")
        elif self._sel_voice_engine == "jarvis":
            self._lbl_engine_status.setText(f"● ACTIVE: Jarvis Voice ({cap.display_status()})")
            color = "#00f0ff" if cap.is_usable(allow_cpu) else "#ffaa00"
            self._lbl_engine_status.setStyleSheet(f"color: {color}; background: transparent;")
        else:
            self._lbl_engine_status.setText(f"● ACTIVE: Standard Voice (Jarvis: {cap.display_status()})")
            self._lbl_engine_status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")

    def _preview_voice(self):
        eng = self._sel_voice_engine
        if getattr(self, "on_preview_voice", None):
            try:
                self.on_preview_voice(eng)
                return
            except Exception as e:
                print(f"[Voice Preview] Custom handler error: {e}")

        def _worker():
            try:
                from core.tts import get_engine
                engine = get_engine(eng)
                engine.speak("All systems nominal, sir. Tactical audio matrix online.")
            except Exception as exc:
                print(f"[Voice Preview] Synthesis error: {exc}")

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    # ── colour flow ──────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Updates the selected colour; hex box + wheel stay in sync, theme is live-previewed."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        self._refresh_theme_buttons()
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _refresh_theme_buttons(self):
        """Highlight active theme button; dim others with authentic styling."""
        from core.ui.themes import ThemeRegistry
        cur_theme = ThemeRegistry.instance().get(self._sel_color)
        for theme in ThemeRegistry.instance().list_themes():
            btn = self._theme_btns.get(theme.display_name)
            if not btn:
                continue
            is_active = (theme.id == cur_theme.id) or (self._sel_color.lower() == theme.hex.lower())
            accent_hex = theme.hex
            bg_hex = theme.palette.panel2
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {accent_hex}33;
                        color: #ffffff;
                        border: 1.5px solid {accent_hex};
                        border-radius: 2px;
                        padding: 0 10px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {bg_hex};
                        color: {accent_hex};
                        border: 1px solid {accent_hex}55;
                        border-radius: 2px;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        background: {accent_hex}22;
                        border-color: {accent_hex};
                        color: #ffffff;
                    }}
                """)

    def _on_wheel_pick(self, hx: str):
        # While dragging: update the hex box, don't apply the theme yet
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        # Handle released → live-preview the whole interface
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _refresh_icon_cards(self):
        norm_cur = Path(self._current_icon).name.lower() if self._current_icon else ""
        style_key = (norm_cur, C.PRI, C.PANEL2, C.BORDER_A)
        if getattr(self, "_icon_style_key", None) == style_key:
            return
        for path_key, btn in self._icon_cards.items():
            is_active = (path_key == self._current_icon) or (norm_cur and Path(path_key).name.lower() == norm_cur)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(0, 240, 255, 0.16);
                        border: 1.5px solid {C.PRI};
                        border-radius: 4px;
                        text-align: left;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2};
                        border: 1px solid {C.BORDER_A};
                        border-radius: 4px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background: rgba(142, 155, 255, 0.12);
                        border-color: {C.PRI};
                    }}
                """)
        self._icon_style_key = style_key

    def _on_icon_picked(self, path: str):
        self._current_icon = path
        self._refresh_icon_cards()
        if self.on_icon_change:
            try:
                self.on_icon_change(path)
            except Exception as e:
                print(f"[Icon] Realtime change error: {e}")

    def _cancel(self):
        TacticalHoverHelpManager.instance().dismiss()
        # If a preview was applied, revert to the colour from launch
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        if self.on_icon_change and self._current_icon != self._initial_icon:
            self.on_icon_change(self._initial_icon)
        self.hide()

    def _save(self):
        TacticalHoverHelpManager.instance().dismiss()
        name = self._name_input.text().strip() or "Alfred"
        user = self._user_input.text().strip()
        from memory.config_manager import save_voice_engine
        save_voice_engine(self._sel_voice_engine)
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice)
        if self._current_icon and self.on_icon_change:
            self.on_icon_change(self._current_icon)
        self.hide()

    def hideEvent(self, event):
        TacticalHoverHelpManager.instance().dismiss()
        super().hideEvent(event)


class CapabilitiesOverlay(QWidget):
    """
    Floating glassmorphic overlay displaying a categorized directory of everything
    Alfred can do, complete with live search filtering and Batcomputer theme styling.
    """
    _OW, _OH = 620, 680

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CapabilitiesOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        hdr = QLabel("📋  DIRECTIVES & CAPABILITIES ARCHIVE")
        hdr.setFont(tech_font(12, QFont.Weight.Bold, letter_spacing=2.0))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        title_box.addWidget(hdr)

        sub = QLabel("OPERATIONAL DIRECTIVES & VOICE CAPABILITIES DIRECTORY")
        sub.setFont(tech_font(8, letter_spacing=1.0))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        title_box.addWidget(sub)
        top_h.addLayout(title_box)
        top_h.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(tech_font(10, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: {C.RED};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        attach_hover_help(close_btn, "Close the directives and capabilities archive overlay.")
        top_h.addWidget(close_btn)
        lay.addLayout(top_h)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;")
        lay.addWidget(sep)

        # Search Bar
        search_box = QHBoxLayout()
        search_box.setSpacing(8)
        search_icon = QLabel("🔍")
        search_icon.setFont(tech_font(9))
        search_icon.setStyleSheet("background: transparent;")
        search_box.addWidget(search_icon)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter directives: e.g. open file, gmail, notes, weather, alarm, screen...")
        self._search.setFixedHeight(32)
        self._search.setFont(tech_font(9, letter_spacing=0.4))
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2};
                color: {C.WHITE};
                border: 1px solid {C.BORDER_A};
                border-radius: 6px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
                background: rgba(142, 155, 255, 0.08);
            }}
        """)
        self._search.textChanged.connect(self._filter_cards)
        attach_hover_help(self._search, "Type keywords to live-filter directives across files, emails, intel, web, and system tools.")
        search_box.addWidget(self._search)
        lay.addLayout(search_box)

        # Scroll area for capability cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_A};
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C.PRI};
            }}
        """)

        cards_w = QWidget()
        cards_w.setStyleSheet("background: transparent;")
        self._cards_lay = QVBoxLayout(cards_w)
        self._cards_lay.setContentsMargins(2, 6, 6, 6)
        self._cards_lay.setSpacing(10)

        self._cards: list[tuple[QWidget, str]] = []
        self._populate_capabilities()

        from core.ui.themes import ThemeChrome
        self._empty_lbl = QLabel(f"◈  {ThemeChrome.chrome().empty_archive.upper()}  ◈")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setFont(mono_font(9, QFont.Weight.Bold, letter_spacing=1.0))
        self._empty_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; padding: 40px; background: transparent;")
        self._empty_lbl.hide()
        self._cards_lay.addWidget(self._empty_lbl)

        scroll.setWidget(cards_w)
        lay.addWidget(scroll, stretch=1)

        # Footer row
        bot = QHBoxLayout()
        tip = QLabel("💡 Tip: Ask naturally via voice or type in Directive Input.")
        tip.setFont(tech_font(8, letter_spacing=0.3))
        tip.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        bot.addWidget(tip)
        bot.addStretch()

        dismiss = QPushButton("CLOSE")
        dismiss.setFixedSize(80, 28)
        dismiss.setFont(tech_font(8, QFont.Weight.Bold))
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
            }}
        """)
        dismiss.clicked.connect(self.hide)
        attach_hover_help(dismiss, "Close the directives and capabilities archive overlay.")
        bot.addWidget(dismiss)
        lay.addLayout(bot)

    def _populate_capabilities(self):
        cats = [
            ("📂  FILES & FOLDER EXPLORER", "#00f0ff", [
                ("Open Native Files", "Opens documents, PDFs, pictures, audio, spreadsheets in default OS apps ('open report.pdf')."),
                ("Explore Folders", "Opens and highlights directories or files in Windows File Explorer ('explore my downloads')."),
                ("Drive System Search", "Locates files across all system drives (C:, D:, Desktop, Documents) by name or extension."),
                ("File Management", "Create, read, write, copy, move, and rename files with built-in undo protection."),
                ("Desktop Organizer", "Automatically cleans and sorts scattered desktop files into organized category folders."),
            ]),
            ("✉️  GMAIL & COMMUNICATIONS", "#4488ff", [
                ("Read Unread Emails", "Fetches and summarizes recent unread emails with sender and subject priority."),
                ("Compose & Send Drafts", "Drafts and sends emails directly through your authenticated Google account."),
                ("Daily Email Briefing", "Delivers a morning summary of emails and calendar events during startup brief."),
                ("Messaging Automation", "Automates message sending to WhatsApp, Telegram, or Discord via PyAutoGUI."),
            ]),
            ("📝  INTEL & NOTES TERMINAL", "#ffb800", [
                ("Special Notes Terminal", "Saves research notes, key takeaways, and references into your dedicated side terminal."),
                ("Interactive Link Vault", "Stores clickable URLs and hyperlinks that launch in your default web browser."),
                ("Data & Code Logging", "Formats code blocks, tables, and structured data cleanly without crowding chat."),
                ("Clipboard Copy & Export", "One-click copy of all saved notes and persistent storage across reboots."),
            ]),
            ("🌐  WEB INTEL & MEDIA", "#00ff9d", [
                ("Live Google Grounding", "Real-time Google search for breaking news, up-to-date facts, and current events."),
                ("Article & Doc Extraction", "Extracts readable text from URLs and documentation pages."),
                ("YouTube Playback", "Searches and launches YouTube videos or audio tracks in your browser."),
                ("Weather & Atmosphere", "Current conditions, temperature forecasts, and air quality telemetry."),
            ]),
            ("⚙️  SYSTEM CONTROLS & TELEMETRY", "#ff6b00", [
                ("Telemetry Matrix", "Real-time telemetry tracking CPU, RAM, Network, GPU, and Core temperatures."),
                ("Acoustic Sensor Control", "Mute/unmute microphone listening, audio level HUD, and push-to-talk mode."),
                ("Desktop Deployment", "Deploy desktop shortcuts and configure auto-start on Windows boot."),
                ("Remote Neural Link", "Pair with companion mobile or browser interface for remote teleoperation."),
            ]),
            ("👁️  VISUAL RECON & MULTIMODAL", "#c084fc", [
                ("Screen Capture Recon", "Captures active monitor screen and provides instant visual analysis and debugging."),
                ("Live Webcam Stream", "Inspects webcam feed in the HUD or overlay for pair-programming and visual tasks."),
                ("Interactive Doc Review", "Provides structured document audits with severity markers (serious, caution, note)."),
            ]),
            ("⏰  ALARMS, TIMERS & SYNAPSE", "#ff5577", [
                ("Natural Speech Timers", "Set countdown timers and alarms ('set a timer for 15 minutes')."),
                ("Scheduled Reminders", "Set reminders that notify you at specific times or intervals."),
                ("Synapse Long-Term Memory", "Remembers your preferences, habits, instructions, and name across all sessions."),
            ]),
        ]

        for cat_title, color, items in cats:
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER};
                    border-left: 3px solid {color};
                    border-radius: 6px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(12, 10, 12, 10)
            c_lay.setSpacing(6)

            h = QLabel(cat_title)
            h.setFont(tech_font(9, QFont.Weight.Bold, letter_spacing=1.0))
            h.setStyleSheet(f"color: {color}; background: transparent; border: none;")
            c_lay.addWidget(h)

            full_text = cat_title + " "
            for title, desc in items:
                row = QHBoxLayout()
                row.setSpacing(6)
                b_lbl = QLabel(f"• <b>{title}</b>: <span style='color: {C.TEXT_MED};'>{desc}</span>")
                b_lbl.setTextFormat(Qt.TextFormat.RichText)
                b_lbl.setFont(tech_font(8, letter_spacing=0.2))
                b_lbl.setStyleSheet("background: transparent; border: none;")
                b_lbl.setWordWrap(True)
                row.addWidget(b_lbl)
                c_lay.addLayout(row)
                full_text += f"{title} {desc} "

            self._cards_lay.addWidget(card)
            self._cards.append((card, full_text.lower()))

    def _filter_cards(self, text: str):
        q = text.strip().lower()
        matched = 0
        for card, searchable in self._cards:
            if not q or q in searchable:
                card.show()
                matched += 1
            else:
                card.hide()
        if matched == 0:
            self._empty_lbl.show()
        else:
            self._empty_lbl.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        TacticalHoverHelpManager.instance().dismiss()
        super().hideEvent(event)


class PluginManagerOverlay(QWidget):
    """Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles."""

    _OW = 420

    def __init__(self, plugins: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginManagerOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        hdr = QLabel("🧩  TACTICAL EXTENSIONS")
        hdr.setFont(tech_font(12, QFont.Weight.Bold, 60))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        if not plugins:
            empty = QLabel("No plugins discovered in /plugins repository.")
            empty.setFont(tech_font(8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        lay.addSpacing(4)
        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(32)
        close_btn.setFont(tech_font(9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(8)

        label_text = p["name"] if p["valid"] else f"{p['name']}  (⚠ {p['file']})"
        lbl = QLabel(label_text)
        lbl.setFont(tech_font(9))
        lbl.setStyleSheet(f"color: {C.TEXT if p['valid'] else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p["description"] if p["valid"] else p["error"])
        lbl.setWordWrap(False)
        row.addWidget(lbl, stretch=1)

        btn = QPushButton()
        btn.setFixedSize(76, 26)
        btn.setFont(tech_font(8, QFont.Weight.Bold, 30))
        if not p["valid"]:
            btn.setText("OFFLINE")
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 4px;
                }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, p["enabled"])
            btn.clicked.connect(lambda _, name=p["name"], b=btn: self._toggle(name, b))
        row.addWidget(btn)
        return row

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ACTIVE")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0, 255, 157, 0.15); color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 4px;
                }}
                QPushButton:hover {{ background: rgba(0, 255, 157, 0.25); }}
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 4px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
            """)

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)


class _HudOverlay(QWidget):
    """Base for the floating panels placed by hand over the HUD.

    They are children of the central widget but sit in no layout, so Qt never
    invalidates the region they occupy when they hide or shrink: the HUD keeps
    painting around them and their last frame stays on screen as a ghost. Any
    overlay positioned with _centre_overlay needs this."""

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            # Repaint exactly what we were covering, before we stop covering it.
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)


class ConfirmBanner(_HudOverlay):
    """The gate in front of an action that cannot be taken back.

    The old confirmation was a tool parameter the model filled in itself, which
    means it confirmed its own shutdown requests. This is the interface asking,
    and the answer travels from a human finger to core/confirm.py without the
    model in the loop. Nothing blocks while it is up: the assistant keeps
    talking, so this costs no latency — unlike the old gate, which spent two
    tool round trips on every power command."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ConfirmBanner {{
                background: rgba(22, 6, 2, 0.96);
                border: 1px solid rgba(255, 115, 0, 0.45);
                border-radius: 14px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)

        hdr = QLabel("⚠  TACTICAL OVERRIDE CONFIRMATION")
        hdr.setFont(tech_font(11, QFont.Weight.Bold, 60))
        hdr.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(hdr)

        ttl = QLabel(title)
        ttl.setWordWrap(True)
        ttl.setFont(tech_font(10, QFont.Weight.Bold, 30))
        ttl.setStyleSheet(f"color: {C.TEXT_BRIGHT}; background: transparent;")
        lay.addWidget(ttl)

        if detail:
            dtl = QLabel(detail)
            dtl.setWordWrap(True)
            dtl.setFont(tech_font(9))
            dtl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            lay.addWidget(dtl)

        row = QHBoxLayout(); row.setSpacing(10)

        yes = QPushButton("▸  CONFIRM ACTION")
        yes.setFixedHeight(36)
        yes.setFont(tech_font(9, QFont.Weight.Bold, 50))
        yes.setCursor(Qt.CursorShape.PointingHandCursor)
        yes.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 115, 0, 0.35), stop:1 rgba(255, 60, 0, 0.20)); color: #ffffff;
                border: 1px solid {C.ACC}; border-radius: 9px; }}
            QPushButton:hover {{ background: rgba(255, 115, 0, 0.50); color: {C.WHITE}; border-color: #ffffff; }}
            QPushButton:pressed {{ background: rgba(255, 115, 0, 0.20); }}
        """)
        yes.clicked.connect(lambda: self.answered.emit(True))
        row.addWidget(yes)

        no = QPushButton("ABORT")
        no.setFixedHeight(36)
        no.setFont(tech_font(9, QFont.Weight.Bold))
        no.setCursor(Qt.CursorShape.PointingHandCursor)
        no.setStyleSheet(f"""
            QPushButton {{ background: rgba(255, 255, 255, 0.04); color: {C.TEXT_MED};
                border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 9px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: rgba(255, 115, 0, 0.4); background: rgba(255, 255, 255, 0.08); }}
            QPushButton:pressed {{ background: rgba(255, 255, 255, 0.02); }}
        """)
        no.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(no)
        lay.addLayout(row)

        # Default focus on CANCEL: if someone hits Enter without reading, the
        # safe answer wins.
        no.setDefault(True)
        no.setFocus()


class AudioDeviceOverlay(_HudOverlay):
    """Choose which microphone ALFRED listens to and which speakers it uses.

    Both audio streams used to open with no `device=` at all, so they always
    took the OS default — which on Windows moves by itself the moment a headset
    is plugged in. 'ALFRED can't hear me' is usually 'ALFRED is listening to the
    webcam'."""

    picked = pyqtSignal()      # emitted after Apply, when something changed
    _OW = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.audio_devices import list_devices, DEFAULT_LABEL
        from memory.config_manager import get_input_device, get_output_device

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AudioDeviceOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(8)

        hdr = QLabel("🎧  ACOUSTIC ROUTING MATRIX")
        hdr.setFont(tech_font(12, QFont.Weight.Bold, 60))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        _combo_css = (
            f"QComboBox {{ background: rgba(3, 14, 25, 0.85); color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER_B}; border-radius: 5px; padding: 4px 10px; }}"
            f"QComboBox:hover {{ border-color: {C.PRI_DIM}; }}"
            f"QComboBox QAbstractItemView {{ background: #030e19; color: {C.TEXT}; "
            f"selection-background-color: {C.PRI_GHO}; border: 1px solid {C.BORDER_B}; }}"
        )

        def _row(label: str, kind: str, current: str) -> QComboBox:
            cap = QLabel(label)
            cap.setFont(tech_font(8, QFont.Weight.Bold, 30))
            cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(cap)

            box = QComboBox()
            box.setFont(tech_font(9))
            box.setFixedHeight(32)
            box.setStyleSheet(_combo_css)
            box.addItem(DEFAULT_LABEL, "")
            for name in list_devices(kind):
                box.addItem(name, name)
            idx = box.findData(current) if current else 0
            box.setCurrentIndex(idx if idx >= 0 else 0)
            if current and idx < 0:
                box.addItem(f"{current}  (not connected)", current)
                box.setCurrentIndex(box.count() - 1)
            lay.addWidget(box)
            return box

        self._in_box  = _row("MICROPHONE SENSOR — acoustic capture feed",
                             "input", get_input_device())
        lay.addSpacing(4)
        self._out_box = _row("TRANSMIT SPEAKERS — vocal synthesis output",
                             "output", get_output_device())

        note = QLabel("Applying reconnects the session. Active memory matrix is preserved.")
        note.setWordWrap(True)
        note.setFont(tech_font(7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addSpacing(6)
        lay.addWidget(note)

        row = QHBoxLayout(); row.setSpacing(8)
        ok = QPushButton("▸  APPLY ROUTING")
        ok.setFixedHeight(34)
        ok.setFont(tech_font(9, QFont.Weight.Bold, 50))
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.15), stop:1 rgba(0,180,255,0.06));
                color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.28), stop:1 rgba(0,200,255,0.12));
                color: {C.TEXT_BRIGHT}; border-color: {C.TEXT_BRIGHT};
            }}
        """)
        ok.clicked.connect(self._apply)
        row.addWidget(ok)

        cancel = QPushButton("CLOSE")
        cancel.setFixedHeight(34)
        cancel.setFont(tech_font(9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _apply(self):
        from memory.config_manager import (
            get_input_device, get_output_device,
            save_input_device, save_output_device,
        )
        new_in  = self._in_box.currentData()  or ""
        new_out = self._out_box.currentData() or ""
        changed = (new_in != get_input_device()) or (new_out != get_output_device())
        save_input_device(new_in)
        save_output_device(new_out)
        self.hide()
        # Only rebuild the session if something actually moved — a no-op Apply
        # should not cost a reconnect.
        if changed:
            self.picked.emit()


class MemoryOverlay(_HudOverlay):
    """Everything ALFRED has stored about you, and when it learned it.

    Memory used to be a 2200-character store that deleted its oldest entries
    when full and mentioned it only on stdout. The cap is gone; this panel is
    the other half of that change — a memory you cannot inspect is a memory you
    cannot trust, and 'delete' has to be something the person can do."""

    _OW = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MemoryOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(22, 18, 22, 18)
        self._lay.setSpacing(6)
        self._rebuild()

    def _clear_layout(self):
        """Take every item out of the layout and detach it from the widget tree
        in this call.

        deleteLater() on its own is not enough: it queues destruction for the
        next event-loop pass, and until then the old rows are still children of
        this widget and still paint — which is what drew half of the previous
        panel over the new one. setParent(None) removes them from the tree now;
        deleteLater() then frees them safely."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() stops it painting in this frame; deleteLater() frees it
                # safely afterwards. setParent(None) would also stop the paint,
                # but it turns the widget into a top-level window for the moment
                # between the two calls, which is not something to leave lying
                # around inside a click handler.
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _settle(self, before):
        """Size the panel to its content, re-centre it, and repaint what the old
        size covered."""
        self._lay.invalidate()
        self._lay.activate()
        self.updateGeometry()
        self.adjustSize()

        p = self.parentWidget()
        if p is None:
            self.update()
            return
        self.move(max(0, (p.width()  - self.width())  // 2),
                  max(0, (p.height() - self.height()) // 2))
        p.update(before.united(self.geometry()))
        self.update()

    def _rebuild(self):
        before = self.geometry()
        self._clear_layout()

        from memory.memory_manager import all_entries_for_ui

        hdr = QLabel("🧠  NEURAL SYNAPSE ARCHIVE")
        hdr.setFont(tech_font(12, QFont.Weight.Bold, 60))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        rows = all_entries_for_ui()

        cap = QLabel(f"{len(rows)} persistent telemetry records — local secure storage "
                     f"at memory/long_term.json.")
        cap.setWordWrap(True)
        cap.setFont(tech_font(8))
        cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(cap)

        if not rows:
            empty = QLabel("No neural data recorded in long-term store.")
            empty.setFont(tech_font(9))
            empty.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._lay.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(min(420, 36 * len(rows) + 10))
            scroll.setStyleSheet(f"""
                QScrollArea {{
                    border: 1px solid {C.BORDER};
                    border-radius: 6px;
                    background: rgba(3, 14, 25, 0.60);
                }}
            """)
            inner = QWidget()
            ilay  = QVBoxLayout(inner)
            ilay.setContentsMargins(8, 8, 8, 8)
            ilay.setSpacing(4)

            for r in rows:
                line = QHBoxLayout(); line.setSpacing(8)
                txt = QLabel(f"<b>{r['key'].replace('_', ' ')}</b> "
                             f"<span style='color:{C.TEXT_MED}'>— {r['value']}</span>")
                txt.setWordWrap(True)
                txt.setFont(tech_font(9))
                txt.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                line.addWidget(txt, 1)

                meta = QLabel(f"{r['category'][:4]} · {r['updated'] or '—'}")
                meta.setFont(mono_font(8))
                meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                line.addWidget(meta)

                rm = QPushButton("✕")
                rm.setFixedSize(20, 20)
                rm.setFont(mono_font(8, QFont.Weight.Bold))
                rm.setCursor(Qt.CursorShape.PointingHandCursor)
                rm.setToolTip("Purge record")
                rm.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 4px; }}
                    QPushButton:hover {{ color: {C.RED}; border-color: {C.RED}; background: rgba(255, 51, 85, 0.15); }}
                """)
                rm.clicked.connect(
                    lambda _=False, c=r["category"], k=r["key"]: self._forget(c, k))
                line.addWidget(rm)

                holder = QWidget()
                holder.setLayout(line)
                ilay.addWidget(holder)

            ilay.addStretch()
            scroll.setWidget(inner)
            self._lay.addWidget(scroll)

        close = QPushButton("CLOSE")
        close.setFixedHeight(34)
        close.setFont(tech_font(9, QFont.Weight.Bold))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self._settle(before)
        QTimer.singleShot(0, lambda g=before: self._settle(g))

    def _forget(self, category: str, key: str):
        from memory.memory_manager import forget
        forget(key, category)
        # Rebuild on the NEXT event-loop turn, not inside this click handler.
        # The rebuild destroys the very ✕ button that emitted this signal, and
        # Qt is entitled to touch the sender after a slot returns; tearing it
        # down mid-emission is how a widget ends up half-alive on screen.
        QTimer.singleShot(0, self._rebuild)


class ClipboardPanel(QWidget):
    """Floating panel shown when text is copied — offers quick Alfred actions."""

    action_requested = pyqtSignal(str)
    _W, _H = 326, 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        hdr = QHBoxLayout(); hdr.setSpacing(6)
        icon_lbl = QLabel("◈  CLIPBOARD STREAM INTERCEPTED")
        icon_lbl.setFont(tech_font(8, QFont.Weight.Bold, 40))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl); hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(18, 18)
        x_btn.setFont(mono_font(8, QFont.Weight.Bold))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(mono_font(8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: rgba(3, 14, 25, 0.80);
            border: 1px solid {C.BORDER_B}; border-radius: 4px; padding: 4px 8px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(28)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        _bs = (f"QPushButton {{ background: rgba(0, 240, 255, 0.08); color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 4px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI}; background: rgba(0, 240, 255, 0.16); }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN",   "Explain this: {text}"),
            ("FIX",       "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.setFont(tech_font(7, QFont.Weight.Bold, 30))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:58].replace('\n', ' ')
        if len(text) > 58:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show(); self.raise_()
        self._dismiss_timer.start(8000)


class PluginSettingsOverlay(QWidget):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    setup_api_requested = pyqtSignal()
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 10px;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: rgba(3, 14, 25, 0.85); color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER_B}; border-radius: 4px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)

        root.addWidget(self._lbl("⚙  EXTENSION CONFIGURATION MATRIX", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                "No configurable plugins are installed.\nDrop a plugin that needs "
                "settings into the plugins folder and it will appear here.", 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton("▸  SAVE CHANGES")
            save_btn.setFixedHeight(34)
            save_btn.setFont(tech_font(9, QFont.Weight.Bold, 50))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.15), stop:1 rgba(0,180,255,0.06));
                    color: {C.PRI};
                    border: 1px solid {C.PRI}; border-radius: 5px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.28), stop:1 rgba(0,200,255,0.12));
                    color: {C.TEXT_BRIGHT}; border-color: {C.TEXT_BRIGHT};
                }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        api_btn = QPushButton("◈  SETUP API")
        api_btn.setFixedHeight(34)
        api_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.5))
        api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        api_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 4px; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        api_btn.clicked.connect(lambda: self.setup_api_requested.emit())
        btn_row.addWidget(api_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(34)
        close_btn.setFont(tech_font(9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(tech_font(fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal,
                            50 if bold else 20))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)

            form.addWidget(self._lbl(label.upper(), 8, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(tech_font(9))
                w.setFixedHeight(30)
                w.setStyleSheet(
                    f"QComboBox {{ background: rgba(3, 14, 25, 0.85); color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER_B}; border-radius: 4px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: #030e19; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(tech_font(8, QFont.Weight.Bold, 30))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(mono_font(10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.EchoMode.Password)

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            form.addWidget(w)

        # optional test/connect action button + status line
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or "TEST"))
            ab.setFixedHeight(30)
            ab.setFont(tech_font(8, QFont.Weight.Bold, 40))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: rgba(0, 240, 255, 0.08); color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 4px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ACTIVE" if on else "OFF")
        if on:
            btn.setStyleSheet(f"QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI}; "
                              f"border: 1px solid {C.PRI}; border-radius: 3px; }}")
        else:
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                              f"border: 1px solid {C.BORDER}; border-radius: 3px; }}")

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        save_plugin_config(ns, self._gather(ns))

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                self._save_ns(ns)
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText("Saved ✓")
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        self._save_ns(ns)                 # persist what the user typed before testing
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText("Testing…")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok, msg = False, str(e)
            self._test_done.emit(ns, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")


# ── Remote Uplink Popup Named Constants ──────────────────────────────────────
UPLINK_OVERLAY_W: int = 500
UPLINK_OVERLAY_H: int = 620
UPLINK_QR_SIZE: int = 176
UPLINK_CORNER_BRACKET_LEN: int = 12
UPLINK_CORNER_BRACKET_WIDTH: float = 1.5
UPLINK_COPY_FLASH_MS: int = 1400


class RemoteKeyOverlay(_HudOverlay):
    """Batcomputer-grade tactical floating overlay for companion device pairing."""

    closed = pyqtSignal()

    _OW: int = UPLINK_OVERLAY_W
    _OH: int = UPLINK_OVERLAY_H

    def __init__(
        self,
        url: str,
        key: str,
        auto_login_url: str = "",
        manual_url: str = "",
        desktop_url: str = "",
        expiry_secs: int = 600,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self._OW, self._OH)
        self.setObjectName("remoteKeyOverlay")

        self._expiry: float = time.time() + expiry_secs
        self._on_new_key = None
        self._auto_login_url: str = auto_login_url
        self._manual_url: str = manual_url or url
        self._desktop_url: str = desktop_url
        self._current_key: str = key
        self._drag_start_pos: QPoint | None = None
        self._copy_flash_timers: dict[str, QTimer] = {}

        self._build_ui()
        self._apply_theme_styles()
        self._render_links()
        self._update_qr(self._auto_login_url or url)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def _build_ui(self) -> None:
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(16, 14, 16, 14)
        root_lay.setSpacing(10)

        # ── Header Strip (Draggable Area) ───────────────────────────────────────
        self._header_widget = QWidget(self)
        self._header_widget.setObjectName("uplinkHeader")
        hdr_lay = QHBoxLayout(self._header_widget)
        hdr_lay.setContentsMargins(4, 2, 4, 4)
        hdr_lay.setSpacing(8)

        # Tactical Insignia
        self._insignia_lbl = QLabel("◈")
        self._insignia_lbl.setFont(tech_font(12, QFont.Weight.Bold))
        hdr_lay.addWidget(self._insignia_lbl)

        # Title & Sub-status
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._title_lbl = QLabel("REMOTE UPLINK NODE")
        self._title_lbl.setFont(mono_font(10, QFont.Weight.Bold, letter_spacing=1.8))
        title_box.addWidget(self._title_lbl)

        self._status_line_lbl = QLabel("SECURE CHANNEL // AES-256 TELEMETRY")
        self._status_line_lbl.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=1.0))
        title_box.addWidget(self._status_line_lbl)
        hdr_lay.addLayout(title_box)

        hdr_lay.addStretch()

        # Corner Close Button
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setFont(tech_font(9, QFont.Weight.Bold))
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._do_close)
        attach_hover_help(self._close_btn, "Dismiss the remote pairing overlay.")
        hdr_lay.addWidget(self._close_btn)

        root_lay.addWidget(self._header_widget)

        # ── Center Content: QR Frame (Left) + Coordinate Rows (Right) ──────────
        center_row = QHBoxLayout()
        center_row.setContentsMargins(2, 2, 2, 2)
        center_row.setSpacing(16)

        # QR Column
        qr_col = QVBoxLayout()
        qr_col.setSpacing(6)
        qr_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._qr_frame = QFrame(self)
        self._qr_frame.setObjectName("qrChassis")
        self._qr_frame.setFixedSize(UPLINK_QR_SIZE + 12, UPLINK_QR_SIZE + 12)
        qr_frame_lay = QVBoxLayout(self._qr_frame)
        qr_frame_lay.setContentsMargins(6, 6, 6, 6)

        self._qr_label = QLabel(self._qr_frame)
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(UPLINK_QR_SIZE, UPLINK_QR_SIZE)
        qr_frame_lay.addWidget(self._qr_label)
        qr_col.addWidget(self._qr_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self._scan_lbl = QLabel("SCAN TO PAIR")
        self._scan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scan_lbl.setFont(tech_font(7, QFont.Weight.Bold, letter_spacing=1.4))
        qr_col.addWidget(self._scan_lbl)
        center_row.addLayout(qr_col, stretch=0)

        # Coordinates & Key Column
        info_col = QVBoxLayout()
        info_col.setSpacing(8)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Helper to create a tactical coordinate field
        def _make_field_row(field_id: str, label_text: str, tooltip_text: str):
            box = QVBoxLayout()
            box.setSpacing(2)

            # Header row with field label and copy feedback flash label
            hdr = QHBoxLayout()
            hdr.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setFont(tech_font(7, QFont.Weight.Bold, letter_spacing=1.0))
            hdr.addWidget(lbl)

            flash = QLabel("")
            flash.setFont(tech_font(7, QFont.Weight.Bold))
            flash.hide()
            hdr.addWidget(flash)
            hdr.addStretch()

            box.addLayout(hdr)

            # Value row with container, value label, and tactical copy button
            val_frame = QFrame(self)
            val_frame.setObjectName(f"valFrame_{field_id}")
            vf_lay = QHBoxLayout(val_frame)
            vf_lay.setContentsMargins(8, 4, 4, 4)
            vf_lay.setSpacing(6)

            val_lbl = QLabel("—")
            val_lbl.setFont(mono_font(8, QFont.Weight.Normal))
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            val_lbl.setOpenExternalLinks(True)
            vf_lay.addWidget(val_lbl, stretch=1)

            copy_btn = QPushButton("⎘")
            copy_btn.setFixedSize(22, 22)
            copy_btn.setFont(tech_font(9, QFont.Weight.Bold))
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.setObjectName("tacticalCopyBtn")
            attach_hover_help(copy_btn, f"Copy {label_text} value to clipboard.")
            vf_lay.addWidget(copy_btn, stretch=0)

            box.addWidget(val_frame)
            attach_hover_help(val_frame, tooltip_text, lbl)
            info_col.addLayout(box)
            return val_lbl, copy_btn, flash

        self._lan_lbl, self._lan_copy_btn, self._lan_flash = _make_field_row(
            "lan", "LAN COORDINATES",
            "Local Network address for mobile or secondary device pairing."
        )
        self._lan_copy_btn.clicked.connect(lambda: self._copy_to_clipboard(self._manual_url, self._lan_flash))

        self._local_lbl, self._local_copy_btn, self._local_flash = _make_field_row(
            "localhost", "LOCALHOST DASHBOARD",
            "Direct local loopback address for browser dashboard access."
        )
        self._local_copy_btn.clicked.connect(
            lambda: self._copy_to_clipboard(self._desktop_url or self._manual_url, self._local_flash)
        )

        self._manual_lbl, self._manual_copy_btn, self._manual_flash = _make_field_row(
            "manual", "MANUAL ENTRY",
            "IP and port coordinates for manual browser entry without auto-token."
        )
        self._manual_copy_btn.clicked.connect(
            lambda: self._copy_to_clipboard(self._extract_host_port(self._manual_url), self._manual_flash)
        )

        center_row.addLayout(info_col, stretch=1)
        root_lay.addLayout(center_row)

        # ── Access Key Pill ─────────────────────────────────────────────────────
        key_box = QVBoxLayout()
        key_box.setSpacing(3)
        key_hdr_row = QHBoxLayout()
        key_lbl_title = QLabel("ACCESS CREDENTIAL")
        key_lbl_title.setFont(tech_font(7, QFont.Weight.Bold, letter_spacing=1.2))
        key_hdr_row.addWidget(key_lbl_title)

        self._key_flash = QLabel("")
        self._key_flash.setFont(tech_font(7, QFont.Weight.Bold))
        self._key_flash.hide()
        key_hdr_row.addWidget(self._key_flash)
        key_hdr_row.addStretch()
        key_box.addLayout(key_hdr_row)

        self._key_frame = QFrame(self)
        self._key_frame.setObjectName("keyChassis")
        kf_lay = QHBoxLayout(self._key_frame)
        kf_lay.setContentsMargins(12, 6, 8, 6)
        kf_lay.setSpacing(8)

        self._key_lbl = QLabel(self._current_key)
        self._key_lbl.setFont(mono_font(18, QFont.Weight.Bold, letter_spacing=6.0))
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        kf_lay.addWidget(self._key_lbl, stretch=1)

        self._key_copy_btn = QPushButton("⎘")
        self._key_copy_btn.setFixedSize(28, 28)
        self._key_copy_btn.setFont(tech_font(11, QFont.Weight.Bold))
        self._key_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key_copy_btn.setObjectName("tacticalCopyBtn")
        self._key_copy_btn.clicked.connect(lambda: self._copy_to_clipboard(self._current_key, self._key_flash))
        attach_hover_help(self._key_copy_btn, "Copy access credential key to clipboard.")
        kf_lay.addWidget(self._key_copy_btn, stretch=0)

        key_box.addWidget(self._key_frame)
        attach_hover_help(self._key_frame, "Temporary one-time session authentication credential.", key_lbl_title)
        root_lay.addLayout(key_box)

        # ── Timer & Security Status Readout ────────────────────────────────────
        self._timer_lbl = QLabel("Key expires in  10:00")
        self._timer_lbl.setFont(tech_font(8, QFont.Weight.Medium, letter_spacing=0.8))
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_lay.addWidget(self._timer_lbl)

        # ── Tactical Action Controls ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._open_btn = QPushButton("↗ OPEN IN BROWSER")
        self._open_btn.setFixedHeight(34)
        self._open_btn.setFont(tech_font(8, QFont.Weight.Bold, letter_spacing=0.8))
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setObjectName("primaryActionButton")
        self._open_btn.clicked.connect(self._open_in_browser)
        attach_hover_help(self._open_btn, "Launch default web browser directly with encrypted auto-authentication token.")
        btn_row.addWidget(self._open_btn, stretch=2)

        self._new_btn = QPushButton("NEW KEY")
        self._new_btn.setFixedHeight(34)
        self._new_btn.setFont(tech_font(8, QFont.Weight.Bold, letter_spacing=0.6))
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setObjectName("secondaryActionButton")
        self._new_btn.clicked.connect(self._refresh_key)
        attach_hover_help(self._new_btn, "Revoke current authentication key and generate a fresh session token.")
        btn_row.addWidget(self._new_btn, stretch=1)

        self._dismiss_btn = QPushButton("DISMISS")
        self._dismiss_btn.setFixedHeight(34)
        self._dismiss_btn.setFont(tech_font(8, QFont.Weight.Bold, letter_spacing=0.6))
        self._dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_btn.setObjectName("ghostActionButton")
        self._dismiss_btn.clicked.connect(self._do_close)
        attach_hover_help(self._dismiss_btn, "Close pairing dialog and return to tactical HUD.")
        btn_row.addWidget(self._dismiss_btn, stretch=1)

        root_lay.addLayout(btn_row)

        # ── Footer Status Strip ────────────────────────────────────────────────
        self._footer_lbl = QLabel("UPLINK ARMED // WAITING FOR HANDSHAKE")
        self._footer_lbl.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=1.2))
        self._footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_lay.addWidget(self._footer_lbl)

    def _apply_theme_styles(self) -> None:
        """Retint all chrome, borders, and tactical buttons according to the active theme palette."""
        self.setStyleSheet(f"""
            QWidget#uplinkHeader {{
                background: transparent;
                border-bottom: 1px solid {C.BORDER_A};
                padding-bottom: 4px;
            }}
            QFrame#qrChassis {{
                background: rgba(3, 8, 18, 0.92);
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
            QLabel {{
                color: {C.TEXT};
                background: transparent;
            }}
            QFrame[objectName^="valFrame_"] {{
                background: {C.PANEL2};
                border: 1px solid {C.BORDER_A};
                border-radius: 3px;
            }}
            QFrame[objectName^="valFrame_"]:hover {{
                border: 1px solid {C.PRI_DIM};
            }}
            QFrame#keyChassis {{
                background: {C.PANEL2};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
            QPushButton#closeButton, QPushButton#uplinkCloseBtn {{
                background: transparent;
                color: {C.TEXT_DIM};
                border: 1px solid transparent;
                border-radius: 2px;
            }}
            QPushButton#closeButton:hover, QPushButton#uplinkCloseBtn:hover {{
                color: {C.RED};
                background: rgba(255, 42, 85, 0.16);
                border-color: {C.RED};
            }}
            QPushButton#tacticalCopyBtn {{
                background: rgba(142, 155, 255, 0.08);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
            }}
            QPushButton#tacticalCopyBtn:hover {{
                background: rgba(142, 155, 255, 0.22);
                color: #ffffff;
                border-color: {C.PRI};
            }}
            QPushButton#primaryActionButton {{
                background: rgba(142, 155, 255, 0.16);
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 3px;
                padding: 0 12px;
            }}
            QPushButton#primaryActionButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
                border-color: #ffffff;
            }}
            QPushButton#primaryActionButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
            QPushButton#secondaryActionButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 3px;
                padding: 0 10px;
            }}
            QPushButton#secondaryActionButton:hover {{
                color: #ffffff;
                border-color: {C.PRI};
                background: rgba(142, 155, 255, 0.12);
            }}
            QPushButton#ghostActionButton {{
                background: transparent;
                color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 0 10px;
            }}
            QPushButton#ghostActionButton:hover {{
                color: {C.TEXT};
                border-color: {C.BORDER_B};
                background: rgba(255, 255, 255, 0.04);
            }}
        """)

        self._insignia_lbl.setStyleSheet(f"color: {C.PRI};")
        self._title_lbl.setStyleSheet(f"color: {C.PRI};")
        self._status_line_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._scan_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._key_lbl.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._footer_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom HUD chassis rendering with angular corner brackets, dark translucent backing, and scanlines."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # 1. Dark translucent CRT chassis
        p.fillRect(rect, qcol(C.BG, 246))

        # 2. Subtle CRT scanlines
        p.setPen(qcol(C.PRI_GHO, 40))
        for y in range(0, h, 4):
            p.drawLine(0, y, w, y)

        # 3. Outer border frame
        border_pen = QPen(qcol(C.BORDER, 200), 1.0)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)

        # 4. Precision Angular Corner Brackets
        cb_pen = QPen(qcol(C.PRI, 240), UPLINK_CORNER_BRACKET_WIDTH)
        p.setPen(cb_pen)
        bl = UPLINK_CORNER_BRACKET_LEN

        # Top-Left
        p.drawLine(1, 1, 1 + bl, 1)
        p.drawLine(1, 1, 1, 1 + bl)

        # Top-Right
        p.drawLine(w - 2 - bl, 1, w - 2, 1)
        p.drawLine(w - 2, 1, w - 2, 1 + bl)

        # Bottom-Left
        p.drawLine(1, h - 2 - bl, 1, h - 2)
        p.drawLine(1, h - 2, 1 + bl, h - 2)

        # Bottom-Right
        p.drawLine(w - 2 - bl, h - 2, w - 2, h - 2)
        p.drawLine(w - 2, h - 2 - bl, w - 2, h - 2)

        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 48:
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    @staticmethod
    def _extract_host_port(url: str) -> str:
        if not url:
            return ""
        clean = url.replace("https://", "").replace("http://", "").split("/")[0]
        return clean

    def _copy_to_clipboard(self, text: str, flash_lbl: QLabel | None = None) -> None:
        if not text:
            return
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        if flash_lbl:
            flash_lbl.setText("COPIED ✓")
            flash_lbl.setStyleSheet(f"color: {C.GREEN};")
            flash_lbl.show()
            timer_id = str(id(flash_lbl))
            old_timer = self._copy_flash_timers.get(timer_id)
            if old_timer:
                old_timer.stop()
            tmr = QTimer(self)
            tmr.setSingleShot(True)
            tmr.timeout.connect(lambda: flash_lbl.hide())
            tmr.start(UPLINK_COPY_FLASH_MS)
            self._copy_flash_timers[timer_id] = tmr

    def _render_links(self) -> None:
        if self._manual_url:
            self._lan_lbl.setText(
                f'<a href="{self._manual_url}" style="color: {C.PRI}; text-decoration: underline;">{self._manual_url}</a>'
            )
            self._manual_lbl.setText(self._extract_host_port(self._manual_url))
        else:
            self._lan_lbl.setText("—")
            self._manual_lbl.setText("—")

        link = self._desktop_url or self._auto_login_url
        if link:
            self._local_lbl.setText(
                f'<a href="{link}" style="color: {C.ACC}; text-decoration: underline;">{link}</a>'
            )
        else:
            self._local_lbl.setText("—")

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO

            qr = _qrmod.QRCode(
                box_size=5,
                border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            # High-contrast black on white QR modules for dependable mobile camera scanning
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(
                    UPLINK_QR_SIZE,
                    UPLINK_QR_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._qr_label.setStyleSheet("background: white; border-radius: 4px; padding: 2px;")
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(tech_font(8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 4px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(mono_font(7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 4px; padding: 4px;"
            )

    def _tick(self) -> None:
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText("UPLINK ACTIVE")
        self._key_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; letter-spacing: 2px;")
        self._key_frame.setStyleSheet(f"""
            QFrame#keyChassis {{
                background: rgba(34, 197, 94, 0.14);
                border: 1px solid {C.GREEN};
                border-radius: 4px;
            }}
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(tech_font(48, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            f"color: {C.GREEN}; background: rgba(3, 14, 25, 0.95); border-radius: 4px;"
        )
        self._timer_lbl.setText("Device paired — telemetry uplink active")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        self._footer_lbl.setText("SECURE HANDSHAKE VERIFIED // LINK ESTABLISHED")
        self._footer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self) -> None:
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url = result[0]
                key = result[1]
                auto = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                localhost_url = result[4] if len(result) >= 5 else None
                self._manual_url = manual or url
                self._desktop_url = localhost_url or ""
                self._auto_login_url = auto
                self._current_key = key
                self._key_lbl.setText(key)
                self._render_links()
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"color: {C.ACC}; background: transparent;")
                self._key_frame.setStyleSheet(f"""
                    QFrame#keyChassis {{
                        background: {C.PANEL2};
                        border: 1px solid {C.BORDER_B};
                        border-radius: 4px;
                    }}
                """)
                self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
                self._footer_lbl.setText("UPLINK ARMED // WAITING FOR HANDSHAKE")
                self._footer_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                self._ctimer.start(1000)
                self._tick()

    def _open_in_browser(self) -> None:
        target = self._desktop_url or self._auto_login_url or self._manual_url
        if target:
            try:
                import webbrowser
                webbrowser.open(target)
            except Exception:
                pass

    def _do_close(self) -> None:
        self._ctimer.stop()
        for tmr in self._copy_flash_timers.values():
            tmr.stop()
        self._copy_flash_timers.clear()
        self.hide()
        self.closed.emit()


class ReactiveMicButton(QPushButton):
    """Acoustic control with a cheap listening-level outline."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._react_level = 0.0
        self._react_active = False

    def set_reactivity(self, level: float, active: bool) -> None:
        level = max(0.0, min(1.0, float(level)))
        active = bool(active)
        if active != self._react_active or abs(level - self._react_level) >= 0.025:
            self._react_level = level
            self._react_active = active
            self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._react_active or self._react_level <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = qcol(C.GREEN)
        glow.setAlpha(int(45 + self._react_level * 145))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(glow, 1.0 + self._react_level * 1.5))
        inset = 2.0 + (1.0 - self._react_level) * 1.5
        p.drawRoundedRect(
            QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2),
            2.0,
            2.0,
        )
        p.end()


class MainWindow(QMainWindow):
    _log_sig        = pyqtSignal(str)
    _state_sig      = pyqtSignal(str)
    _sentry_snapshot_sig = pyqtSignal(object)
    _content_sig    = pyqtSignal(str, str)   # (title, text) — thread-safe content display
    _reconfig_sig   = pyqtSignal()           # trigger setup overlay from any thread
    _camera_sig     = pyqtSignal(bytes)      # show camera frame preview (small overlay)
    _cam_stream_sig = pyqtSignal(bool)       # True=start live stream, False=stop
    _cam_frame_sig  = pyqtSignal(bytes)      # live camera frame → HUD area
    _clipboard_sig  = pyqtSignal(str)        # clipboard text changed (thread-safe)
    _confirm_sig    = pyqtSignal(str, str)   # (title, detail) — irreversible-action gate
    _confirm_hide_sig = pyqtSignal()
    _wake_dl_sig    = pyqtSignal(bool, str)  # wake-word install finished (ok, message)
    _quiz_sig       = pyqtSignal(str, object, object)  # (topic, questions, grader)
    _quiz_hide_sig  = pyqtSignal()
    _review_sig     = pyqtSignal(str, str, object, object)  # document review payload
    _intel_note_sig = pyqtSignal(str, str, str)  # (title, content, note_type)
    _clear_log_sig  = pyqtSignal()
    _screen_monitor_sig = pyqtSignal(bool, str)  # active, status label
    _spotify_playback_sig = pyqtSignal(str, str, str, bool)
    _spotify_state_sig = pyqtSignal(bool)
    _audio_status_sig = pyqtSignal(str)
    _hud_video_show_sig = pyqtSignal()   # thread-safe: show video surface
    _hud_video_hide_sig = pyqtSignal()   # thread-safe: restore avatar
    _scheduler_event_sig = pyqtSignal(object)  # task engine event from scheduler thread

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path
        self.on_clear_chat     = None
        self.on_screen_monitor_toggle = None  # callable: (enabled: bool) -> status

        # Load customization from config
        _cfg = _read_full_config()
        self._assistant_name: str = (_cfg.get("assistant_name") or "Alfred").strip()
        _display = self._assistant_name.upper()

        # Apply the saved UI colour BEFORE panels/stylesheets are built
        _ui_color = (_cfg.get("ui_color") or "").strip()
        apply_ui_accent(_ui_color or DEFAULT_UI_COLOR)

        from core.ui.themes import ThemeChrome
        self.setWindowTitle(f"{_display} — {APP_VERSION} // {ThemeChrome.chrome().window_title_suffix}")
        ThemeChrome.add_listener(self._on_theme_chrome_updated)
        self._current_icon_path = None
        self._log = None
        saved_icon = _cfg.get("app_icon", "")
        if saved_icon and Path(saved_icon).exists():
            self.set_app_icon(saved_icon, notify=False)
        else:
            avail = get_available_app_icons()
            if avail:
                self.set_app_icon(avail[0]["path"], notify=False)
            else:
                _cfg_dir = Path(__file__).resolve().parent / "config"
                for _ico_name in ("alfred.ico", "alfred.png", "jarvis.ico", "jarvis.png", "logo.png"):
                    _ico_file = _cfg_dir / _ico_name
                    if _ico_file.exists():
                        self.setWindowIcon(QIcon(str(_ico_file)))
                        break

        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command   = None
        self.on_remote_clicked = None   # callable: () -> (url, key) | None
        self.on_interrupt      = None   # callable: () -> None — stop ALFRED mid-speech
        self.on_voice_change   = None   # callable: () -> None — rebuild session with new voice
        self.on_audio_device_change = None  # callable: () -> None — reopen audio streams
        self._confirm_overlay  = None   # live ConfirmBanner, if one is on screen
        self.get_plugins       = None   # callable: () -> list[dict], set by JarvisLive
        self.get_plugin_settings = None # callable: () -> list[dict] settings schemas, set by JarvisLive
        self.on_wake_toggle    = None   # callable: (enable: bool) -> str, set by JarvisLive
        self.on_wake_manual    = None   # callable: () -> None — manual sleep/wake
        self.on_push_to_talk   = None   # callable: (enable: bool) -> str scope
        self.ptt_hold          = None   # callable: (held: bool) -> None — windowed chord
        self.wake_get_state    = None   # callable: () -> dict {enabled, awake, ready}
        self._muted            = False
        self._current_file: str | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._customize_overlay: CustomizeOverlay | None = None
        self._capabilities_overlay: CapabilitiesOverlay | None = None

        central = QWidget()
        central.setStyleSheet(f"""
            QWidget {{
                background: {C.BG};
            }}
            QToolTip {{
                background-color: {C.PANEL_BG};
                color: {C.PRI};
                border: 1px solid {C.BORDER_A};
                border-radius: 4px;
                padding: 5px 9px;
                font-family: 'JetBrains Mono', 'Cascadia Mono', 'Consolas', monospace;
                font-size: 11px;
            }}
        """)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Background score player (10% default, ducks to 5% when Alfred speaks)
        self._bg_music = TronScoreBackgroundPlayer(self)
        self._image_deck = None  # Lazily instantiated on first request via get_image_viewer()
        self._task_board = None

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        # Center column: HUD + resizable content panel via QSplitter
        self.hud = HudCanvas(face_path, _display)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_panel = self._build_content_panel()
        self._quiz_panel = self._build_quiz_panel()

        # Live camera container — replaces HUD when camera stream is active
        _cam_cont = QWidget()
        _cam_cont.setStyleSheet("background: #000308;")
        _cam_v = QVBoxLayout(_cam_cont)
        _cam_v.setContentsMargins(0, 0, 0, 0)
        _cam_v.setSpacing(0)
        _cam_hdr = QHBoxLayout()
        _cam_hdr.setContentsMargins(10, 6, 10, 6)
        _cam_title = QLabel("◈  OPTICAL RECON FEED // LIVE")
        _cam_title.setFont(tech_font(8, QFont.Weight.Bold, 60))
        _cam_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _cam_hdr.addWidget(_cam_title)
        _cam_hdr.addStretch()
        _cam_x = QPushButton("✕  CLOSE")
        _cam_x.setFont(tech_font(8, QFont.Weight.Bold))
        _cam_x.setCursor(Qt.CursorShape.PointingHandCursor)
        _cam_x.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent;
                border: none; padding: 2px 8px;
            }}
            QPushButton:hover {{ color: {C.PRI}; }}
        """)
        _cam_x.clicked.connect(self.stop_camera_stream)
        _cam_hdr.addWidget(_cam_x)
        _cam_v.addLayout(_cam_hdr)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _cam_v.addWidget(self._cam_live_lbl, stretch=1)

        # Stack: 0 = animated HUD, 1 = live camera, 2 = HUD video surface
        self._hud_cam_stack = QStackedWidget()
        self._hud_cam_stack.addWidget(self.hud)
        self._hud_cam_stack.addWidget(_cam_cont)

        # HUD video surface (slot 2) — built only when Qt Multimedia is available
        self._hud_video_surface = None
        self._hud_video_controller = None
        if _HAS_QT_MULTIMEDIA:
            self._init_hud_video()

        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background: {C.PRI_DIM};
            }}
        """)
        self._center_split.addWidget(self._hud_cam_stack)
        self._center_split.addWidget(self._content_panel)
        self._center_split.addWidget(self._quiz_panel)
        self._center_split.setStretchFactor(0, 3)
        self._center_split.setStretchFactor(1, 1)
        self._center_split.setCollapsible(0, False)
        body.addWidget(self._center_split, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)
        self.hud.on_visual_level = self._mute_btn.set_reactivity

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        # Quick-access drawer (floating overlay, built after central widget layout is done)
        self._quick_drawer = self._build_quick_drawer()
        self._update_autostart_btn(self._check_autostart())
        from memory.config_manager import get_brief_enabled as _gbe
        self._update_brief_btn(_gbe())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metric update timer
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._hud_overlay = MinimizedHudOverlay(
            self, self._log_sig, self._assistant_name
        )
        self._focus_card = FloatingFocusCard()
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)
        self._confirm_sig.connect(self._show_confirm_banner)
        self._confirm_hide_sig.connect(self._hide_confirm_banner)
        self._cam_stream_sig.connect(self._on_cam_stream)
        self._cam_frame_sig.connect(self._on_cam_frame)
        self._clipboard_sig.connect(self._show_clipboard_panel)
        self._wake_dl_sig.connect(self._on_wake_install_done)
        self._quiz_sig.connect(self._show_quiz)
        self._quiz_hide_sig.connect(self._hide_quiz)
        self._review_sig.connect(self._show_review)
        self._intel_note_sig.connect(self._on_intel_note_received, Qt.ConnectionType.QueuedConnection)
        self._clear_log_sig.connect(self._on_clear_chat)
        self._screen_monitor_sig.connect(self._apply_screen_monitor_state)
        self._sentry_snapshot_sig.connect(self._apply_sentry_snapshot)
        self._spotify_playback_sig.connect(self.set_spotify_playback)
        self._spotify_state_sig.connect(self.set_spotify_playback_state)
        self._audio_status_sig.connect(self._apply_audio_status)
        self._hud_video_show_sig.connect(self._on_hud_video_show)
        self._hud_video_hide_sig.connect(self._on_hud_video_hide)
        self._scheduler_event_sig.connect(self._on_scheduler_event)
        self._cam_stop = threading.Event()

        # Camera preview overlay (child of central widget, positioned in resizeEvent)
        self._cam_preview = _CameraPreview(self.centralWidget())

        # Clipboard panel (child of central widget, bottom-center)
        self._clipboard_panel = ClipboardPanel(self.centralWidget())
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()
        else:
            QTimer.singleShot(2500, self._prewarm_settings_overlays)
        QTimer.singleShot(0, self._start_animations)

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_intr = QShortcut(QKeySequence("Escape"), self)
        sc_intr.activated.connect(self._do_interrupt)

        # Background score player initialized earlier before left panel for UI docking

    def _show_camera_frame(self, img_bytes: bytes):
        """Slot — display camera preview overlay (main thread)."""
        self._cam_preview.show_frame(img_bytes)
        cw = self.centralWidget()
        pw = _CameraPreview._W
        ph = self._cam_preview.height()
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )

    # --- Live camera stream in HUD area ------------------------------------
    def _on_cam_stream(self, start: bool) -> None:
        if start:
            self._hud_cam_stack.setCurrentIndex(1)
        else:
            self._hud_cam_stack.setCurrentIndex(0)
            self._cam_live_lbl.clear()

    def _on_cam_frame(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self._cam_live_lbl.width(), self._cam_live_lbl.height()
            if w > 1 and h > 1:
                self._cam_live_lbl.setPixmap(
                    px.scaled(w, h,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
                )

    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._cam_stream_sig.emit(True)
        t = threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream")
        t.start()

    def _cam_loop(self) -> None:
        try:
            import cv2
            # Reuse camera index detected by screen_processor (cached in api_keys.json)
            cam_idx = 0
            try:
                import json as _j
                cfg = _j.loads((CONFIG_DIR / "api_keys.json").read_text())
                cam_idx = int(cfg.get("camera_index", 0))
            except Exception:
                pass
            try:
                backend = cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY
            except AttributeError:
                backend = 0
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            # warm-up frames
            for _ in range(5):
                cap.read()
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            print(f"[Camera] Stream error: {e}")
        finally:
            self._cam_stream_sig.emit(False)

    def stop_camera_stream(self) -> None:
        self._cam_stop.set()

    # ------------------------------------------------------------------
    # HUD Video Surface — integration
    # ------------------------------------------------------------------

    def _init_hud_video(self) -> None:
        """Build HudVideoSurface + HudVideoController and add to stack."""
        try:
            from core.hud_video.surface import HudVideoSurface
            from core.hud_video.controller import HudVideoController
            from core.hud_video.backends.local_url import LocalUrlBackend

            ctrl = HudVideoController(self)
            surf = HudVideoSurface(ctrl, self)
            backend = LocalUrlBackend(surf.video_widget(), ctrl)

            # Wire controller -> backend -> surface
            ctrl.wire(
                on_show_surface=lambda: self._hud_video_show_sig.emit(),
                on_hide_surface=lambda: self._hud_video_hide_sig.emit(),
                on_backend_play=lambda ref, muted: (
                    backend.load(ref) or backend.set_muted(muted)
                ),
                on_backend_pause=backend.pause,
                on_backend_resume=backend.play,
                on_backend_stop=backend.stop,
                on_backend_set_muted=backend.set_muted,
                on_backend_set_volume=backend.set_volume,
                on_backend_seek=backend.seek,
            )

            # Backend signals -> controller
            backend.on_ready.connect(ctrl.on_backend_ready)
            backend.on_error.connect(lambda msg: ctrl.on_backend_error(msg[:60]))
            backend.on_ended.connect(ctrl.on_backend_ended)
            backend.on_position_changed.connect(ctrl.on_backend_position)
            backend.on_duration_changed.connect(ctrl.on_backend_duration)
            backend.on_seekable_changed.connect(ctrl.on_backend_seekable)

            # Surface close button -> stop
            surf.stop_requested.connect(ctrl.stop)

            # Duck background music when video unmuted
            ctrl.state_changed.connect(self._on_hud_video_state_changed)

            self._hud_video_surface = surf
            self._hud_video_controller = ctrl
            self._hud_video_backend = backend
            self._hud_cam_stack.addWidget(surf)   # slot 2

            # Register in process-wide registry so action handlers can reach
            # the controller regardless of __main__ vs 'main' module identity.
            from core.registry import register as _reg_register
            _reg_register("hud_video_controller", ctrl)

            try:
                from core.logger import _tlog
                _tlog("HUD", "info", "video controller registered", None)
            except Exception:
                print("[HUD] video controller registered")

        except Exception as exc:
            import traceback, sys
            print(f"[HudVideo] init failed: {exc}", file=sys.stderr, flush=True)
            traceback.print_exc()


    def _on_hud_video_show(self) -> None:
        """Switch stack to video surface slot (Qt thread)."""
        self._hud_cam_stack.setCurrentIndex(2)

    def _on_hud_video_hide(self) -> None:
        """Return stack to HudCanvas slot (Qt thread)."""
        self._hud_cam_stack.setCurrentIndex(0)

    def _on_hud_video_state_changed(self, state) -> None:
        """Duck / unduck background music based on video mute state."""
        from core.hud_video.controller import VideoState
        if state == VideoState.PLAYING:
            # Video is playing — do not duck unless user unmuted
            # Ducking is handled separately in set_muted.
            pass
        elif state == VideoState.IDLE:
            # Ensure background music is unducked when video ends
            if hasattr(self, "_bg_music"):
                self._bg_music.set_ducked(False)


    # ------------------------------------------------------------------
    # Icon generation — arc-reactor style, rendered with Pillow
    # ------------------------------------------------------------------
    @staticmethod
    def _build_jarvis_icon(out_path: Path) -> bool:
        """
        Render an ALFRED tactical icon at 4× resolution and downsample
        for crisp results at all sizes. Saves a multi-res .ico to out_path.
        Returns True on success.
        """
        try:
            import math
            import PIL.Image
            import PIL.ImageDraw
            import PIL.ImageFilter
        except ImportError:
            return False

        CYAN   = (0, 212, 255)
        DIM    = (0, 100, 140)
        DARK   = (0, 6, 10)
        GLOW   = (0, 160, 200)
        WHITE  = (220, 240, 255)

        def _render(sz: int) -> PIL.Image.Image:
            S  = sz * 4                     # draw at 4× then downscale
            img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d   = PIL.ImageDraw.Draw(img)
            cx = cy = S // 2

            # ── filled background circle ──────────────────────────────────
            R = S // 2 - 2
            d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=(*DARK, 255))

            # ── outer border ring ─────────────────────────────────────────
            lw = max(2, S // 40)
            d.ellipse([cx-R, cy-R, cx+R, cy+R],
                      outline=(*CYAN, 220), width=lw)

            # ── mid decorative ring ───────────────────────────────────────
            R2 = int(R * 0.72)
            d.ellipse([cx-R2, cy-R2, cx+R2, cy+R2],
                      outline=(*DIM, 180), width=max(1, lw // 2))

            # ── 6 radial spokes (hex bolt) ────────────────────────────────
            R_inner = int(R * 0.30)
            R_outer = int(R * 0.62)
            spoke_w = max(1, S // 80)
            for i in range(6):
                angle = math.radians(i * 60 - 30)
                x1 = cx + int(R_inner * math.cos(angle))
                y1 = cy + int(R_inner * math.sin(angle))
                x2 = cx + int(R_outer * math.cos(angle))
                y2 = cy + int(R_outer * math.sin(angle))
                d.line([x1, y1, x2, y2], fill=(*GLOW, 200), width=spoke_w)

            # ── 6 tick marks on outer ring ────────────────────────────────
            for i in range(6):
                angle = math.radians(i * 60)
                for dr in range(lw * 2):
                    rx = (R - lw - dr)
                    d.point(
                        [cx + int(rx * math.cos(angle)),
                         cy + int(rx * math.sin(angle))],
                        fill=(*WHITE, 220),
                    )

            # ── inner glowing ring ────────────────────────────────────────
            Ri = int(R * 0.26)
            d.ellipse([cx-Ri, cy-Ri, cx+Ri, cy+Ri],
                      outline=(*CYAN, 255), width=max(2, lw))

            # ── bright glow soft blur applied before core ─────────────────
            # (draw a slightly larger cyan circle on a separate layer)
            glow_layer = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            gd = PIL.ImageDraw.Draw(glow_layer)
            Rc = int(R * 0.13)
            gd.ellipse([cx-Rc*2, cy-Rc*2, cx+Rc*2, cy+Rc*2],
                       fill=(*CYAN, 110))
            glow_layer = glow_layer.filter(PIL.ImageFilter.GaussianBlur(S // 14))
            img = PIL.Image.alpha_composite(img, glow_layer)
            d   = PIL.ImageDraw.Draw(img)

            # ── core dot ──────────────────────────────────────────────────
            d.ellipse([cx-Rc, cy-Rc, cx+Rc, cy+Rc], fill=(*WHITE, 255))

            # ── downscale to target size ──────────────────────────────────
            return img.resize((sz, sz), PIL.Image.LANCZOS)

        try:
            sizes  = [256, 128, 64, 48, 32, 16]
            frames = [_render(s) for s in sizes]
            frames[0].save(
                out_path,
                format="ICO",
                append_images=frames[1:],
                sizes=[(s, s) for s in sizes],
            )
            return True
        except Exception as e:
            print(f"[Shortcut] ⚠️  Icon generation failed: {e}")
            return False

    @staticmethod
    def _create_lnk_windows(lnk: str, target: str, args: str,
                             work_dir: str, icon_loc: str) -> None:
        """
        Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd.
        Tries win32com (pywin32) first; falls back to wscript.exe + VBScript.
        wscript.exe is a GUI-mode host — it never opens a console window.
        """
        # ── Option 1: pywin32 (pure Python COM, zero subprocess) ──────────
        try:
            from win32com.client import Dispatch   # type: ignore
            sh = Dispatch("WScript.Shell")
            sc = sh.CreateShortCut(lnk)
            sc.TargetPath       = target
            sc.Arguments        = f'"{args}"'
            sc.WorkingDirectory = work_dir
            sc.Description      = "J.A.R.V.I.S AI Assistant"
            sc.IconLocation     = icon_loc
            sc.save()
            return
        except ImportError:
            pass

        # ── Option 2: wscript.exe + VBScript (always available on Windows,
        #    GUI-mode executable — never opens a console window) ────────────
        vbs = "\n".join([
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work_dir}"',
            'sc.Description = "J.A.R.V.I.S AI Assistant"',
            f'sc.IconLocation = "{icon_loc}"',
            'sc.Save',
        ])
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(vbs)
            proc = subprocess.Popen(
                ["wscript.exe", "/nologo", tmp],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            proc.wait(timeout=10)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @staticmethod
    def _get_desktop_dir() -> Path:
        """
        Resolve the user's REAL desktop directory instead of assuming
        ~/Desktop, which breaks when:
          • OneDrive "Known Folder Move" relocates the desktop
            (C:/Users/x/OneDrive/Desktop) — very common on Win 10/11;
          • the XDG desktop is localized on Linux (~/Masaüstü,
            ~/Schreibtisch, ~/Bureau, …).
        Falls back to ~/Desktop only as a last resort.
        """
        home = Path.home()
        _os = platform.system()

        if _os == "Windows":
            # ── 1) SHGetKnownFolderPath(FOLDERID_Desktop) — the canonical
            #       answer; follows OneDrive redirection. No dependencies. ──
            try:
                import ctypes
                from ctypes import wintypes

                class _GUID(ctypes.Structure):
                    _fields_ = [("Data1", wintypes.DWORD),
                                ("Data2", wintypes.WORD),
                                ("Data3", wintypes.WORD),
                                ("Data4", ctypes.c_ubyte * 8)]

                # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
                fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                                 0x9A, 0x87, 0xC6, 0x41))
                buf = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(
                        ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    if p.is_dir():
                        return p
            except Exception:
                pass

            # ── 2) Registry: User Shell Folders (may contain %VARS%) ──────
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Explorer\User Shell Folders") as key:
                    val, _t = winreg.QueryValueEx(key, "Desktop")
                p = Path(os.path.expandvars(val))
                if p.is_dir():
                    return p
            except Exception:
                pass

        elif _os == "Linux":
            # ── xdg-user-dir honours localized names (~/Masaüstü, …) ──────
            try:
                out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                     capture_output=True, text=True, timeout=5)
                p = Path(out.stdout.strip())
                if out.stdout.strip() and p != home and p.is_dir():
                    return p
            except Exception:
                pass
            try:
                cfg = home / ".config" / "user-dirs.dirs"
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p != home and p.is_dir():
                            return p
            except Exception:
                pass

        # macOS: ~/Desktop is always the real path (localization is
        # display-only). Everything else lands here as a last resort.
        return home / "Desktop"

    def _create_desktop_shortcut(self):
        """
        Create a desktop shortcut on Windows / macOS / Linux.
        Never opens a terminal, console, or PowerShell window on any platform.
        """
        import stat as _stat
        script  = Path(__file__).resolve().parent / "main.py"
        python  = Path(sys.executable)
        desktop = self._get_desktop_dir()

        # Arc-reactor icon (.ico — also exported as .png for Linux/macOS)
        ico_path = Path(__file__).resolve().parent / "config" / "jarvis.ico"
        if not ico_path.exists():
            self._build_jarvis_icon(ico_path)

        try:
            _os = platform.system()

            # ── Windows ───────────────────────────────────────────────────────
            if _os == "Windows":
                pythonw  = python.parent / "pythonw.exe"
                target   = str(pythonw if pythonw.exists() else python)
                lnk      = str(desktop / "A.L.F.R.E.D.lnk")
                icon_loc = str(ico_path) if ico_path.exists() else f"{target},0"
                self._create_lnk_windows(lnk, target, str(script),
                                         str(script.parent), icon_loc)

            # ── macOS — proper .app bundle (no Terminal window) ───────────────
            elif _os == "Darwin":
                app     = desktop / "A.L.F.R.E.D.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)

                # Launcher executable (bash — runs as background process,
                # macOS does NOT open Terminal for executables inside .app bundles)
                launcher = mac_dir / "ALFRED"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n'
                )
                launcher.chmod(launcher.stat().st_mode
                               | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)

                # Minimal Info.plist (required for .app recognition)
                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>CFBundleExecutable</key><string>ALFRED</string>\n'
                    '  <key>CFBundleIdentifier</key>'
                    '<string>com.alfred.assistant</string>\n'
                    '  <key>CFBundleName</key><string>A.L.F.R.E.D</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n'
                )

                # Optional: copy icon as .icns (skip silently if Pillow is missing)
                try:
                    import PIL.Image
                    icns = res_dir / "AppIcon.icns"
                    PIL.Image.open(ico_path).save(icns, format="ICNS")
                    # Inject icon reference into plist
                    plist = app / "Contents" / "Info.plist"
                    txt = plist.read_text()
                    plist.write_text(
                        txt.replace(
                            '</dict></plist>',
                            '  <key>CFBundleIconFile</key>'
                            '<string>AppIcon</string>\n</dict></plist>\n',
                        )
                    )
                except Exception:
                    pass  # icon is optional

            # ── Linux — .desktop file (Terminal=false, no console) ────────────
            else:
                # Export .ico → .png for better desktop integration
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize(
                            (256, 256), PIL.Image.LANCZOS
                        ).save(png_path, format="PNG")
                    except Exception:
                        png_path = ico_path  # fallback to .ico

                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / "J.A.R.V.I.S.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    "Name=J.A.R.V.I.S\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                    + icon_line
                )
                desk.chmod(desk.stat().st_mode | 0o755)

            self._log.append_log("SYS: Desktop shortcut created.")
        except Exception as e:
            self._log.append_log(f"ERR: Shortcut failed — {e}")

    def pause_audio_core(self):
        """Pause background score player."""
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.pause_core()

    def resume_audio_core(self):
        """Resume background score player."""
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.resume_core()

    def set_audio_core_volume(self, vol: int):
        """Set volume percentage 0-100 on background score."""
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.set_base_volume(vol / 100.0)

    def get_audio_core_status(self) -> dict:
        """Query current state of background audio player."""
        if not hasattr(self, "_bg_music") or not self._bg_music:
            return {"is_playing": False, "volume": 0, "track": ""}
        return {
            "is_playing": self._bg_music.is_playing(),
            "volume": int(self._bg_music.base_volume() * 100),
            "track": self._bg_music.current_track_name(),
        }

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        TacticalHoverHelpManager.instance().dismiss()
        super().resizeEvent(event)
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._remote_overlay and self._remote_overlay.isVisible():
            ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
            self._remote_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._customize_overlay and self._customize_overlay.isVisible():
            ow = min(CustomizeOverlay._OW, cw.width() - 24)
            oh = min(CustomizeOverlay._OH, cw.height() - 24)
            self._customize_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._capabilities_overlay and self._capabilities_overlay.isVisible():
            ow, oh = CapabilitiesOverlay._OW, CapabilitiesOverlay._OH
            oh = min(oh, cw.height() - 20)
            ow = min(ow, cw.width() - 20)
            self._capabilities_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        # Camera preview — bottom-right corner of the center/HUD area
        pw = _CameraPreview._W
        ph = self._cam_preview.height() or _CameraPreview._H
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )
        # Clipboard panel — bottom-center
        if hasattr(self, '_clipboard_panel') and self._clipboard_panel.isVisible():
            self._position_clipboard_panel()
        # Quick drawer — reposition if open
        if hasattr(self, '_quick_drawer') and self._quick_drawer.isVisible():
            self._position_quick_drawer()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, '_quick_drawer') and self._quick_drawer.isVisible():
            self._position_quick_drawer()

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        if hasattr(self, "_uptime_lbl"):
            self._uptime_lbl.setText(f"UP  {snap.get('uptime', '--:--')}")

        if hasattr(self, "_proc_lbl"):
            self._proc_lbl.setText(f"PROC  {snap.get('proc', '--')}")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(56)
        w.setStyleSheet(f"""
            QWidget {{
                background: {C.PANEL};
                border-bottom: 1px solid {C.BORDER_A};
            }}
        """)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 0, 14, 0)

        self._drawer_btn = QPushButton("[ ⚙ ]  TACTICAL CONTROLS")
        self._drawer_btn.setFixedHeight(30)
        self._drawer_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.6))
        self._drawer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drawer_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(142, 155, 255, 0.14);
                color: #ffffff;
                border: 1px solid {C.PRI};
            }}
            QPushButton:checked {{
                color: {C.DARK};
                border: 1px solid {C.PRI};
                background: {C.PRI};
            }}
        """)
        self._drawer_btn.setCheckable(True)
        self._drawer_btn.clicked.connect(self._toggle_drawer)
        attach_hover_help(self._drawer_btn, "Toggle the tactical controls panel for quick access to system settings and tools.")
        lay.addWidget(self._drawer_btn)

        self._directives_btn = QPushButton("[ ▤ ]  DIRECTIVES ARCHIVE")
        self._directives_btn.setFixedHeight(30)
        self._directives_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.6))
        self._directives_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._directives_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(142, 155, 255, 0.14);
                color: #ffffff;
                border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: rgba(142, 155, 255, 0.25);
            }}
        """)
        self._directives_btn.clicked.connect(self._open_directives)
        attach_hover_help(self._directives_btn, "Open the full directory of operational skills, directives, and capabilities.")
        lay.addWidget(self._directives_btn)

        # Sentry Monitoring Toggle Button
        self._sentry_btn = QPushButton("[ ▣ ]  SENTRY MODE")
        self._sentry_btn.setFixedHeight(30)
        self._sentry_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.6))
        self._sentry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sentry_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(142, 155, 255, 0.14);
                color: #ffffff;
                border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: rgba(142, 155, 255, 0.25);
            }}
            QPushButton:checked {{
                color: {C.DARK};
                border: 1px solid {C.PRI};
                background: {C.PRI};
            }}
        """)
        self._sentry_btn.setCheckable(True)
        self._sentry_btn.clicked.connect(self._toggle_sentry_mode)
        attach_hover_help(self._sentry_btn, "Toggle continuous visual monitoring and active task focus tracking.")
        lay.addWidget(self._sentry_btn)

        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(2)
        _disp = self._assistant_name.upper()

        top_title_row = QHBoxLayout()
        top_title_row.setSpacing(8)
        top_title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._header_icon_lbl = QLabel()
        self._header_icon_lbl.setFixedSize(22, 22)
        self._header_icon_lbl.setStyleSheet("background: transparent;")
        if getattr(self, "_current_icon_path", None) and Path(self._current_icon_path).exists():
            pm = _scaled_icon_pixmap(self._current_icon_path, 22, 22)
            if not pm.isNull():
                self._header_icon_lbl.setPixmap(pm)
        top_title_row.addWidget(self._header_icon_lbl)

        self._title_lbl = QLabel(f"┌  {_disp} // {APP_VERSION}  ┐")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(mono_font(12, QFont.Weight.Bold, letter_spacing=2.5))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        top_title_row.addWidget(self._title_lbl)

        mid.addLayout(top_title_row)

        from core.ui.themes import ThemeChrome
        self._sub_lbl = QLabel(ThemeChrome.identity().affiliation_line)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(mono_font(7, QFont.Weight.Medium, letter_spacing=1.6))
        self._sub_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(mono_font(12, QFont.Weight.Bold, letter_spacing=1.0))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(mono_font(7, QFont.Weight.Normal, letter_spacing=0.5))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        container.setFixedWidth(_LEFT_W)
        container.setStyleSheet(f"""
            QWidget {{
                background: {C.PANEL};
                border-right: 1px solid {C.BORDER_A};
            }}
        """)
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(0, 0, 0, 0)
        container_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {C.PANEL};
                width: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                min-height: 20px;
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # 1. Optical Recon Scanner Widget (Screenshot 1 top-left)
        self._recon_widget = CRTReconWidget()
        lay.addWidget(self._recon_widget)

        # 2. Biometric Fingerprint Scanner Widget (Screenshot 1 middle-left)
        self._bio_widget = BiometricFingerprintWidget()
        lay.addWidget(self._bio_widget)

        # 3. Telemetry Pose Humanoid Widget (Screenshot 1 lower-left)
        self._pose_widget = WireframePoseWidget()
        lay.addWidget(self._pose_widget)

        # Developer / Power-User 2x2 Data Grid (GIT, PORTS, TOP PROC, SESSION)
        from core.hud.datagrid import DeveloperDataGridWidget
        self._data_grid = DeveloperDataGridWidget()
        lay.addWidget(self._data_grid)

        # 4. Metric Bars
        lay.addSpacing(2)
        from core.ui.themes import ThemeChrome
        self._hdr_telemetry = QLabel(ThemeChrome.chrome().telemetry_header)
        self._hdr_telemetry.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
        self._hdr_telemetry.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none; padding-left: 2px;")
        lay.addWidget(self._hdr_telemetry)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff5577")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net, self._bar_gpu, self._bar_tmp]:
            bar.setFixedHeight(34)
            lay.addWidget(bar)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(4, 2, 4, 2)
        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(mono_font(7, QFont.Weight.Normal, letter_spacing=0.8))
        self._uptime_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(mono_font(7, QFont.Weight.Normal, letter_spacing=0.8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        meta_row.addWidget(self._uptime_lbl)
        meta_row.addStretch()
        meta_row.addWidget(self._proc_lbl)
        lay.addLayout(meta_row)

        lay.addSpacing(4)

        # 5. Dedicated Cyber Audio Player Widget (Bottom-Left Deck)
        self._audio_player = TacticalAudioPlayerWidget(self._bg_music, parent=w)
        lay.addWidget(self._audio_player)

        scroll.setWidget(w)
        container_lay.addWidget(scroll)
        return container

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"""
            QWidget {{
                background: {C.PANEL};
                border-left: 1px solid {C.BORDER_A};
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        # 1. Subject Tactical Dossier Card (Screenshot 1 exact card!)
        self._dossier_card = SubjectDossierCard(self._assistant_name)
        lay.addWidget(self._dossier_card)

        # 2. Segmented tab header: Telemetry vs Dossier Notes
        from core.ui.themes import ThemeChrome
        tab_row = QHBoxLayout(); tab_row.setSpacing(6)
        self._tab_activity_btn = QPushButton(ThemeChrome.chrome().tab_telemetry)
        self._tab_activity_btn.setFixedHeight(28)
        self._tab_activity_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.8))
        self._tab_activity_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_activity_btn.setCheckable(True)
        self._tab_activity_btn.setChecked(True)

        self._tab_notes_btn = QPushButton(ThemeChrome.chrome().tab_intel)
        self._tab_notes_btn.setFixedHeight(28)
        self._tab_notes_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.8))
        self._tab_notes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_notes_btn.setCheckable(True)
        self._tab_notes_btn.setChecked(False)

        tab_row.addWidget(self._tab_activity_btn)
        tab_row.addWidget(self._tab_notes_btn)
        lay.addLayout(tab_row)

        attach_hover_help(self._tab_activity_btn, "Display live system telemetry, activity logs, and assistant messages.")
        attach_hover_help(self._tab_notes_btn, "View gathered intel entries, research notes, URLs, and code snippets.")

        self._tab_activity_btn.clicked.connect(lambda: self._switch_terminal_tab(0))
        self._tab_notes_btn.clicked.connect(lambda: self._switch_terminal_tab(1))

        self._terminal_stack = QStackedWidget()
        self._terminal_stack.setStyleSheet("background: transparent; border: none;")
        self._log = LogWidget()
        self._notes_terminal = NotesTerminalWidget()
        self._notes_terminal.note_added.connect(self._on_notes_count_updated)
        self._terminal_stack.addWidget(self._log)
        self._terminal_stack.addWidget(self._notes_terminal)

        # ── Cognitive-trace (thinking) toggle ──────────────────────────────────
        # Sits between the dossier card and the tab row so it is clearly
        # "above the chat" without eating space from the log itself.
        self._think_btn = QPushButton("[ ◈ ]  COGNITIVE TRACE : OFF")
        self._think_btn.setFixedHeight(24)
        self._think_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.6))
        self._think_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._think_btn.setCheckable(True)
        self._think_btn.setChecked(False)
        attach_hover_help(
            self._think_btn,
            "Show or hide the assistant's real-time internal reasoning trace and thoughts before answering."
        )
        self._style_think_btn(False)
        self._think_btn.toggled.connect(self._toggle_think)
        lay.addWidget(self._think_btn)

        lay.addWidget(self._terminal_stack, stretch=1)
        self._update_tab_button_styles(0)

        # 3. Forensic Data Ingestion
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        attach_hover_help(self._drop_zone, "Drop files or click to upload documents, images, code, and logs for immediate analysis.")
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("DROP EVIDENCE // SURVEILLANCE CAPTURES // TELEMETRY LOGS")
        self._file_hint.setFont(mono_font(6, letter_spacing=0.8))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; padding-left: 2px;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        # 4. Directive Input Row
        lay.addLayout(self._build_input_row())

        # 5. Emergency Purge Button
        self._interrupt_btn = QPushButton("[ ■ ]  ABORT ACTIVE DIRECTIVE  //  ESC")
        self._interrupt_btn.setFixedHeight(32)
        self._interrupt_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.2))
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_hover_help(self._interrupt_btn, "Immediately stop active speech synthesis, reasoning tasks, and ongoing directives.")
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 42, 85, 0.08);
                color: #ff5577;
                border: 1px solid rgba(255, 42, 85, 0.45);
                border-radius: 2px;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: #ff2a55;
                border: 1px solid #ff2a55;
                color: #05060a;
            }}
            QPushButton:pressed {{
                background: #cc1840;
                color: #ffffff;
            }}
        """)
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn)

        # 6. Mute Button
        self._mute_btn = ReactiveMicButton("BATCAVE SENSORS: ONLINE")
        self._mute_btn.setFixedHeight(32)
        self._mute_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.8))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setAccessibleName("Acoustic sensors")
        self._mute_btn.setAccessibleDescription(
            "Toggle microphone listening. The outline responds to input level while listening."
        )
        attach_hover_help(self._mute_btn, "Toggle microphone input on or off. Responds dynamically to audio volume.")
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        return w

    def _build_quick_drawer(self) -> QWidget:
        """Floating overlay panel shown when the ⚙ header button is toggled."""
        _BTN_STYLE_PRI = f"""
            QPushButton {{
                background: rgba(142, 155, 255, 0.12);
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                text-align: left; padding: 0 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
        """
        _BTN_STYLE_DIM = f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                text-align: left; padding: 0 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {C.PRI};
                background: rgba(142, 155, 255, 0.10);
            }}
            QPushButton:pressed {{
                background: rgba(142, 155, 255, 0.20);
            }}
        """

        w = QWidget(self)
        w.setObjectName("QuickDrawer")
        from core.hud_video.layering import make_frameless_overlay
        make_frameless_overlay(w, self)
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        w.setStyleSheet(f"""
            QWidget#QuickDrawer {{
                background-color: #040810;
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)

        hdr = QLabel("◈  BATCAVE TACTICAL SYSTEMS")
        hdr.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.5))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER_A}; padding-bottom: 6px;")
        lay.addWidget(hdr)

        remote_btn = QPushButton("[ ⟁ ]  SATELLITE COMMS // UPLINK")
        remote_btn.setFixedHeight(30)
        remote_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.5))
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setStyleSheet(_BTN_STYLE_PRI)
        remote_btn.clicked.connect(self._open_remote)
        attach_hover_help(remote_btn, "Pair with companion mobile device or browser to control ALFRED remotely over your local network.")
        lay.addWidget(remote_btn)

        fs_btn = QPushButton("[ ⛶ ]  TACTICAL HUD VIEW  [F11]")
        fs_btn.setFixedHeight(29)
        fs_btn.setFont(mono_font(8, letter_spacing=0.5))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(_BTN_STYLE_DIM)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        attach_hover_help(fs_btn, "Toggle full-screen tactical Batcomputer HUD view (or press F11).")
        lay.addWidget(fs_btn)

        sc_btn = QPushButton("[ ⊞ ]  DEPLOY BATCAVE CONSOLE")
        sc_btn.setFixedHeight(29)
        sc_btn.setFont(mono_font(8, letter_spacing=0.5))
        sc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sc_btn.setStyleSheet(_BTN_STYLE_DIM)
        sc_btn.clicked.connect(self._create_desktop_shortcut)
        attach_hover_help(sc_btn, "Create a quick-launch shortcut icon for ALFRED on your Windows desktop.")
        lay.addWidget(sc_btn)

        self._autostart_btn = QPushButton("[ ◈ ]  BATCOMPUTER AUTO-BOOT: OFF")
        self._autostart_btn.setFixedHeight(29)
        self._autostart_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._autostart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autostart_btn.clicked.connect(self._toggle_autostart)
        attach_hover_help(self._autostart_btn, "Automatically start ALFRED in the background whenever Windows boots up.")
        lay.addWidget(self._autostart_btn)

        cust_btn = QPushButton("[ ⚙ ]  RECONFIGURE BATCOMPUTER")
        cust_btn.setFixedHeight(29)
        cust_btn.setFont(mono_font(8, letter_spacing=0.5))
        cust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cust_btn.setStyleSheet(_BTN_STYLE_DIM)
        cust_btn.clicked.connect(self._open_customize)
        attach_hover_help(cust_btn, "Customize assistant name, commander designation, vocal synthesis, CRT theme, and app icon.")
        lay.addWidget(cust_btn)

        self._brief_btn = QPushButton()
        self._brief_btn.setFixedHeight(29)
        self._brief_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._brief_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._brief_btn.clicked.connect(self._toggle_brief)
        attach_hover_help(self._brief_btn, "Deliver an automated morning briefing with weather, unread emails, and schedule on startup.")
        lay.addWidget(self._brief_btn)

        # ── Wake word ──────────────────────────────────────────────────────────
        self._wake_btn = QPushButton()
        self._wake_btn.setFixedHeight(29)
        self._wake_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._wake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_btn.clicked.connect(self._toggle_wake_word)
        attach_hover_help(self._wake_btn, "Toggle continuous hands-free voice wake word detection for 'Alfred' and 'Jarvis'.")
        lay.addWidget(self._wake_btn)

        self._wake_sleep_btn = QPushButton()
        self._wake_sleep_btn.setFixedHeight(29)
        self._wake_sleep_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._wake_sleep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_sleep_btn.clicked.connect(self._tap_wake_manual)
        attach_hover_help(self._wake_sleep_btn, "Manually trigger listening mode or put speech recognition to sleep.")
        lay.addWidget(self._wake_sleep_btn)
        self._wake_btn.setText("[ ◈ ]  COWL VOICE SENSORS")
        self._wake_btn.setStyleSheet(_BTN_STYLE_DIM)
        self._wake_sleep_btn.hide()

        self._ptt_btn = QPushButton()
        self._ptt_btn.setFixedHeight(29)
        self._ptt_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._ptt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ptt_btn.clicked.connect(self._toggle_ptt)
        attach_hover_help(self._ptt_btn, "Hold hotkey to speak so the microphone only listens while the key combination is held down.")
        lay.addWidget(self._ptt_btn)

        self._refresh_talk_btns()

        audio_btn = QPushButton("[ ☊ ]  COWL ACOUSTIC ROUTING")
        audio_btn.setFixedHeight(29)
        audio_btn.setFont(mono_font(8, letter_spacing=0.5))
        audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_btn.setStyleSheet(_BTN_STYLE_DIM)
        audio_btn.clicked.connect(self._open_audio_devices)
        attach_hover_help(audio_btn, "Choose which microphone and speaker devices ALFRED uses for voice input and speech output.")
        lay.addWidget(audio_btn)

        mem_btn = QPushButton("[ ☵ ]  WAYNE SECURE ARCHIVES")
        mem_btn.setFixedHeight(29)
        mem_btn.setFont(mono_font(8, letter_spacing=0.5))
        mem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_btn.setStyleSheet(_BTN_STYLE_DIM)
        mem_btn.clicked.connect(self._open_memory_panel)
        attach_hover_help(mem_btn, "View and manage remembered facts, user habits, and long-term memory stored in the archives.")
        lay.addWidget(mem_btn)

        self._setup_api_btn = QPushButton("[ ◈ ]  SETUP API BACKENDS")
        self._setup_api_btn.setFixedHeight(29)
        self._setup_api_btn.setFont(mono_font(8, letter_spacing=0.5))
        self._setup_api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_api_btn.setStyleSheet(_BTN_STYLE_PRI)
        self._setup_api_btn.clicked.connect(self._open_api_setup)
        attach_hover_help(self._setup_api_btn, "Manage encrypted credentials and OAuth tokens for Google Workspace, Spotify, and Gmail.")
        lay.addWidget(self._setup_api_btn)
        self._refresh_setup_api_btn()

        w.adjustSize()
        return w

    def _toggle_drawer(self, checked: bool):
        TacticalHoverHelpManager.instance().dismiss()
        if checked:
            self._refresh_wake_btns()   # resolve wake state on open (lazy)
            self._position_quick_drawer()
            from core.hud_video.layering import raise_overlay
            raise_overlay(self._quick_drawer, self)
        else:
            self._quick_drawer.hide()

    def _position_quick_drawer(self):
        if not hasattr(self, '_quick_drawer'):
            return
        _W = 286
        self._quick_drawer.setFixedWidth(_W)
        self._quick_drawer.adjustSize()
        global_pos = self.mapToGlobal(QPoint(16, 56))
        self._quick_drawer.setGeometry(
            global_pos.x(),
            global_pos.y(),
            _W,
            self._quick_drawer.sizeHint().height(),
        )

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("INPUT DIRECTIVE // QUERY BATCOMPUTER...")
        self._input.setFont(mono_font(8, letter_spacing=0.6))
        self._input.setFixedHeight(34)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2};
                color: {C.WHITE};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
                background: rgba(0, 240, 255, 0.08);
            }}
        """)
        self._input.returnPressed.connect(self._send)
        attach_hover_help(self._input, "Type a text directive or question to submit to ALFRED directly.")
        row.addWidget(self._input)

        send = QPushButton("TRANSMIT ❯")
        send.setFixedHeight(34)
        send.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 240, 255, 0.12);
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                border: 1px solid {C.PRI};
                color: #040e19;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: #040e19;
            }}
        """)
        send.clicked.connect(self._send)
        attach_hover_help(send, "Transmit typed directive or query to the AI reasoning engine.")
        row.addWidget(send)

        self._clear_btn = QPushButton("✕ CLEAR")
        self._clear_btn.setFixedHeight(34)
        self._clear_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_hover_help(self._clear_btn, "Clear conversational chat history and reset terminal display.")
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 42, 85, 0.08);
                color: #ff5577;
                border: 1px solid rgba(255, 42, 85, 0.45);
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: #ff2a55;
                border: 1px solid #ff2a55;
                color: #05060a;
            }}
            QPushButton:pressed {{
                background: #cc1840;
                color: #ffffff;
            }}
        """)
        self._clear_btn.clicked.connect(self.clear_chat)
        row.addWidget(self._clear_btn)

        return row

    def _build_content_panel(self) -> QWidget:
        """
        Collapsible panel below the HUD — shows search results, news, briefings.
        Hidden by default; appears when show_content() is called.
        """
        w = QWidget()
        w.setObjectName("ContentPanel")
        w.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: rgba(4, 14, 25, 0.94);
                border-top: 1px solid rgba(0, 240, 255, 0.20);
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)

        # ── header row ───────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(8)

        dot = QLabel("◈")
        dot.setFont(tech_font(9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._content_title_lbl = QLabel("INTEL & BRIEFING")
        self._content_title_lbl.setFont(tech_font(8, QFont.Weight.Bold, letter_spacing=1.5))
        self._content_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent;"
        )
        hdr.addWidget(self._content_title_lbl)
        hdr.addStretch()

        self._content_ts_lbl = QLabel("")
        self._content_ts_lbl.setFont(mono_font(7))
        self._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._content_ts_lbl)

        dismiss = QPushButton("DISMISS  ✕")
        dismiss.setFont(tech_font(7, QFont.Weight.Bold))
        dismiss.setFixedHeight(22)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.04); color: {C.TEXT_DIM};
                border: 1px solid rgba(0, 240, 255, 0.15); border-radius: 6px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(0, 240, 255, 0.12); }}
        """)
        dismiss.clicked.connect(w.hide)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        # ── separator ─────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(0, 240, 255, 0.15);"); lay.addWidget(sep)

        # ── text display ──────────────────────────────────────────────────────
        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setFont(tech_font(9))
        self._content_display.setMinimumHeight(60)
        self._content_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_display.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(3, 12, 22, 0.88);
                color: {C.TEXT};
                border: 1px solid rgba(0, 240, 255, 0.15);
                border-radius: 8px;
                padding: 10px 12px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; border: none; margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 240, 255, 0.25); border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 240, 255, 0.60);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._content_display)

        return w

    def _show_content(self, title: str, text: str):
        """Slot — runs on Qt main thread. Updates and shows the content panel."""
        import time as _time
        # The panel opens below the head, so the head looks down at it. It is a
        # tiny thing that answers "did that land?" before you read a word.
        self.hud.glance(0.0, -0.85, hold=1.3)
        self._content_title_lbl.setText(title.upper()[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setPlainText(text)
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start
        )
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 220, 120), 220])

    # ── document review ──────────────────────────────────────────────────────
    # Rendered as rich text into the content panel that already exists, rather
    # than into a panel of its own. A review is read, not clicked, so QTextEdit
    # gives scrolling, selection and copy for nothing, and the HUD gains no
    # widget it has to lay out. Severity decides colour and order here because
    # that is presentation; the plugin supplies no styling and knows no palette,
    # which is also what lets a re-theme repaint a review correctly.

    # Severity is marked by a symbol and a colour, not by a word. The findings
    # themselves are in the user's language, and "[SERIOUS]" sitting inside a
    # Turkish sentence is the kind of seam this project tries not to have —
    # while translating the tag would mean a table per language, which is worse.
    # A shape carries it in every language, and shape plus colour still reads
    # for someone who cannot separate red from amber. What the marks mean
    # arrives the way everything else does: JARVIS says it out loud.
    _REVIEW_MARKS = {"serious": ("RED", "▲"), "caution": ("ACC2", "●"), "note": ("PRI_DIM", "·")}

    @staticmethod
    def _esc(s) -> str:
        return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))

    def _show_review(self, title: str, summary: str, findings, unclear):
        """Slot — Qt main thread. Lays a document review into the content panel."""
        e = self._esc
        parts = [f'<div style="color:{C.TEXT}; font-family:\'JetBrains Mono\', \'Fira Code\', \'SF Pro Display\', \'SF Pro Text\', \'-apple-system\', \'Segoe UI\', sans-serif; font-size:12px; line-height:1.6;">']

        if summary:
            parts.append(
                f'<div style="color:{C.WHITE}; border-left:3px solid {C.PRI};'
                f' padding-left:10px; margin-bottom:12px; font-weight:600;">{e(summary)}</div>')

        for f in (findings or []):
            key, mark = self._REVIEW_MARKS.get(f.get("severity"), ("PRI_DIM", "·"))
            colour = getattr(C, key)
            parts.append(f'<div style="margin-bottom:12px;">')
            parts.append(
                f'<span style="color:{colour}; font-weight:bold;">{mark}</span> '
                f'<span style="color:{C.WHITE}; font-weight:bold;">'
                f'{e(f.get("heading"))}</span>')
            if f.get("detail"):
                parts.append(f'<div style="margin-left:14px; margin-top:2px;">{e(f["detail"])}</div>')
            if f.get("quote"):
                parts.append(
                    f'<div style="margin-left:14px; margin-top:3px; color:{C.TEXT_DIM};'
                    f' border-left:1px solid {C.BORDER}; padding-left:8px;">'
                    f'&ldquo;{e(f["quote"])}&rdquo;</div>')
            if f.get("suggestion"):
                parts.append(
                    f'<div style="margin-left:12px; color:{C.PRI};">'
                    f'&rarr; {e(f["suggestion"])}</div>')
            parts.append('</div>')

        if unclear:
            parts.append(
                f'<div style="margin-top:6px; border-top:1px solid {C.BORDER};'
                f' padding-top:7px; color:{C.TEXT_MED};">'
                'The document does not settle:</div>')
            for u in unclear:
                parts.append(
                    f'<div style="margin-left:12px; color:{C.TEXT_MED};">'
                    f'&middot; {e(u)}</div>')
        parts.append('</div>')

        import time as _time
        self.hud.glance(0.0, -0.85, hold=1.3)
        # Left as written, not upper-cased. The other content-panel titles are
        # the app's own English labels, but this one is the document's name in
        # the user's language, and str.upper() applies English casing rules to
        # it: Turkish "Sözleşmesi" comes back "SÖZLEŞMESI", having lost the
        # dotted capital İ. Python has no locale-aware upper to reach for, and
        # imposing one language's rules on all of them is the bug, not the fix.
        self._content_title_lbl.setText((title or "Document")[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setHtml("".join(parts))
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start)
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 260, 120), 260, 0])

    # ── quiz panel ───────────────────────────────────────────────────────────
    # An interactive twin of the content panel. The plugin only ever hands over
    # questions; everything about asking, marking and reporting happens here,
    # and the finished result is pushed back into the conversation the same way
    # a dropped file is — as a message JARVIS reads and responds to. That keeps
    # the tool call short (it returns the moment the board is up) and leaves the
    # talking to the assistant, in the user's own language.

    def _quiz_btn(self, text: str, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setFont(tech_font(8, QFont.Weight.Bold if primary else QFont.Weight.Medium, 30))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(32)
        if primary:
            b.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 240, 255, 0.35), stop:1 rgba(0, 180, 255, 0.20));
                    color: #ffffff;
                    border: 1px solid {C.PRI}; border-radius: 8px;
                    padding: 4px 12px; text-align: left; font-weight: bold;
                }}
                QPushButton:hover {{ background: rgba(0, 240, 255, 0.50); border-color: #ffffff; color: #ffffff; }}
                QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: rgba(255, 255, 255, 0.1); background: rgba(255, 255, 255, 0.02); }}
            """)
        else:
            b.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.04); color: {C.TEXT};
                    border: 1px solid rgba(0, 240, 255, 0.14); border-radius: 8px;
                    padding: 4px 12px; text-align: left;
                }}
                QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(0, 240, 255, 0.12); }}
                QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: rgba(255, 255, 255, 0.06); }}
            """)
        return b

    def _build_quiz_panel(self) -> QWidget:
        w = QWidget()
        w.setObjectName("QuizPanel")
        w.setStyleSheet(f"""
            QWidget#QuizPanel {{
                background: rgba(4, 14, 25, 0.94);
                border-top: 1px solid rgba(0, 240, 255, 0.20);
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 9, 14, 10)
        lay.setSpacing(6)

        hdr = QHBoxLayout(); hdr.setSpacing(6)
        dot = QLabel("◈")
        dot.setFont(tech_font(9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._quiz_title_lbl = QLabel("TACTICAL EVALUATION")
        self._quiz_title_lbl.setFont(tech_font(8, QFont.Weight.Bold, 60))
        self._quiz_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(self._quiz_title_lbl)
        hdr.addStretch()

        self._quiz_count_lbl = QLabel("")
        self._quiz_count_lbl.setFont(mono_font(8))
        self._quiz_count_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._quiz_count_lbl)

        quit_btn = QPushButton("DISMISS  ✕")
        quit_btn.setFont(tech_font(7, QFont.Weight.Bold))
        quit_btn.setFixedHeight(20)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 0 6px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        quit_btn.clicked.connect(self._hide_quiz)
        hdr.addWidget(quit_btn)
        lay.addLayout(hdr)

        rule = QFrame(); rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {C.BORDER};")
        lay.addWidget(rule)

        self._quiz_q_lbl = QLabel("")
        self._quiz_q_lbl.setWordWrap(True)
        self._quiz_q_lbl.setFont(tech_font(10, QFont.Weight.Bold, 20))
        self._quiz_q_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._quiz_q_lbl)

        self._quiz_answers = QWidget()
        self._quiz_answers.setStyleSheet("background: transparent;")
        self._quiz_answers_lay = QVBoxLayout(self._quiz_answers)
        self._quiz_answers_lay.setContentsMargins(0, 2, 0, 0)
        self._quiz_answers_lay.setSpacing(4)
        lay.addWidget(self._quiz_answers)

        self._quiz_note_lbl = QLabel("")
        self._quiz_note_lbl.setWordWrap(True)
        self._quiz_note_lbl.setFont(tech_font(8))
        self._quiz_note_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._quiz_note_lbl.hide()
        lay.addWidget(self._quiz_note_lbl)

        foot = QHBoxLayout()
        foot.addStretch()
        self._quiz_next_btn = self._quiz_btn("NEXT  →", primary=True)
        self._quiz_next_btn.setFixedWidth(110)
        self._quiz_next_btn.clicked.connect(self._quiz_next)
        self._quiz_next_btn.hide()
        foot.addWidget(self._quiz_next_btn)
        lay.addLayout(foot)

        self._quiz = None
        return w

    def _show_quiz(self, topic: str, questions, grader=None):
        """Slot — Qt main thread. Puts a fresh quiz on the board."""
        if not questions:
            return
        self._quiz = {
            "topic": topic or "",
            "questions": list(questions),
            "grader": grader,
            "i": 0,
            "results": [],
            "answered": False,
        }
        self._quiz_title_lbl.setText((topic or "evaluation").upper()[:48])
        self.hud.glance(0.0, -0.85, hold=1.3)
        first_show = not self._quiz_panel.isVisible()
        self._quiz_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 250, 120), 0, 250])
        self._quiz_render()

    def _hide_quiz(self):
        self._quiz = None
        self._quiz_panel.hide()

    def _quiz_clear_answers(self):
        while self._quiz_answers_lay.count():
            item = self._quiz_answers_lay.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()

    def _quiz_render(self):
        q = self._quiz["questions"][self._quiz["i"]]
        n, total = self._quiz["i"] + 1, len(self._quiz["questions"])
        self._quiz_count_lbl.setText(f"{n} / {total}")
        self._quiz_q_lbl.setText(q.get("question", ""))
        self._quiz_note_lbl.hide()
        self._quiz_next_btn.hide()
        self._quiz["answered"] = False
        self._quiz_clear_answers()

        opts = q.get("options") or []
        if opts:
            for text in opts:
                b = self._quiz_btn("   " + text)
                b.clicked.connect(lambda _=False, t=text: self._quiz_submit(t))
                self._quiz_answers_lay.addWidget(b)
        else:
            row = QWidget(); row.setStyleSheet("background: transparent;")
            h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
            field = QLineEdit()
            field.setFont(tech_font(9))
            field.setPlaceholderText("your answer")
            field.setStyleSheet(f"""
                QLineEdit {{
                    background: {C.PANEL2}; color: {C.WHITE};
                    border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;
                }}
                QLineEdit:focus {{ border-color: {C.PRI}; }}
            """)
            send = self._quiz_btn("ANSWER", primary=True)
            send.setFixedWidth(90)
            field.returnPressed.connect(lambda: self._quiz_submit(field.text()))
            send.clicked.connect(lambda: self._quiz_submit(field.text()))
            h.addWidget(field, stretch=1)
            h.addWidget(send)
            self._quiz_answers_lay.addWidget(row)
            field.setFocus()

    def _quiz_submit(self, given: str):
        if self._quiz is None or self._quiz["answered"]:
            return
        self._quiz["answered"] = True
        q = self._quiz["questions"][self._quiz["i"]]
        grader = self._quiz.get("grader")
        verdict = None
        if callable(grader):
            try:
                verdict = grader(q, given)
            except Exception:
                verdict = None
        self._quiz["results"].append({
            "question": q.get("question", ""),
            "type": q.get("type", ""),
            "given": str(given or "").strip(),
            "answer": q.get("answer", ""),
            "correct": verdict,
        })

        for i in range(self._quiz_answers_lay.count()):
            wdg = self._quiz_answers_lay.itemAt(i).widget()
            if wdg is not None:
                wdg.setEnabled(False)

        if verdict is True:
            mark, colour = "✓  correct", C.GREEN
        elif verdict is False:
            mark, colour = "✕  " + str(q.get("answer", "")), C.RED
        else:
            # Open answers and near-miss gap-fills are JARVIS's to judge. Saying
            # so is honest; marking it wrong here would be a guess.
            mark, colour = "…  noted — I'll go over this one with you", C.ACC2
        note = q.get("note") or ""
        self._quiz_note_lbl.setText(mark + (("\n" + note) if note else ""))
        self._quiz_note_lbl.setStyleSheet(f"color: {colour}; background: transparent;")
        self._quiz_note_lbl.show()

        last = self._quiz["i"] >= len(self._quiz["questions"]) - 1
        self._quiz_next_btn.setText("FINISH  →" if last else "NEXT  →")
        self._quiz_next_btn.show()
        self._quiz_next_btn.setFocus()

    def _quiz_next(self):
        if self._quiz is None:
            return
        if self._quiz["i"] >= len(self._quiz["questions"]) - 1:
            self._quiz_finish()
        else:
            self._quiz["i"] += 1
            self._quiz_render()

    def _quiz_finish(self):
        if self._quiz is None:
            return
        topic = self._quiz["topic"]
        results = self._quiz["results"]
        right = sum(1 for r in results if r["correct"] is True)
        unsure = sum(1 for r in results if r["correct"] is None)
        total = len(results)
        self._quiz_panel.hide()
        self._quiz = None

        self._log.append_log(f"QUIZ: {topic or 'quiz'} — {right}/{total} correct")

        # Hand it back to JARVIS as a message, not as a tool return: the tool
        # call ended minutes ago. This is the same channel a dropped file uses.
        lines = [f"[QUIZ_DONE] topic={topic or 'general'} | "
                 f"auto-marked {right}/{total} correct"
                 + (f", {unsure} still need your marking" if unsure else "")]
        for i, r in enumerate(results, 1):
            state = ("correct" if r["correct"] is True
                     else "wrong" if r["correct"] is False else "NEEDS MARKING")
            lines.append(
                f"{i}. [{r['type']}] {r['question']} | they answered: "
                f"{r['given'] or '(blank)'} | expected: {r['answer']} | {state}")
        lines.append(
            "Mark every question flagged NEEDS MARKING yourself — accept an answer "
            "that means the same thing. Then tell them how they did in their own "
            "language: the score, what they got wrong and why, in a couple of "
            "sentences. Offer another round only if it fits. "
            "Remember something only if it would still matter next week — that they "
            "are working through a subject, or keep missing the same thing. A score "
            "from one session is not worth a memory, and a memory per quiz would "
            "bury the things that are.")
        msg = "\n".join(lines)
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(26)
        w.setStyleSheet(f"""
            background: {C.PANEL};
            border-top: 1px solid {C.BORDER_A};
        """)
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("CONTROL YOUR DATA · PROTECT YOUR PRIVACY · WAYNE TACTICAL OS"))
        lay.addStretch()
        self._audio_status_pill = _fl("AUDIO: INITIALISING...", C.ACC2)
        lay.addWidget(self._audio_status_pill)
        lay.addSpacing(16)
        lay.addWidget(_fl("⌨ [F4] MUTE  ·  [F11] FULLSCREEN  ·  [ESC] ABORT", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell {self._assistant_name} what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._log.append_log("SYS: Dashboard not running — remote unavailable.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log.append_log("SYS: Could not generate remote key.")
            return
        url    = result[0]
        key    = result[1]
        auto   = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        localhost_url = result[4] if len(result) >= 5 else None
        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw  = self.centralWidget()
        ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
        ov  = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual,
                               desktop_url=localhost_url, expiry_secs=600, parent=cw)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.closed.connect(lambda: setattr(self, '_remote_overlay', None))
        ov.show()
        self._remote_overlay = ov
        link = auto or localhost_url or manual or url
        self._log.append_log(f"SYS: Remote Uplink live — View: {link} (Key: {key})")

    # ── Auto-start ──────────────────────────────────────────────────────────────

    def _check_autostart(self) -> bool:
        """Returns True if auto-start is currently registered on this OS."""
        try:
            if _OS == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    try:
                        winreg.QueryValueEx(key, "ALFRED_AI")
                        return True
                    except FileNotFoundError:
                        winreg.QueryValueEx(key, "JARVIS_AI")
                        return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif _OS == "Darwin":
                return ((Path.home() / "Library" / "LaunchAgents"
                        / "com.alfred.assistant.plist").exists() or
                        (Path.home() / "Library" / "LaunchAgents"
                        / "com.jarvis.assistant.plist").exists())
            else:
                return ((Path.home() / ".config" / "autostart" / "alfred.desktop").exists() or
                        (Path.home() / ".config" / "autostart" / "jarvis.desktop").exists())
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                if currently_on:
                    try:
                        winreg.DeleteValue(reg, "ALFRED_AI")
                    except FileNotFoundError:
                        pass
                    try:
                        winreg.DeleteValue(reg, "JARVIS_AI")
                    except FileNotFoundError:
                        pass
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    exe = str(pythonw if pythonw.exists() else sys.executable)
                    winreg.SetValueEx(reg, "ALFRED_AI", 0, winreg.REG_SZ,
                                      f'"{exe}" "{script}"')
                    try:
                        winreg.DeleteValue(reg, "JARVIS_AI")
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(reg)
            elif _OS == "Darwin":
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.alfred.assistant.plist"
                legacy_plist = plist_dir / "com.jarvis.assistant.plist"
                legacy_plist.unlink(missing_ok=True)
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.alfred.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n'
                    )
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "alfred.desktop"
                legacy_desk = desk_dir / "jarvis.desktop"
                legacy_desk.unlink(missing_ok=True)
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            enabled = not currently_on
            self._update_autostart_btn(enabled)
            self._log.append_log(
                f"SYS: Auto-start {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._log.append_log(f"ERR: Auto-start failed — {e}")

    def _update_autostart_btn(self, enabled: bool):
        if not hasattr(self, '_autostart_btn'):
            return
        if enabled:
            self._autostart_btn.setText("[ ◈ ]  AUTO-START : ON")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(78, 242, 187, 0.08); color: {C.GREEN};
                    border: 1px solid rgba(78, 242, 187, 0.45); border-radius: 2px;
                    text-align: left; padding: 0 10px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {C.GREEN}; color: #05060a; border: 1px solid {C.GREEN}; }}
                QPushButton:pressed {{ background: {C.GREEN_D}; color: #ffffff; }}
            """)
        else:
            self._autostart_btn.setText("[ ⊘ ]  AUTO-START : OFF")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    text-align: left; padding: 0 10px; font-weight: 500;
                }}
                QPushButton:hover {{ color: #ffffff; border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                QPushButton:pressed {{ background: rgba(142, 155, 255, 0.20); }}
            """)

    def _toggle_brief(self):
        from memory.config_manager import get_brief_enabled, save_brief_enabled
        new_val = not get_brief_enabled()
        save_brief_enabled(new_val)
        self._update_brief_btn(new_val)

    # ── Wake word settings ───────────────────────────────────────────────────

    def _wake_state(self) -> dict:
        """Combined state for the two wake-word buttons. Readiness is a cheap,
        deterministic on-disk check now (see core.wake_word.is_ready), so there
        is nothing to cache — the button never flickers to a stale value."""
        if self.wake_get_state:
            try:
                s = self.wake_get_state()
                return {"ready": bool(s.get("ready")),
                        "enabled": bool(s.get("enabled")),
                        "awake": bool(s.get("awake"))}
            except Exception:
                pass
        # Before JarvisLive has wired its callback (drawer built at startup).
        ready, enabled = False, False
        try:
            from core.wake_word import is_ready
            from memory.config_manager import get_wake_word_enabled
            ready, enabled = is_ready(), get_wake_word_enabled()
        except Exception:
            pass
        return {"ready": ready, "enabled": enabled, "awake": True}

    def _refresh_wake_btns(self):
        if not hasattr(self, '_wake_btn'):
            return
        st = self._wake_state()
        _on = f"""
            QPushButton {{ background: rgba(78, 242, 187, 0.08); color: {C.GREEN};
                border: 1px solid rgba(78, 242, 187, 0.45); border-radius: 2px;
                text-align: left; padding: 0 10px; font-weight: bold; }}
            QPushButton:hover {{ background: {C.GREEN}; color: #05060a; border: 1px solid {C.GREEN}; }}
            QPushButton:pressed {{ background: {C.GREEN_D}; color: #ffffff; }}"""
        _off = f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A}; border-radius: 2px;
                text-align: left; padding: 0 10px; font-weight: 500; }}
            QPushButton:hover {{ color: #ffffff; border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
            QPushButton:pressed {{ background: rgba(142, 155, 255, 0.20); }}"""
        self._wake_btn.setEnabled(True)
        if not st["ready"]:
            self._wake_btn.setText("[ ⬇ ]  COWL SENSORS : DOWNLOAD")
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()
        elif st["enabled"]:
            self._wake_btn.setText("[ ◈ ]  COWL SENSORS : ONLINE")
            self._wake_btn.setStyleSheet(_on)
            self._wake_sleep_btn.show()
            self._wake_sleep_btn.setText("[ ⊘ ]  COWL STANDBY" if st["awake"] else "[ ⚡ ]  ACTIVATE COWL")
            self._wake_sleep_btn.setStyleSheet(_off)
        else:
            self._wake_btn.setText("[ ⊘ ]  COWL SENSORS : STANDBY")
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()

    def _refresh_talk_btns(self):
        """Repaint the push-to-talk row from the saved setting."""
        if not hasattr(self, "_ptt_btn"):
            return
        from core.hotkey import chord_label
        from memory.config_manager import get_push_to_talk_enabled
        _on = f"""
            QPushButton {{ background: rgba(78, 242, 187, 0.08); color: {C.GREEN};
                border: 1px solid rgba(78, 242, 187, 0.45); border-radius: 2px;
                text-align: left; padding: 0 10px; font-weight: bold; }}
            QPushButton:hover {{ background: {C.GREEN}; color: #05060a; border: 1px solid {C.GREEN}; }}
            QPushButton:pressed {{ background: {C.GREEN_D}; color: #ffffff; }}"""
        _off = f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A}; border-radius: 2px;
                text-align: left; padding: 0 10px; font-weight: 500; }}
            QPushButton:hover {{ color: #ffffff; border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
            QPushButton:pressed {{ background: rgba(142, 155, 255, 0.20); }}"""

        ptt = get_push_to_talk_enabled()
        self._ptt_btn.setText(f"[ ◈ ]  TACTICAL COMMS PTT : {chord_label()}" if ptt
                              else "[ ⊘ ]  TACTICAL COMMS PTT : OFF")
        self._ptt_btn.setStyleSheet(_on if ptt else _off)
        self._ptt_btn.setToolTip(
            "Microphone stays closed until you hold the key — nothing is sent "
            "while you are not holding it." if ptt
            else "Hold a key to talk instead of streaming the mic continuously.")


    def _toggle_ptt(self):
        from memory.config_manager import (get_push_to_talk_enabled,
                                           save_push_to_talk_enabled)
        want = not get_push_to_talk_enabled()
        save_push_to_talk_enabled(want)
        scope = None
        if self.on_push_to_talk:
            try:
                scope = self.on_push_to_talk(want)
            except Exception as e:
                self._log.append_log(f"ERR: Push-to-talk failed — {e}")
                save_push_to_talk_enabled(False)
                want = False
        self._apply_ptt_shortcut(want and scope != "global")
        self._refresh_talk_btns()

    def _apply_ptt_shortcut(self, needed: bool):
        """Bind the chord inside the window when no global hook is available.

        On macOS and Linux there is no dependency-free way to read global key
        state, so the chord is at least live whenever this window has focus.
        Qt gives no key-release for a QShortcut, so a press latches the mic open
        and a short timer closes it; held down, auto-repeat keeps pushing that
        timer out, which behaves like holding a key.
        """
        from PyQt6.QtGui import QKeySequence, QShortcut
        from core.hotkey import qt_sequence

        if not needed:
            sc = getattr(self, "_ptt_sc", None)
            if sc is not None:
                sc.setEnabled(False)
                self._ptt_sc = None
            self._ptt_hold(False)
            return
        if getattr(self, "_ptt_sc", None) is not None:
            return

        self._ptt_release = QTimer(self)
        self._ptt_release.setSingleShot(True)
        self._ptt_release.setInterval(420)
        self._ptt_release.timeout.connect(lambda: self._ptt_hold(False))

        def _press():
            self._ptt_hold(True)
            self._ptt_release.start()

        self._ptt_sc = QShortcut(QKeySequence(qt_sequence()), self)
        self._ptt_sc.setAutoRepeat(True)
        self._ptt_sc.activated.connect(_press)

    def _ptt_hold(self, held: bool):
        """Report a windowed press/release to whoever owns the microphone."""
        cb = getattr(self, "ptt_hold", None)
        if cb:
            try:
                cb(bool(held))
            except Exception:
                pass

    def _toggle_wake_word(self):
        st = self._wake_state()
        if not st["ready"]:
            # First time: download openwakeword + model in a worker thread.
            self._wake_btn.setText("⬇  DOWNLOADING… (one-time)")
            self._wake_btn.setEnabled(False)
            def _work():
                try:
                    from core.wake_word import install_and_download
                    ok, msg = install_and_download(
                        logger=lambda m: self._log_sig.emit(f"SYS: {m}"))
                except Exception as e:
                    ok, msg = False, str(e)
                if ok and self.on_wake_toggle:
                    try:
                        self.on_wake_toggle(True)   # auto-enable after a successful download
                    except Exception:
                        pass
                self._wake_dl_sig.emit(ok, msg)
            threading.Thread(target=_work, daemon=True).start()
            return
        # Already downloaded → just flip enabled/disabled through JarvisLive.
        if self.on_wake_toggle:
            try:
                self.on_wake_toggle(not st["enabled"])
            except Exception:
                pass
        self._refresh_wake_btns()

    def _on_wake_install_done(self, ok: bool, msg: str):
        self._log_sig.emit(f"SYS: {'Wake word ready.' if ok else 'Wake word setup failed: ' + msg}")
        self._refresh_wake_btns()

    def _tap_wake_manual(self):
        if self.on_wake_manual:
            try:
                self.on_wake_manual()
            except Exception:
                pass
        self._refresh_wake_btns()

    def _update_brief_btn(self, enabled: bool):
        if not hasattr(self, '_brief_btn'):
            return
        if enabled:
            self._brief_btn.setText("[ ◈ ]  GOTHAM BRIEFING : ON")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(78, 242, 187, 0.08); color: {C.GREEN};
                    border: 1px solid rgba(78, 242, 187, 0.45); border-radius: 2px;
                    text-align: left; padding: 0 10px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {C.GREEN}; color: #05060a; border: 1px solid {C.GREEN}; }}
                QPushButton:pressed {{ background: {C.GREEN_D}; color: #ffffff; }}
            """)
        else:
            self._brief_btn.setText("[ ⊘ ]  GOTHAM BRIEFING : OFF")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    text-align: left; padding: 0 10px; font-weight: 500;
                }}
                QPushButton:hover {{ color: #ffffff; border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                QPushButton:pressed {{ background: rgba(142, 155, 255, 0.20); }}
            """)

    # ── Directives & Intel Terminal Controls ────────────────────────────────────

    def _open_directives(self):
        if self._capabilities_overlay:
            self._capabilities_overlay.hide()
        cw = self.centralWidget()
        ov = CapabilitiesOverlay(parent=cw)
        ow, oh = CapabilitiesOverlay._OW, CapabilitiesOverlay._OH
        oh = min(oh, cw.height() - 24)
        ow = min(ow, cw.width() - 24)
        ov.setGeometry(
            (cw.width() - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.show()
        self._capabilities_overlay = ov

    def _switch_terminal_tab(self, index: int):
        self._terminal_stack.setCurrentIndex(index)
        self._update_tab_button_styles(index)
        cnt = self._notes_terminal.count()
        count_str = f" ({cnt})" if cnt > 0 else ""
        from core.ui.themes import ThemeChrome
        self._tab_notes_btn.setText(f"{ThemeChrome.chrome().tab_intel}{count_str}")

    def _update_tab_button_styles(self, active_index: int):
        _ACTIVE_STYLE = f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
            }}
        """
        _INACTIVE_STYLE = f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: rgba(142, 155, 255, 0.10);
                color: #ffffff;
                border: 1px solid {C.PRI};
            }}
        """
        if active_index == 0:
            self._tab_activity_btn.setChecked(True)
            self._tab_activity_btn.setStyleSheet(_ACTIVE_STYLE)
            self._tab_notes_btn.setChecked(False)
            self._tab_notes_btn.setStyleSheet(_INACTIVE_STYLE)
        else:
            self._tab_activity_btn.setChecked(False)
            self._tab_activity_btn.setStyleSheet(_INACTIVE_STYLE)
            self._tab_notes_btn.setChecked(True)
            self._tab_notes_btn.setStyleSheet(_ACTIVE_STYLE)

    def _on_notes_count_updated(self, count: int):
        cur_idx = self._terminal_stack.currentIndex()
        count_str = f" ({count})" if count > 0 else ""
        from core.ui.themes import ThemeChrome
        tab_lbl = ThemeChrome.chrome().tab_intel
        if cur_idx == 0 and count > 0:
            self._tab_notes_btn.setText(f"{tab_lbl} • ({count})")
            self._tab_notes_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2};
                    color: {C.ACC};
                    border: 1px solid {C.ACC};
                    border-radius: 2px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {C.ACC};
                    color: {C.DARK};
                }}
            """)
        else:
            self._tab_notes_btn.setText(f"{tab_lbl}{count_str}")

    def _on_intel_note_received(self, title: str, content: str, note_type: str):
        self._notes_terminal.add_note(title, content, note_type)

    # ── Customization ────────────────────────────────────────────────────────────

    def _create_customize_overlay(self, cfg: dict) -> CustomizeOverlay:
        current_icon = self._current_icon_path or cfg.get("app_icon", "")
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "Alfred") or "Alfred",
            cfg.get("user_name", ""),
            cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
            cfg.get("voice_name", ""),
            current_icon=current_icon,
            voice_engine=cfg.get("voice_engine", "default"),
            parent=self.centralWidget(),
        )
        ov.on_preview = self._preview_ui_color
        ov.on_icon_change = self.set_app_icon
        ov.saved.connect(self._apply_name_update)
        ov.setup_api_requested.connect(self._open_api_setup)
        self._customize_overlay = ov
        return ov

    def _prewarm_settings_overlays(self) -> None:
        """Build expensive reusable settings widgets after first paint."""
        started = time.perf_counter()
        try:
            cfg = _read_full_config()
            if self._customize_overlay is None:
                self._create_customize_overlay(cfg)
            if self._overlay is None:
                self._overlay = SetupOverlay(self.centralWidget())
                self._overlay.done.connect(self._on_setup_done)
            print(f"[UI Perf] settings prewarm: {(time.perf_counter() - started) * 1000:.1f} ms")
        except Exception as exc:
            print(f"[UI Perf] settings prewarm skipped: {exc}")

    def _open_customize(self):
        started = time.perf_counter()
        try:
            cfg = _read_full_config()
            cw = self.centralWidget()
            current_icon = self._current_icon_path or cfg.get("app_icon", "")
            ov = self._customize_overlay
            if ov is None:
                ov = self._create_customize_overlay(cfg)
            else:
                ov.reset_values(
                    cfg.get("assistant_name", "Alfred") or "Alfred",
                    cfg.get("user_name", ""),
                    cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
                    cfg.get("voice_name", ""),
                    current_icon,
                    voice_engine=cfg.get("voice_engine", "default"),
                )
            ow = min(CustomizeOverlay._OW, cw.width() - 20)
            oh = min(CustomizeOverlay._OH, cw.height() - 20)
            ov.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
            ov.show()
            ov.raise_()
            print(f"[UI Perf] customize open: {(time.perf_counter() - started) * 1000:.1f} ms")
        except Exception as e:
            print(f"[UI] ⚠️ Failed to open reconfigure overlay: {e}")
            if hasattr(self, "_log") and self._log:
                try:
                    self._log.append_log(f"ERR: Failed to open reconfigure overlay — {e}")
                except Exception:
                    pass

    def set_app_icon(self, icon_path_or_name: str, notify: bool = True) -> bool:
        """
        Updates the main application window, taskbar icon, and chassis insignia in realtime.
        Accepts a full path, a filename in Icons/, or a keyword (e.g. 'beyond', 'white', 'asylum').
        """
        resolved_path = None
        if icon_path_or_name:
            p = Path(icon_path_or_name)
            if p.is_file() and p.exists():
                resolved_path = str(p.resolve())
            else:
                avail = get_available_app_icons()
                target_q = icon_path_or_name.lower().strip()
                for ic in avail:
                    if (target_q in ic["name"].lower() or 
                        target_q in ic["filename"].lower() or 
                        target_q == Path(ic["path"]).stem.lower()):
                        resolved_path = ic["path"]
                        break

        if not resolved_path:
            return False

        try:
            p_res = Path(resolved_path)
            ico_file = p_res.with_suffix(".ico")
            if not ico_file.exists():
                try:
                    from PIL import Image
                    img = Image.open(resolved_path)
                    img.save(ico_file, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
                except Exception:
                    pass

            if ico_file.exists():
                ico = QIcon(str(ico_file))
            else:
                ico = QIcon()
                for sz in (16, 24, 32, 48, 64, 128, 256):
                    pm = _scaled_icon_pixmap(resolved_path, sz, sz)
                    if not pm.isNull():
                        ico.addPixmap(pm)

            if not ico.isNull():
                self.setWindowIcon(ico)
                app = QApplication.instance()
                if app:
                    app.setWindowIcon(ico)

                # Native Win32 Taskbar icon injection
                if sys.platform == "win32":
                    try:
                        import ctypes
                        WM_SETICON = 0x0080
                        ICON_SMALL = 0
                        ICON_BIG = 1
                        LR_LOADFROMFILE = 0x0010
                        IMAGE_ICON = 1
                        target_ico_str = str(ico_file if ico_file.exists() else resolved_path)
                        hicon_big = ctypes.windll.user32.LoadImageW(
                            0, target_ico_str, IMAGE_ICON, 32, 32, LR_LOADFROMFILE
                        )
                        hicon_small = ctypes.windll.user32.LoadImageW(
                            0, target_ico_str, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
                        )
                        hwnd = int(self.winId())
                        if hicon_big:
                            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                        if hicon_small:
                            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    except Exception:
                        pass

                self._current_icon_path = resolved_path
                from memory.config_manager import save_app_icon
                save_app_icon(resolved_path)
                display_name = format_icon_display_name(Path(resolved_path).name)
                # Update top header app icon next to MK-IV
                if hasattr(self, "_header_icon_lbl") and self._header_icon_lbl:
                    pm = _scaled_icon_pixmap(resolved_path, 22, 22)
                    if not pm.isNull():
                        self._header_icon_lbl.setPixmap(pm)
                if notify and hasattr(self, "_log") and self._log:
                    self._log.append_log(f"SYS: Insignia updated in realtime — {display_name}")
                return True
        except Exception as e:
            if hasattr(self, "_log") and self._log:
                self._log.append_log(f"ERR: Failed to set app icon: {e}")
            else:
                print(f"[UI] ⚠️ Failed to set app icon: {e}")
            return False
        return False


    def _preview_ui_color(self, hex_color: str):
        """Live preview — paints the whole interface the new colour (does NOT write to config)."""
        old = current_palette()
        if apply_ui_accent(hex_color):
            retheme_all_widgets(old, current_palette())

    def _on_theme_chrome_updated(self, theme):
        """Update contextual chrome text whenever theme changes."""
        try:
            display = self._assistant_name.upper()
            chrome = theme.chrome
            ident = theme.identity
            self.setWindowTitle(f"{display} — {APP_VERSION} // {chrome.window_title_suffix}")
            if hasattr(self, "_sub_lbl") and self._sub_lbl:
                self._sub_lbl.setText(ident.affiliation_line)
            if hasattr(self, "_hdr_telemetry") and self._hdr_telemetry:
                self._hdr_telemetry.setText(chrome.telemetry_header)
            if hasattr(self, "_tab_activity_btn") and self._tab_activity_btn:
                self._tab_activity_btn.setText(chrome.tab_telemetry)
            if hasattr(self, "_tab_notes_btn") and self._tab_notes_btn:
                cnt = self._notes_terminal.count() if hasattr(self, "_notes_terminal") and self._notes_terminal else 0
                count_str = f" ({cnt})" if cnt > 0 else ""
                self._tab_notes_btn.setText(f"{chrome.tab_intel}{count_str}")
            if hasattr(self, "_dossier_card") and self._dossier_card:
                self._dossier_card.update()
            if hasattr(self, "_recon_widget") and self._recon_widget:
                self._recon_widget.update()
            if hasattr(self, "_bio_widget") and self._bio_widget:
                self._bio_widget.update()
            if hasattr(self, "_pose_widget") and self._pose_widget:
                self._pose_widget.update()
            if hasattr(self, "_hud_overlay") and self._hud_overlay:
                self._hud_overlay.refresh_thematic_chrome()
        except Exception as e:
            print(f"[Theme Update] Error updating chrome: {e}")

    def _apply_name_update(self, name: str, user_name: str, ui_color: str = "",
                           voice: str = ""):
        """Update all name/theme-dependent UI elements and persist to config."""
        self._assistant_name = name.strip() or "Alfred"
        display = self._assistant_name.upper()
        from core.ui.themes import ThemeChrome
        self.setWindowTitle(f"{display} — {APP_VERSION} // {ThemeChrome.chrome().window_title_suffix}")
        self._title_lbl.setText(f"┌  {display} // {APP_VERSION}  ┐")
        self._sub_lbl.setText(ThemeChrome.identity().affiliation_line)
        self._log._ai_name_lc = self._assistant_name.lower()
        self._hud_overlay.set_assistant_name(self._assistant_name)
        self.hud._assistant_name = display
        if hasattr(self, "_dossier_card") and self._dossier_card:
            self._dossier_card.set_name(display)
        pass  # face renderer removed

        color_changed = False
        if ui_color:
            old = current_palette()
            if apply_ui_accent(ui_color):
                # Live-paint the whole interface (panels, buttons, borders, HUD)
                retheme_all_widgets(old, current_palette())
                color_changed = old["PRI"] != C.PRI

        # Voice change → persist and, if it actually changed, rebuild the Live
        # session so the new voice takes effect (it's fixed at connect time).
        voice_changed = False
        if voice:
            from memory.config_manager import get_voice, save_voice
            if voice != get_voice():
                save_voice(voice)
                voice_changed = True

        try:
            data = _read_full_config()
            data["assistant_name"] = self._assistant_name
            data["user_name"] = user_name.strip()
            if ui_color:
                data["ui_color"] = ui_color.strip().lower()
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log(f"SYS: Identity updated — {display}")
            if color_changed:
                self._log.append_log(f"SYS: UI colour applied — {ui_color}")
            if voice_changed:
                self._log.append_log(f"SYS: Voice set — {voice}")
        except Exception as e:
            self._log.append_log(f"ERR: Config save failed — {e}")

        if voice_changed and self.on_voice_change:
            self.on_voice_change()

    def _centre_overlay(self, ov) -> None:
        """Place a floating overlay in the middle of the HUD and show it."""
        from core.hud_video.layering import raise_overlay
        cw = self.centralWidget()
        ov.adjustSize()
        ov.setGeometry(
            max(0, (cw.width()  - ov.width())  // 2),
            max(0, (cw.height() - ov.height()) // 2),
            ov.width(), ov.height(),
        )
        raise_overlay(ov, cw)

    # ── Audio devices ────────────────────────────────────────────────────────

    def _open_audio_devices(self):
        ov = AudioDeviceOverlay(parent=self.centralWidget())
        ov.picked.connect(self._on_audio_devices_applied)
        self._centre_overlay(ov)
        self._audio_overlay = ov            # keep a reference so it isn't GC'd

    def _on_audio_devices_applied(self):
        self._log.append_log("SYS: Audio devices updated.")
        if self.on_audio_device_change:
            self.on_audio_device_change()

    def set_audio_status(self, status: str) -> None:
        """Update audio status indicator in a thread-safe way."""
        self._audio_status_sig.emit(status)

    def _apply_audio_status(self, status: str) -> None:
        st = (status or "").upper().strip()
        if hasattr(self, "_audio_status_pill") and self._audio_status_pill is not None:
            if "READY" in st or "ONLINE" in st:
                self._audio_status_pill.setText("AUDIO: READY")
                self._audio_status_pill.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
            else:
                self._audio_status_pill.setText(f"AUDIO: {st}")
                self._audio_status_pill.setStyleSheet(f"color: {C.ACC2}; background: transparent;")

    def _start_animations(self) -> None:
        if hasattr(self, "hud") and hasattr(self.hud, "_start_animations"):
            self.hud._start_animations()

    # ── Memory panel ─────────────────────────────────────────────────────────

    def _open_memory_panel(self):
        ov = MemoryOverlay(parent=self.centralWidget())
        self._centre_overlay(ov)
        self._memory_overlay = ov

    # ── Irreversible-action confirmation ─────────────────────────────────────

    def _show_confirm_banner(self, title: str, detail: str):
        self._hide_confirm_banner()
        ov = ConfirmBanner(title, detail, parent=self.centralWidget())
        ov.answered.connect(self._on_confirm_answered)
        self._centre_overlay(ov)
        self._confirm_overlay = ov

    def _hide_confirm_banner(self):
        ov = getattr(self, "_confirm_overlay", None)
        if ov is not None:
            ov.hide()
            ov.deleteLater()
            self._confirm_overlay = None

    def _on_confirm_answered(self, accepted: bool):
        # Tear the banner down first: core.confirm.resolve() may be about to
        # shut the machine down, and a live widget mid-callback is not where you
        # want to be when that happens.
        self._hide_confirm_banner()
        try:
            from core.confirm import resolve
            resolve(bool(accepted))
        except Exception as e:
            self._log.append_log(f"ERR: Confirmation failed — {e}")

    def _open_plugin_manager(self):
        try:
            plugins = self.get_plugins() if self.get_plugins else []
            cw = self.centralWidget()
            if hasattr(self, "_plugin_manager_overlay") and self._plugin_manager_overlay:
                self._plugin_manager_overlay.hide()
            ov = PluginManagerOverlay(plugins, parent=cw)
            ov.adjustSize()
            ov.setGeometry(
                (cw.width()  - ov.width())  // 2,
                (cw.height() - ov.height()) // 2,
                ov.width(), ov.height(),
            )
            ov.show()
            ov.raise_()
            self._plugin_manager_overlay = ov   # keep a reference so it isn't GC'd
        except Exception as e:
            print(f"[UI] ⚠️ Failed to open plugin manager: {e}")
            if hasattr(self, "_log") and self._log:
                try:
                    self._log.append_log(f"ERR: Failed to open plugin manager — {e}")
                except Exception:
                    pass

    def _open_plugin_settings(self):
        started = time.perf_counter()
        try:
            sections = self.get_plugin_settings() if self.get_plugin_settings else []
            cw = self.centralWidget()
            signature = _plugin_settings_signature(sections)
            ov = getattr(self, "_plugin_settings_overlay", None)
            if ov is None or getattr(self, "_plugin_settings_signature", None) != signature:
                if ov is not None:
                    ov.hide()
                    ov.deleteLater()
                ov = PluginSettingsOverlay(sections, parent=cw)
                ov.setup_api_requested.connect(self._open_api_setup)
                self._plugin_settings_overlay = ov
                self._plugin_settings_signature = signature
            ow = PluginSettingsOverlay._OW
            oh = min(560, cw.height() - 16)
            ov.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
            ov.show()
            ov.raise_()
            print(f"[UI Perf] plugin settings open: {(time.perf_counter() - started) * 1000:.1f} ms")
        except Exception as e:
            print(f"[UI] ⚠️ Failed to open module parameters: {e}")
            if hasattr(self, "_log") and self._log:
                try:
                    self._log.append_log(f"ERR: Failed to open module parameters — {e}")
                except Exception:
                    pass

    def _refresh_setup_api_btn(self):
        """Update the Tactical Controls button text with configured count."""
        if not hasattr(self, "_setup_api_btn") or self._setup_api_btn is None:
            return
        try:
            from core.apis.registry import get_configured_backends_count
            configured, total = get_configured_backends_count()
            self._setup_api_btn.setText(f"[ ◈ ]  SETUP API BACKENDS ({configured}/{total})")
        except Exception:
            self._setup_api_btn.setText("[ ◈ ]  SETUP API BACKENDS")

    def _open_api_setup(self):
        """Lazy-instantiate and display the SetupApiModal dialog."""
        started = time.perf_counter()
        try:
            if not hasattr(self, "_api_setup_modal") or self._api_setup_modal is None:
                from ui.setup_api_modal import SetupApiModal
                self._api_setup_modal = SetupApiModal(parent=self)
                self._api_setup_modal.config_saved.connect(self._on_api_setup_saved)
            from core.hud_video.layering import centre_overlay_globally, raise_overlay
            centre_overlay_globally(self._api_setup_modal, self)
            raise_overlay(self._api_setup_modal, self)
            print(f"[UI Perf] api setup modal open: {(time.perf_counter() - started) * 1000:.1f} ms")
        except Exception as e:
            print(f"[UI] ⚠️ Failed to open api setup modal: {e}")
            if hasattr(self, "_log") and self._log:
                try:
                    self._log.append_log(f"ERR: Failed to open API setup — {e}")
                except Exception:
                    pass

    def _on_api_setup_saved(self, backend_name: str):
        """Handle backend credentials saved event."""
        self._refresh_setup_api_btn()
        if hasattr(self, "_log") and self._log:
            try:
                self._log.append_log(f"SYS: Backend '{backend_name}' authenticated and configured, sir.")
            except Exception:
                pass

    # ── Clipboard intelligence ───────────────────────────────────────────────────

    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self._clipboard_sig.emit(text)
        except Exception:
            pass

    def _show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.centralWidget()
        pw = ClipboardPanel._W
        ph = self._clipboard_panel.sizeHint().height() or ClipboardPanel._H
        x = (cw.width() - pw) // 2
        y = cw.height() - ph - 6
        self._clipboard_panel.setGeometry(x, y, pw, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    # ────────────────────────────────────────────────────────────────────────────

    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Silence protocol engaged. Cowl acoustic sensors offline.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Cowl acoustic sensors online. Batcomputer listening.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("[ ⊘ ]  SILENCE PROTOCOL : ENGAGED  //  COWL MUTED")
            self._mute_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 51, 102, 0.08);
                    color: #ff3366;
                    border: 1px solid rgba(255, 51, 102, 0.45);
                    border-radius: 2px;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: #ff3366;
                    border: 1px solid #ff3366;
                    color: #05060a;
                }}
                QPushButton:pressed {{
                    background: #cc2244;
                    color: #ffffff;
                }}
            """)
        else:
            self._mute_btn.setText("[ ◈ ]  ACOUSTIC SENSORS : ONLINE  //  COWL PROTOCOL")
            self._mute_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=1.0))
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(78, 242, 187, 0.08);
                    color: {C.GREEN};
                    border: 1px solid rgba(78, 242, 187, 0.45);
                    border-radius: 2px;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: {C.GREEN};
                    border: 1px solid {C.GREEN};
                    color: #05060a;
                }}
                QPushButton:pressed {{
                    background: {C.GREEN_D};
                    color: #ffffff;
                }}
            """)

    # ── Cognitive-trace toggle ────────────────────────────────────────────────

    def _style_think_btn(self, active: bool) -> None:
        """Style the COGNITIVE TRACE toggle to reflect its on/off state."""
        if active:
            self._think_btn.setText("[ ◈ ]  COGNITIVE TRACE : ON")
            self._think_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0, 240, 255, 0.10);
                    color: {C.PRI};
                    border: 1px solid {C.PRI_DIM};
                    border-radius: 2px;
                    padding: 0 8px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {C.PRI_GHO};
                    border-color: {C.PRI};
                }}
                QPushButton:pressed {{
                    background: rgba(0, 240, 255, 0.25);
                }}
            """)
        else:
            self._think_btn.setText("[ ◈ ]  COGNITIVE TRACE : OFF")
            self._think_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER};
                    border-radius: 2px;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    color: {C.TEXT_MED};
                    border-color: {C.BORDER_B};
                    background: rgba(255, 255, 255, 0.03);
                }}
                QPushButton:pressed {{
                    background: rgba(255, 255, 255, 0.06);
                }}
            """)

    def _toggle_think(self, active: bool) -> None:
        """Show or hide the agent's internal reasoning trace in the chat log."""
        self._log.show_thinking = active
        self._style_think_btn(active)
        if active:
            self._log.append_log(
                "SYS: Cognitive trace enabled, sir. "
                "You may now observe the deliberation behind each response."
            )
        else:
            self._log.append_log(
                "SYS: Cognitive trace concealed, sir. Only the conclusions remain."
            )

    def _toggle_sentry_mode(self, checked: bool | None = None) -> None:
        """Sentry Mode button handler: opens the dual MONITOR + FOCUS menu, or toggles if boolean passed."""
        if isinstance(checked, bool) and getattr(self, "on_screen_monitor_toggle", None):
            try:
                result = self.on_screen_monitor_toggle(bool(checked))
                active = bool(result.get("active", checked)) if isinstance(result, dict) else bool(checked)
                label = result.get("label", "") if isinstance(result, dict) else ""
                self._apply_screen_monitor_state(active, label)
                return
            except Exception as exc:
                self._apply_screen_monitor_state(False, "Screen monitor error")
                if hasattr(self, "_log"):
                    self._log.append_log(f"ERR: Screen monitoring failed — {exc}")
                return

        self._show_sentry_menu(self._sentry_btn)

    def _create_sentry_menu(self) -> QMenu:
        parent_widget = self if isinstance(self, QWidget) else None
        menu = QMenu(parent_widget)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 12px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: rgba(142, 155, 255, 0.22);
                color: #ffffff;
            }}
        """)
        mgr = get_sentry_mode_manager()
        snap = mgr.get_snapshot()

        # MONITOR options
        if snap.monitor.active:
            mon_act = menu.addAction("[ ◈ ] MONITOR (ON) ▸ Stop")
            mon_act.triggered.connect(lambda: self._toggle_monitor_mode(stop_only=True))
        else:
            mon_screen_act = menu.addAction("[ ◈ ] MONITOR (Screen) ▸ Start")
            mon_screen_act.triggered.connect(lambda: self._toggle_monitor_mode(goal="screen"))
            mon_custom_act = menu.addAction("[ ▣ ] MONITOR (Custom / Ask) ▸ Start")
            mon_custom_act.triggered.connect(lambda: self._toggle_monitor_mode(goal=""))

        menu.addSeparator()

        # FOCUS option
        foc_label = f"[ ◉ ] FOCUS (ON) ▸ Stop" if snap.focus.active else f"[ ○ ] FOCUS (OFF) ▸ Start"
        foc_act = menu.addAction(foc_label)
        foc_act.triggered.connect(self._toggle_focus_mode)

        return menu

    def _show_sentry_menu(self, anchor: QWidget | None = None) -> None:
        target = anchor if (isinstance(anchor, QWidget) and anchor.isVisible()) else self._sentry_btn
        if not target or not isinstance(target, QWidget):
            return
        menu = self._create_sentry_menu()
        menu.exec(target.mapToGlobal(QPoint(0, target.height())))

    def _toggle_monitor_mode(self, goal: str = "screen", stop_only: bool = False) -> None:
        mgr = get_sentry_mode_manager()
        if stop_only or mgr.monitor_state.active:
            mgr.stop_monitor("Stopped from UI.")
        else:
            mgr.start_monitor(goal=goal)
        self._apply_sentry_snapshot(mgr.get_snapshot())

    def _toggle_focus_mode(self) -> None:
        mgr = get_sentry_mode_manager()
        mgr.toggle_focus()
        self._apply_sentry_snapshot(mgr.get_snapshot())

    def _apply_sentry_snapshot(self, snapshot: SentrySnapshot) -> None:
        try:
            mon = snapshot.monitor
            foc = snapshot.focus

            if mon.active and foc.active:
                self._sentry_btn.setChecked(True)
                self._sentry_btn.setText("[ ◈◉ ] SENTRY (2)")
                self._sentry_btn.setToolTip("Both MONITOR and FOCUS active")
            elif mon.active:
                self._sentry_btn.setChecked(True)
                self._sentry_btn.setText("[ ◈ ]  SCREEN MONITORING")
                self._sentry_btn.setToolTip(f"MONITOR active: {mon.label or 'running'}")
            elif foc.active:
                self._sentry_btn.setChecked(True)
                self._sentry_btn.setText("[ ◉ ]  FOCUS MODE")
                self._sentry_btn.setToolTip("FOCUS active")
            else:
                self._sentry_btn.setChecked(False)
                self._sentry_btn.setText("[ ▣ ]  SENTRY MODE")
                self._sentry_btn.setToolTip("Sentry Mode: MONITOR + FOCUS")

            if hasattr(self, "hud") and hasattr(self.hud, "set_sentry_snapshot"):
                self.hud.set_sentry_snapshot(snapshot)
            if hasattr(self, "_dossier_card") and self._dossier_card:
                if foc.active and getattr(foc, "drifting", False):
                    self._dossier_card.set_threat_state("critical")
                elif foc.active or mon.active:
                    self._dossier_card.set_threat_state("elevated")
                else:
                    self._dossier_card.set_threat_state("clear")
            if hasattr(self, "_focus_card"):
                self._focus_card.update_state(foc)
            if hasattr(self, "_hud_overlay") and hasattr(self._hud_overlay, "update_sentry_indicator"):
                waiting_for_answer = getattr(mon, "waiting_for_answer", False)
                mgr = get_sentry_mode_manager()
                if hasattr(mgr, "is_waiting_for_answer"):
                    try:
                        waiting_for_answer = bool(waiting_for_answer or mgr.is_waiting_for_answer())
                    except Exception:
                        pass
                self._hud_overlay.update_sentry_indicator(
                    mon.active,
                    foc.active,
                    waiting_for_answer=waiting_for_answer,
                    foc_remaining_s=foc.remaining_s,
                    drifting=foc.drifting,
                )
        except Exception as exc:
            _LOGGER.exception("Safe boundary: unhandled error in _apply_sentry_snapshot: %s", exc)

    def _apply_screen_monitor_state(self, active: bool, label: str = "") -> None:
        """Apply monitor state on the Qt thread for click and voice controls."""
        mgr = get_sentry_mode_manager()
        mgr.update_monitor_state(
            active=bool(active),
            label=label or ("Active" if active else ""),
            target_count=1 if active else 0,
        )
        self._sentry_btn.setChecked(bool(active))
        self._sentry_btn.setText("[ ◈ ]  SCREEN MONITORING" if active else "[ ▣ ]  SENTRY MODE")
        self._sentry_btn.setToolTip(label or (
            "Continuous screen monitoring active" if active
            else "Monitor the screen for task completion"
        ))
        if hasattr(self, "_hud_overlay") and hasattr(self._hud_overlay, "update_sentry_indicator"):
            self._hud_overlay.update_sentry_indicator(bool(active), mgr.focus_state.active)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _on_clear_chat(self):
        """Thread-safe UI slot: wipe chat display."""
        self._log.clear_log()
        self._log.append_log("SYS: Conversation history and chat log wiped.")

    def clear_chat(self):
        """Wipe chat log and trigger any registered callback (e.g. backend/mobile sync)."""
        self._on_clear_chat()
        if self.on_clear_chat:
            try:
                self.on_clear_chat()
            except Exception as e:
                print(f"[UI] on_clear_chat error: {e}")

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")
        if hasattr(self, "_hud_video_controller") and self._hud_video_controller is not None:
            if state == "SPEAKING":
                self._hud_video_controller.duck()
            else:
                self._hud_video_controller.unduck()

    def set_media_arbiter(self, arbiter) -> None:
        """Connect application-level media state to the UI-owned audio player."""
        self._media_arbiter = arbiter
        self._bg_music.set_media_arbiter(arbiter)
        arbiter.state_changed.connect(self._on_media_state_changed)
        self._on_media_state_changed(arbiter.state)

    def _on_media_state_changed(self, state) -> None:
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.set_ducked(bool(state.tts_ducking))
        if hasattr(self, "_hud_video_controller") and self._hud_video_controller is not None:
            if bool(state.tts_ducking):
                self._hud_video_controller.duck()
            else:
                self._hud_video_controller.unduck()
        if state.overridden:
            self.set_audio_status("SHARED")
        elif state.external_suppressed:
            self.set_audio_status("EXCLUSIVE")
        else:
            self.set_audio_status("READY")

    def show_image_deck(self, path: str, caption: str = "") -> None:
        from core.image_viewer import get_image_viewer, extract_host
        viewer = get_image_viewer(self)
        self._image_deck = viewer
        viewer.show_image(path, caption=caption, host=extract_host(path))

    def set_scheduler(self, scheduler) -> None:
        """Attach the local task scheduler after application startup."""
        from core.ui.task_board import TaskBoard
        if self._task_board is None:
            self._task_board = TaskBoard(scheduler, self)
            self._task_board.move(28, 145)
        else:
            self._task_board.scheduler = scheduler

    def _on_scheduler_event(self, task: object) -> None:
        if self._task_board is None or not isinstance(task, dict):
            return
        self._task_board.present_event(task)
        try:
            status = str(task.get("status", "pending")).upper()
            self._log.append_log(f"TASK: {task.get('name', task.get('action_type', 'task'))} // {status}")
        except Exception:
            pass

    def show_task_board(self) -> None:
        if self._task_board is not None:
            self._task_board.refresh()
            self._task_board.show()
            self._task_board.raise_()

    def set_spotify_playback(
        self, title: str, artist: str = "", uri: str = "", is_playing: bool = True
    ):
        """Update bottom-left tactical audio player to display and control Spotify playback."""
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.set_spotify_playback(title, artist, uri, is_playing)

    def set_spotify_playback_state(self, is_playing: bool) -> None:
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.set_spotify_playback_state(is_playing)

    def restore_tron_music(self):
        """Restore default TRON Legacy score on bottom-left tactical audio player."""
        if hasattr(self, "_bg_music") and self._bg_music:
            self._bg_music.clear_spotify_and_restore_tron()

    def pause_audio_core(self) -> bool:
        """Pause the Audio Core (TRON background music engine)."""
        if hasattr(self, "_bg_music") and self._bg_music:
            if hasattr(self._bg_music, "pause_core"):
                self._bg_music.pause_core()
            else:
                self._bg_music.pause()
            return True
        return False

    def resume_audio_core(self) -> bool:
        """Resume or play the Audio Core (TRON background music engine)."""
        if hasattr(self, "_bg_music") and self._bg_music:
            if hasattr(self._bg_music, "resume_core"):
                self._bg_music.resume_core()
            elif self._bg_music.source_mode() != "tron":
                self._bg_music.clear_spotify_and_restore_tron()
            else:
                self._bg_music.play()
            return True
        return False

    def set_audio_core_volume(self, volume_percent: int) -> float:
        """Set base volume of the Audio Core (0 to 100)."""
        if hasattr(self, "_bg_music") and self._bg_music:
            vol = max(0.0, min(1.0, float(volume_percent) / 100.0))
            self._bg_music.set_base_volume(vol)
            return vol
        return 0.10

    def get_audio_core_status(self) -> dict:
        """Get status of the Audio Core."""
        if hasattr(self, "_bg_music") and self._bg_music:
            return {
                "is_playing": self._bg_music.is_playing(),
                "volume": int(self._bg_music.base_volume() * 100),
                "source_mode": self._bg_music.source_mode(),
                "track": self._bg_music.current_track_stem(),
            }
        return {"is_playing": False, "volume": 10, "source_mode": "tron", "track": "The Son of Flynn"}

    def closeEvent(self, e):
        try:
            from core.ui.themes import ThemeChrome
            ThemeChrome.remove_listener(self._on_theme_chrome_updated)
        except Exception:
            pass
        if hasattr(self, "_hud_overlay"):
            self._hud_overlay.shutdown()
        if getattr(self, "_sentry_btn", None) and self._sentry_btn.isChecked():
            try:
                if self.on_screen_monitor_toggle:
                    self.on_screen_monitor_toggle(False)
            except Exception:
                pass
        try:
            if hasattr(self, "_bg_music") and self._bg_music:
                self._bg_music.stop()
        except Exception:
            pass
        super().closeEvent(e)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange or not hasattr(self, "_hud_overlay"):
            return
        if self.isMinimized():
            self._hud_overlay.begin_minimize_session()
            # Pause video when minimised (policy: pause on minimise)
            if self._hud_video_controller is not None:
                self._hud_video_controller.on_minimise()
        else:
            self._hud_overlay.hide_overlay()
            # Resume video if it was paused by minimise
            if self._hud_video_controller is not None:
                self._hud_video_controller.on_restore()

    def _check_config(self) -> bool:
        if not API_FILE.exists():
            env_k = os.environ.get("GEMINI_API_KEY", "").strip()
            return bool(env_k and len(env_k) > 5)
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                return False

            provider = str(d.get("llm_provider", "gemini")).strip().lower()
            if provider in ("ollama", "openai", "lmstudio", "local"):
                # Local offline model configured — Gemini API key is NOT required
                return True

            if provider == "openrouter":
                k = (
                    d.get("openrouter_api_key")
                    or d.get("OPENROUTER_API_KEY")
                    or os.environ.get("OPENROUTER_API_KEY", "")
                )
                return bool(k and len(k.strip()) > 5)

            # If Gemini (or default): check for API key in config or environment
            key = (
                d.get("gemini_api_key")
                or d.get("GEMINI_API_KEY")
                or d.get("api_key")
                or os.environ.get("GEMINI_API_KEY", "")
            )
            if key and isinstance(key, str) and len(key.strip()) > 5:
                return True

            # Also check if any other provider keys exist
            for pk in ("openai_api_key", "groq_api_key", "anthropic_api_key", "openrouter_api_key"):
                val = d.get(pk)
                if val and isinstance(val, str) and len(val.strip()) > 5:
                    return True

            return False
        except Exception:
            return False

    def _show_setup(self):
        started = time.perf_counter()
        ov = getattr(self, "_overlay", None)
        if ov is None:
            ov = SetupOverlay(self.centralWidget())
            ov.done.connect(self._on_setup_done)
            self._overlay = ov
        cw = self.centralWidget()
        ow = min(580, cw.width() - 40)
        oh = min(540, cw.height() - 40)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.show()
        ov.raise_()
        print(f"[UI Perf] setup open: {(time.perf_counter() - started) * 1000:.1f} ms")

    def _open_api_setup(self):
        """Open the API key and neural backend configuration overlay from settings."""
        if hasattr(self, "_quick_drawer") and self._quick_drawer.isVisible():
            self._quick_drawer.hide()
            if hasattr(self, "_drawer_btn"):
                self._drawer_btn.setChecked(False)
        if hasattr(self, "_customize_overlay") and self._customize_overlay and self._customize_overlay.isVisible():
            self._customize_overlay.hide()
        if hasattr(self, "_plugin_settings_overlay") and self._plugin_settings_overlay and self._plugin_settings_overlay.isVisible():
            self._plugin_settings_overlay.hide()
        self._show_setup()

    def _on_setup_done(self, config_data, os_name=None):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        current = {}
        if API_FILE.exists():
            try:
                current = json.loads(API_FILE.read_text(encoding="utf-8"))
            except Exception:
                current = {}

        if isinstance(config_data, dict):
            current.update(config_data)
            os_name = current.get("os_system", "windows")
            prov = current.get("llm_provider", "gemini")
            if "assistant_name" in config_data and config_data["assistant_name"]:
                self._assistant_name = str(config_data["assistant_name"]).strip()
                try:
                    self.setWindowTitle(f"{self._assistant_name.upper()} - {APP_VERSION}")
                except Exception:
                    pass
        else:
            current["gemini_api_key"] = str(config_data)
            if os_name:
                current["os_system"] = os_name
            prov = current.get("llm_provider", "gemini")

        API_FILE.write_text(
            json.dumps(current, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
        self._apply_state("LISTENING")
        self._assistant_name = _read_full_config().get("assistant_name", "Alfred") or "Alfred"
        self._log.append_log(f"SYS: Initialised. Mode: {prov.upper()}. OS: {str(os_name).upper()}. {self._assistant_name} online.")


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("alfred.wayne.batcomputer.mk4")
            except Exception:
                pass
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self.root = _RootShim(self._app)
        self._win.show()
        QTimer.singleShot(0, self._win._start_animations)

    def set_app_icon(self, icon_path_or_name: str) -> bool:
        """Update application and window icon in realtime."""
        return self._win.set_app_icon(icon_path_or_name)


    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    def toggle_mute(self) -> None:
        """Toggle audio mute state."""
        self._win._toggle_mute()

    def set_media_arbiter(self, arbiter) -> None:
        """Connect application-level media state to MainWindow."""
        self._win.set_media_arbiter(arbiter)

    def set_scheduler(self, scheduler) -> None:
        """Attach the local scheduler and marshal events through the Qt UI."""
        self._win.set_scheduler(scheduler)

    def scheduler_event(self, task: dict) -> None:
        self._win._scheduler_event_sig.emit(dict(task))

    def show_task_board(self) -> None:
        self._win.show_task_board()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def on_voice_change(self):
        return self._win.on_voice_change

    @on_voice_change.setter
    def on_voice_change(self, cb):
        self._win.on_voice_change = cb

    @property
    def on_audio_device_change(self):
        return self._win.on_audio_device_change

    @on_audio_device_change.setter
    def on_audio_device_change(self, cb):
        self._win.on_audio_device_change = cb

    @property
    def on_screen_monitor_toggle(self):
        return self._win.on_screen_monitor_toggle

    @on_screen_monitor_toggle.setter
    def on_screen_monitor_toggle(self, cb):
        self._win.on_screen_monitor_toggle = cb

    def apply_sentry_snapshot(self, snapshot: SentrySnapshot) -> None:
        """Thread-safe Sentry Mode snapshot update."""
        self._win._sentry_snapshot_sig.emit(snapshot)

    def set_screen_monitor_state(self, active: bool, label: str = "") -> None:
        """Thread-safe monitor state update used by click and voice controls."""
        self._win._screen_monitor_sig.emit(bool(active), str(label or ""))

    def show_confirm(self, title: str, detail: str) -> None:
        """Thread-safe: raise the irreversible-action gate. Called from action
        handlers running in executor threads, so it goes through a signal."""
        self._win._confirm_sig.emit(str(title)[:120], str(detail)[:300])

    def hide_confirm(self) -> None:
        """Thread-safe: take the gate down."""
        self._win._confirm_hide_sig.emit()

    @property
    def get_plugins(self):
        return self._win.get_plugins

    @get_plugins.setter
    def get_plugins(self, cb):
        self._win.get_plugins = cb

    @property
    def get_plugin_settings(self):
        return self._win.get_plugin_settings

    @get_plugin_settings.setter
    def get_plugin_settings(self, cb):
        self._win.get_plugin_settings = cb

    @property
    def on_wake_toggle(self):
        return self._win.on_wake_toggle

    @on_wake_toggle.setter
    def on_wake_toggle(self, cb):
        self._win.on_wake_toggle = cb

    @property
    def on_wake_manual(self):
        return self._win.on_wake_manual

    @on_wake_manual.setter
    def on_wake_manual(self, cb):
        self._win.on_wake_manual = cb

    @property
    def wake_get_state(self):
        return self._win.wake_get_state

    @wake_get_state.setter
    def wake_get_state(self, cb):
        self._win.wake_get_state = cb

    @property
    def on_wake_install(self):
        return getattr(self._win, "on_wake_install", None)

    @on_wake_install.setter
    def on_wake_install(self, cb):
        self._win.on_wake_install = cb

    @property
    def wake_is_ready(self):
        return getattr(self._win, "wake_is_ready", None)

    @wake_is_ready.setter
    def wake_is_ready(self, cb):
        self._win.wake_is_ready = cb

    @property
    def request_say(self):
        return getattr(self._win, "request_say", None)

    @request_say.setter
    def request_say(self, cb):
        self._win.request_say = cb

    def set_audio_level(self, level: float) -> None:
        """Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform.
        Called from the audio threads; a plain float store is atomic under the
        GIL, so no signal/lock is needed for this cosmetic value."""
        try:
            self._win.hud.set_audio_level(level)
        except Exception:
            pass

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """No-op: gaze tracking removed (face renderer removed)."""
        pass

    @property
    def ptt_hold(self):
        return self._win.ptt_hold

    @ptt_hold.setter
    def ptt_hold(self, cb):
        self._win.ptt_hold = cb

    @property
    def on_push_to_talk(self):
        return self._win.on_push_to_talk

    @on_push_to_talk.setter
    def on_push_to_talk(self, cb):
        self._win.on_push_to_talk = cb

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: post a schedule of (level, openness, width) mouth frames
        for JARVIS's own speech. `at` is the wall-clock time the batch begins to
        sound, not the time of the call. See HudCanvas.push_visemes()."""
        try:
            self._win.hud.push_visemes(frames, hop, at)
        except Exception:
            pass

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_audio_status(self, status: str):
        if hasattr(self, "_win") and self._win is not None:
            self._win.set_audio_status(status)

    def show_image_deck(self, path: str, caption: str = "") -> None:
        self._win.show_image_deck(path, caption)

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def clear_chat(self):
        """Thread-safe: wipe the on-screen conversation chat feed."""
        self._win._clear_log_sig.emit()

    @property
    def on_clear_chat(self):
        return self._win.on_clear_chat

    @on_clear_chat.setter
    def on_clear_chat(self, fn):
        self._win.on_clear_chat = fn

    def add_intel_note(self, title: str, content: str, note_type: str = "note"):
        """Thread-safe: post special note, research link, or structured data to the dedicated Notes Terminal."""
        self._win._intel_note_sig.emit(str(title), str(content), str(note_type))

    def clear_intel_notes(self):
        """Thread-safe: clear the dedicated Notes Terminal."""
        try:
            self._win._notes_terminal.clear_notes()
        except Exception:
            pass

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        """Thread-safe: display content in the panel below the HUD."""
        self._win._content_sig.emit(title[:48], text[:4000])

    def show_quiz(self, topic: str, questions, grade=None) -> None:
        """Thread-safe: put an interactive quiz on the board.

        `grade(question, given)` decides each answer — the plugin supplies it so
        the marking rules live with the questions rather than being duplicated
        here. Returning None from it means "JARVIS should judge this one", which
        is how open answers and near-miss gap-fills are handled.

        Returns immediately: the user answers at their own pace and the finished
        result is delivered back through on_text_command.
        """
        self._win._quiz_sig.emit(str(topic or ""), list(questions or []), grade)

    def hide_quiz(self) -> None:
        """Thread-safe: clear any quiz currently on the board."""
        self._win._quiz_hide_sig.emit()

    def show_review(self, title: str, summary: str, findings, unclear=None) -> None:
        """Thread-safe: lay a document review into the panel below the HUD.

        `findings` is a list of {heading, detail, severity, quote, suggestion};
        severity is one of 'serious' / 'caution' / 'note' and decides colour and
        order here, so the caller supplies no styling of its own.
        """
        self._win._review_sig.emit(str(title or ""), str(summary or ""),
                                   list(findings or []), list(unclear or []))

    def prompt_reconfig(self):
        """Thread-safe: show the API key setup overlay (e.g. after an auth error)."""
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        """Thread-safe: show a webcam frame in the small overlay (screen captures)."""
        self._win._camera_sig.emit(img_bytes)

    def start_camera_stream(self) -> None:
        """Thread-safe: start live camera feed in the full HUD area."""
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        """Thread-safe: stop the live camera feed."""
        self._win.stop_camera_stream()

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def pause_audio_core(self) -> bool:
        """Pause the Audio Core (TRON background music engine)."""
        return self._win.pause_audio_core()

    def resume_audio_core(self) -> bool:
        """Resume or play the Audio Core (TRON background music engine)."""
        return self._win.resume_audio_core()

    def set_audio_core_volume(self, volume_percent: int) -> float:
        """Set base volume of the Audio Core (0 to 100)."""
        return self._win.set_audio_core_volume(volume_percent)

    def get_audio_core_status(self) -> dict:
        """Get status of the Audio Core."""
        return self._win.get_audio_core_status()

    def set_spotify_playback(
        self, title: str, artist: str = "", uri: str = "", is_playing: bool = True
    ) -> None:
        """Queue a Spotify track update onto the Qt UI thread."""
        self._win._spotify_playback_sig.emit(title, artist, uri, is_playing)

    def set_spotify_playback_state(self, is_playing: bool) -> None:
        self._win._spotify_state_sig.emit(is_playing)

    # ------------------------------------------------------------------
    # HUD Video — thread-safe proxy methods
    # ------------------------------------------------------------------

    @property
    def hud_video_controller(self):
        """Return the HudVideoController instance (or None if unavailable)."""
        return getattr(self._win, "_hud_video_controller", None)

    def hud_video_stop(self) -> None:
        """Thread-safe: stop HUD video and restore avatar."""
        ctrl = self.hud_video_controller
        if ctrl is not None:
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(ctrl, "stop", Qt.ConnectionType.QueuedConnection)
