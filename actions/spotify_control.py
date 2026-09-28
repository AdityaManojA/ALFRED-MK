# actions/spotify_control.py
"""
Spotify AI Agent & Playback Control for ALFRED.

Provides seamless Spotify integration:
- Lazy initialization of Spotify client
- Connection pooling with requests.Session
- Smart caching of auth tokens, devices, and profile data
- Multi-tier playback execution: Web API with local desktop URI & media key fallbacks
- Synchronizes with ALFRED's bottom-left Tactical Audio Player & background music engine
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False


logger = logging.getLogger("spotify_control")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Windows Virtual Key Codes and App Commands for media controls
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

HWND_BROADCAST = 0xFFFF
WM_APPCOMMAND = 0x0319
APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_MEDIA_PLAY = 46
APPCOMMAND_MEDIA_PAUSE = 47


def _send_app_command(cmd_code: int) -> bool:
    """Sends a native Windows WM_APPCOMMAND message to explicitly Pause, Play, or Stop."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            res = user32.PostMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, cmd_code << 16)
            return bool(res)
        except Exception as e:
            logger.debug(f"WM_APPCOMMAND failed: {e}")
    return False


def _send_media_key(vk_code: int):
    """Sends a native Windows media key event as a hardware-level fallback."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Key down
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.05)
            # Key up
            user32.keybd_event(vk_code, 0, 2, 0)
            return True
        except Exception as e:
            logger.debug(f"Media key simulation failed: {e}")
    if _PYAUTOGUI:
        try:
            if vk_code == VK_MEDIA_PLAY_PAUSE:
                pyautogui.press('playpause')
            elif vk_code == VK_MEDIA_NEXT_TRACK:
                pyautogui.press('nexttrack')
            elif vk_code == VK_MEDIA_PREV_TRACK:
                pyautogui.press('prevtrack')
            return True
        except Exception:
            pass
    return False


class SpotifyClient:
    """
    High-performance Spotify client with connection pooling, token caching,
    device caching, and fallback playback mechanisms.
    """
    _instance: Optional[SpotifyClient] = None
    _lock = threading.Lock()

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._client_id: str = ""
        self._client_secret: str = ""
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_expires_at: float = 0.0

        # Caches
        self._devices_cache: Optional[List[Dict[str, Any]]] = None
        self._devices_cache_time: float = 0.0
        self._devices_ttl: float = 300.0  # 5 minutes

        self._active_device_id: Optional[str] = None
        self._current_track_info: Dict[str, Any] = {}

        self._load_credentials()
        self._init_session()

    @classmethod
    def get_instance(cls) -> SpotifyClient:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_session(self):
        if not _REQUESTS_AVAILABLE:
            return
        self._session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _load_credentials(self):
        """Loads Spotify credentials from config/api_keys.json or environment variables."""
        if API_CONFIG_PATH.exists():
            try:
                with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self._client_id = cfg.get("spotify_client_id", "").strip()
                    self._client_secret = cfg.get("spotify_client_secret", "").strip()
                    self._refresh_token = cfg.get("spotify_refresh_token", "").strip()
                    if cfg.get("spotify_access_token"):
                        self._access_token = cfg.get("spotify_access_token").strip()
            except Exception as e:
                logger.warning(f"Error reading Spotify credentials from {API_CONFIG_PATH}: {e}")

        # Environment variable overrides
        self._client_id = os.environ.get("SPOTIFY_CLIENT_ID", self._client_id)
        self._client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", self._client_secret)
        self._refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", self._refresh_token)
        if os.environ.get("SPOTIFY_ACCESS_TOKEN"):
            self._access_token = os.environ.get("SPOTIFY_ACCESS_TOKEN", self._access_token)

    def get_token(self) -> Optional[str]:
        """Returns a valid access token, refreshing if needed."""
        now = time.time()
        if self._access_token and now < (self._token_expires_at - 60):
            return self._access_token

        # Attempt refresh using refresh_token if present
        if self._refresh_token and self._client_id and self._client_secret:
            token = self._refresh_with_refresh_token()
            if token:
                return token

        # Attempt Client Credentials flow
        if self._client_id and self._client_secret:
            token = self._refresh_client_credentials()
            if token:
                return token

        return self._access_token or None

    def _refresh_client_credentials(self) -> Optional[str]:
        if not self._session:
            return None
        try:
            auth_header = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            resp = self._session.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"grant_type": "client_credentials"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token", "")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in
                return self._access_token
            else:
                logger.debug(f"Spotify client credentials auth failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.warning(f"Error requesting Spotify client credentials token: {e}")
        return None

    def _refresh_with_refresh_token(self) -> Optional[str]:
        if not self._session:
            return None
        try:
            auth_header = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            resp = self._session.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token
                },
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token", "")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in
                if "refresh_token" in data:
                    self._refresh_token = data["refresh_token"]
                return self._access_token
        except Exception as e:
            logger.warning(f"Error refreshing Spotify token: {e}")
        return None

    def _auth_headers(self) -> Dict[str, str]:
        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, search_type: str = "track", limit: int = 5) -> List[Dict[str, Any]]:
        """Search Spotify for tracks, albums, artists, or playlists."""
        if not self._session or not query:
            return []

        token = self.get_token()
        if not token:
            logger.info("No Spotify token available for API search.")
            return []

        valid_types = {"track", "album", "artist", "playlist"}
        stype = search_type.lower().strip()
        if stype not in valid_types:
            stype = "track"

        url = f"https://api.spotify.com/v1/search?q={quote_plus(query)}&type={stype}&limit={limit}"
        try:
            resp = self._session.get(url, headers=self._auth_headers(), timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                key = f"{stype}s"
                items = data.get(key, {}).get("items", [])
                results = []
                for item in items:
                    artists = ", ".join(a["name"] for a in item.get("artists", [])) if "artists" in item else ""
                    album_name = item.get("album", {}).get("name", "")
                    # Extract popularity for sorting (higher is more popular)
                    popularity = item.get("popularity", 0)
                    results.append({
                        "name": item.get("name"),
                        "artist": artists,
                        "album": album_name,
                        "uri": item.get("uri"),
                        "id": item.get("id"),
                        "preview_url": item.get("preview_url"),
                        "external_url": item.get("external_urls", {}).get("spotify", ""),
                        "type": stype,
                        "popularity": popularity
                    })
                return results
            else:
                logger.debug(f"Spotify search failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Spotify search request error: {e}")
        return []

    # ── Playback Controls ───────────────────────────────────────────────────

    def play(
        self,
        query: Optional[str] = None,
        uri: Optional[str] = None,
        context_uri: Optional[str] = None,
        device_id: Optional[str] = None,
        search_type: str = "track"
    ) -> Dict[str, Any]:
        """
        Starts playback of a query, URI, or resumes current playback.
        Attempts Web API first, falls back gracefully to Spotify desktop URI launch.
        """
        track_info = {}
        target_uri = uri or context_uri

        # If a query is provided, find the best match
        if query and not target_uri:
            # Get more results to choose from, then sort by popularity
            results = self.search(query, search_type=search_type, limit=10)
            if results:
                # Sort by popularity (descending) and take the most popular
                results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                top = results[0]
                target_uri = top["uri"]
                track_info = top
            else:
                # If search via API returned nothing (or no API key), format search URI
                clean_q = quote_plus(query)
                target_uri = f"spotify:search:{clean_q}"
                track_info = {"name": query, "artist": "Spotify", "uri": target_uri}

        if not track_info and target_uri:
            track_info = {"name": target_uri, "artist": "", "uri": target_uri}

        self._current_track_info = track_info

        # 1. Try Web API Playback
        token = self.get_token()
        web_api_success = False
        if token and self._session:
            url = "https://api.spotify.com/v1/me/player/play"
            if device_id or self._active_device_id:
                url += f"?device_id={device_id or self._active_device_id}"

            payload: Dict[str, Any] = {}
            if target_uri:
                if ":track:" in target_uri:
                    payload["uris"] = [target_uri]
                else:
                    payload["context_uri"] = target_uri

            try:
                resp = self._session.put(
                    url,
                    headers=self._auth_headers(),
                    data=json.dumps(payload) if payload else None,
                    timeout=5
                )
                if resp.status_code in (200, 204):
                    web_api_success = True
                else:
                    logger.debug(f"Spotify Web API play returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.debug(f"Spotify Web API play request error: {e}")

        # 2. Local Fallback: Open URI in Spotify desktop client or browser
        if not web_api_success:
            if target_uri:
                self._launch_uri(target_uri)
            else:
                # Resume via media key
                _send_media_key(VK_MEDIA_PLAY_PAUSE)

        return {
            "status": "playing",
            "track": track_info.get("name", query or "Track"),
            "artist": track_info.get("artist", ""),
            "uri": target_uri,
            "method": "api" if web_api_success else "local"
        }

    def _launch_uri(self, uri: str):
        """Launches Spotify URI using the operating system handler."""
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", uri])
            else:
                subprocess.Popen(["xdg-open", uri])
        except Exception as e:
            logger.warning(f"Failed to launch Spotify URI '{uri}': {e}")
            if "spotify:search:" in uri:
                q = uri.replace("spotify:search:", "")
                webbrowser.open(f"https://open.spotify.com/search/{q}")

    def control_playback(self, action: str, device_id: Optional[str] = None) -> bool:
        """
        Controls playback: pause, resume, skip_next, skip_previous.
        Combines Spotify Web API with native media key fail-safes.
        """
        act = action.lower().strip()
        token = self.get_token()
        success = False

        if token and self._session:
            endpoint_map = {
                "pause": ("PUT", "https://api.spotify.com/v1/me/player/pause"),
                "resume": ("PUT", "https://api.spotify.com/v1/me/player/play"),
                "play": ("PUT", "https://api.spotify.com/v1/me/player/play"),
                "skip_next": ("POST", "https://api.spotify.com/v1/me/player/next"),
                "next": ("POST", "https://api.spotify.com/v1/me/player/next"),
                "skip_previous": ("POST", "https://api.spotify.com/v1/me/player/previous"),
                "prev": ("POST", "https://api.spotify.com/v1/me/player/previous"),
                "previous": ("POST", "https://api.spotify.com/v1/me/player/previous"),
            }

            if act in endpoint_map:
                method, url = endpoint_map[act]
                if device_id or self._active_device_id:
                    url += f"?device_id={device_id or self._active_device_id}"
                try:
                    resp = self._session.request(method, url, headers=self._auth_headers(), timeout=4)
                    if resp.status_code in (200, 204):
                        success = True
                except Exception as e:
                    logger.debug(f"Web API control '{act}' error: {e}")

        # Native Windows Media Command (explicit Pause vs Play without toggling)
        if not success and sys.platform == "win32":
            cmd_map = {
                "pause": APPCOMMAND_MEDIA_PAUSE,
                "stop": APPCOMMAND_MEDIA_STOP,
                "play": APPCOMMAND_MEDIA_PLAY,
                "resume": APPCOMMAND_MEDIA_PLAY,
                "skip_next": APPCOMMAND_MEDIA_NEXTTRACK,
                "next": APPCOMMAND_MEDIA_NEXTTRACK,
                "skip_previous": APPCOMMAND_MEDIA_PREVIOUSTRACK,
                "prev": APPCOMMAND_MEDIA_PREVIOUSTRACK,
                "previous": APPCOMMAND_MEDIA_PREVIOUSTRACK,
            }
            if act in cmd_map:
                success = _send_app_command(cmd_map[act])

        # Hardware media key fallback if API & APPCOMMAND were not handled
        if not success:
            if act in ("pause", "resume", "play"):
                success = _send_media_key(VK_MEDIA_PLAY_PAUSE)
            elif act in ("skip_next", "next"):
                success = _send_media_key(VK_MEDIA_NEXT_TRACK)
            elif act in ("skip_previous", "prev", "previous"):
                success = _send_media_key(VK_MEDIA_PREV_TRACK)

        return success

    def manage_queue(self, uri: str, action: str = "add", device_id: Optional[str] = None) -> bool:
        """Adds a track to the playback queue."""
        token = self.get_token()
        if not token or not self._session or not uri:
            return False

        if action.lower() == "add":
            url = f"https://api.spotify.com/v1/me/player/queue?uri={quote_plus(uri)}"
            if device_id or self._active_device_id:
                url += f"&device_id={device_id or self._active_device_id}"
            try:
                resp = self._session.post(url, headers=self._auth_headers(), timeout=4)
                return resp.status_code in (200, 204)
            except Exception as e:
                logger.warning(f"Error adding to Spotify queue: {e}")
        return False

    def set_volume(self, percent: int, device_id: Optional[str] = None) -> bool:
        """Sets Spotify volume percentage (0-100)."""
        pct = max(0, min(100, int(percent)))
        token = self.get_token()
        if token and self._session:
            url = f"https://api.spotify.com/v1/me/player/volume?volume_percent={pct}"
            if device_id or self._active_device_id:
                url += f"&device_id={device_id or self._active_device_id}"
            try:
                resp = self._session.put(url, headers=self._auth_headers(), timeout=4)
                if resp.status_code in (200, 204):
                    return True
            except Exception as e:
                logger.debug(f"Web API set_volume error: {e}")
        return False

    def get_devices(self) -> List[Dict[str, Any]]:
        """Returns available Spotify devices with 5-minute TTL caching."""
        now = time.time()
        if self._devices_cache and (now - self._devices_cache_time) < self._devices_ttl:
            return self._devices_cache

        token = self.get_token()
        if not token or not self._session:
            return []

        try:
            resp = self._session.get("https://api.spotify.com/v1/me/player/devices", headers=self._auth_headers(), timeout=4)
            if resp.status_code == 200:
                devs = resp.json().get("devices", [])
                self._devices_cache = devs
                self._devices_cache_time = now
                for d in devs:
                    if d.get("is_active"):
                        self._active_device_id = d.get("id")
                return devs
        except Exception as e:
            logger.debug(f"Error getting Spotify devices: {e}")
        return self._devices_cache or []

    def set_shuffle(self, state: bool, device_id: Optional[str] = None) -> bool:
        """Toggles or sets shuffle mode."""
        token = self.get_token()
        if not token or not self._session:
            return False
        url = f"https://api.spotify.com/v1/me/player/shuffle?state={'true' if state else 'false'}"
        if device_id or self._active_device_id:
            url += f"&device_id={device_id or self._active_device_id}"
        try:
            resp = self._session.put(url, headers=self._auth_headers(), timeout=4)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def set_repeat(self, state: str, device_id: Optional[str] = None) -> bool:
        """Sets repeat mode: 'track', 'context', or 'off'."""
        mode = state.lower().strip()
        if mode not in ("track", "context", "off"):
            mode = "off"
        token = self.get_token()
        if not token or not self._session:
            return False
        url = f"https://api.spotify.com/v1/me/player/repeat?state={mode}"
        if device_id or self._active_device_id:
            url += f"&device_id={device_id or self._active_device_id}"
        try:
            resp = self._session.put(url, headers=self._auth_headers(), timeout=4)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def get_current_playback(self) -> Dict[str, Any]:
        """Returns currently playing track information."""
        token = self.get_token()
        if token and self._session:
            try:
                resp = self._session.get("https://api.spotify.com/v1/me/player", headers=self._auth_headers(), timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data.get("item", {})
                    if item:
                        artists = ", ".join(a["name"] for a in item.get("artists", []))
                        return {
                            "is_playing": data.get("is_playing", False),
                            "name": item.get("name", ""),
                            "artist": artists,
                            "album": item.get("album", {}).get("name", ""),
                            "uri": item.get("uri", ""),
                            "progress_ms": data.get("progress_ms", 0),
                            "duration_ms": item.get("duration_ms", 0),
                        }
            except Exception:
                pass
        return self._current_track_info


# ── Module-level convenience functions ────────────────────────────────────────

def get_spotify_client() -> SpotifyClient:
    return SpotifyClient.get_instance()

def spotify_search(query: str, search_type: str = "track") -> List[Dict[str, Any]]:
    return get_spotify_client().search(query, search_type=search_type)

def start_playback(
    query: Optional[str] = None,
    uri: Optional[str] = None,
    context_uri: Optional[str] = None,
    device_id: Optional[str] = None,
    player=None
) -> Dict[str, Any]:
    client = get_spotify_client()
    res = client.play(query=query, uri=uri, context_uri=context_uri, device_id=device_id)
    # Sync with ALFRED UI's Tactical Audio Player if available
    if player and hasattr(player, "set_spotify_playback"):
        track_name = res.get("track", query or "Track")
        artist = res.get("artist", "")
        track_uri = res.get("uri", "")
        player.set_spotify_playback(track_name, artist, track_uri)
    return res

def control_playback(action: str, device_id: Optional[str] = None) -> bool:
    return get_spotify_client().control_playback(action, device_id=device_id)

def manage_queue(uri: str, action: str = "add", device_id: Optional[str] = None) -> bool:
    return get_spotify_client().manage_queue(uri, action=action, device_id=device_id)

def set_volume(percent: int, device_id: Optional[str] = None) -> bool:
    return get_spotify_client().set_volume(percent, device_id=device_id)

def get_devices() -> List[Dict[str, Any]]:
    return get_spotify_client().get_devices()

def set_shuffle(state: bool, device_id: Optional[str] = None) -> bool:
    return get_spotify_client().set_shuffle(state, device_id=device_id)

def set_repeat(state: str, device_id: Optional[str] = None) -> bool:
    return get_spotify_client().set_repeat(state, device_id=device_id)


# ── Action Debounce & Call Deduplication ────────────────────────────────────
_call_lock = threading.Lock()
_last_action = ""
_last_query = ""
_last_call_time = 0.0
_CALL_DEBOUNCE_SEC = 1.5


def spotify_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    Main handler for the spotify_control action.
    """
    global _last_action, _last_query, _last_call_time

    params = parameters or {}
    action = params.get("action", "play").lower().strip()
    query = params.get("query", "").strip()
    uri = params.get("uri", "").strip()
    device_id = params.get("device_id")
    search_type = params.get("search_type", "track").strip()

    # Debounce duplicate calls within 1.5 seconds
    with _call_lock:
        now = time.time()
        if (action == _last_action and query == _last_query and (now - _last_call_time) < _CALL_DEBOUNCE_SEC):
            print(f"[Spotify] Coalescing duplicate action '{action}' (query='{query}')")
            return f"Spotify {action} request already executed, sir."
        _last_action = action
        _last_query = query
        _last_call_time = now

    if player and hasattr(player, "write_log"):
        player.write_log(f"[Spotify] Action: {action} query='{query}' uri='{uri}'")
    print(f"[Spotify] Action: {action} | Query: '{query}' | Params: {params}")

    client = get_spotify_client()

    try:
        if action in ("play", "start"):
            res = client.play(
                query=query if query else None,
                uri=uri if uri else None,
                device_id=device_id,
                search_type=search_type
            )
            track_title = res.get("track", query or "Spotify Track")
            artist = res.get("artist", "")
            track_uri = res.get("uri", uri)

            # Update Tactical Audio Player deck on MainWindow
            if player:
                if hasattr(player, "set_spotify_playback"):
                    player.set_spotify_playback(track_title, artist, track_uri)
                elif hasattr(player, "_bg_music") and player._bg_music:
                    player._bg_music.set_spotify_playback(track_title, artist, track_uri)

            return f"Playing {track_title}" + (f" by {artist}" if artist else "") + " on Spotify, sir."

        elif action in ("pause", "stop"):
            if "audio core" in query.lower() or "tron" in query.lower():
                if player:
                    if hasattr(player, "pause_audio_core"):
                        player.pause_audio_core()
                    elif hasattr(player, "_bg_music") and player._bg_music:
                        player._bg_music.pause()
                return "Audio Core paused, sir."

            client.control_playback("pause", device_id=device_id)
            if player and hasattr(player, "_bg_music") and player._bg_music:
                player._bg_music.pause()
            return "Spotify playback paused, sir."

        elif action in ("resume", "unpause"):
            if "audio core" in query.lower() or "tron" in query.lower():
                if player:
                    if hasattr(player, "resume_audio_core"):
                        player.resume_audio_core()
                    elif hasattr(player, "_bg_music") and player._bg_music:
                        player._bg_music.play()
                return "Audio Core resumed, sir."

            client.control_playback("resume", device_id=device_id)
            if player and hasattr(player, "_bg_music") and player._bg_music:
                player._bg_music.play()
            return "Resuming Spotify playback, sir."

        elif action in ("skip_next", "next"):
            client.control_playback("skip_next", device_id=device_id)
            return "Skipped to next track, sir."

        elif action in ("skip_previous", "prev", "previous"):
            client.control_playback("skip_previous", device_id=device_id)
            return "Returning to previous track, sir."

        elif action in ("close", "exit", "quit", "kill"):
            # Terminate Spotify desktop processes safely
            try:
                import psutil
                for proc in psutil.process_iter(['name']):
                    pname = (proc.info['name'] or '').lower()
                    if 'spotify' in pname:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
            except Exception:
                if sys.platform == "win32":
                    subprocess.Popen(["taskkill", "/F", "/IM", "Spotify.exe", "/T"], shell=False)

            if player:
                if hasattr(player, "restore_tron_music"):
                    player.restore_tron_music()
                elif hasattr(player, "_bg_music") and player._bg_music:
                    player._bg_music.clear_spotify_and_restore_tron()

            return "Spotify has been closed and the default TRON background score restored, sir."

        elif action in ("queue", "add_to_queue"):
            if not uri and query:
                # Get more results to choose from, then sort by popularity
                results = client.search(query, search_type="track", limit=10)
                if results:
                    # Sort by popularity (descending) and take the most popular
                    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                    uri = results[0]["uri"]
            if uri:
                ok = client.manage_queue(uri, action="add", device_id=device_id)
                return "Added track to Spotify queue, sir." if ok else "Could not add track to queue, sir."
            else:
                return "Please specify a song or URI to add to the queue, sir."

        elif action in ("set_volume", "volume"):
            vol = params.get("volume_percent", 50)
            client.set_volume(int(vol), device_id=device_id)
            return f"Spotify volume set to {vol}%, sir."

        elif action in ("get_devices", "devices", "list_devices"):
            devs = client.get_devices()
            if devs:
                dev_names = [f"{d['name']} ({d['type']})" + (" [ACTIVE]" if d.get('is_active') else "") for d in devs]
                return "Available Spotify devices: " + ", ".join(dev_names)
            else:
                return "No active Spotify devices found, sir. Please open Spotify on your device."

        elif action in ("shuffle", "set_shuffle"):
            state_val = str(params.get("state", "true")).lower() in ("true", "1", "yes", "on")
            client.set_shuffle(state_val, device_id=device_id)
            return f"Spotify shuffle mode {'enabled' if state_val else 'disabled'}, sir."

        elif action in ("repeat", "set_repeat"):
            repeat_val = str(params.get("state", "off")).lower()
            client.set_repeat(repeat_val, device_id=device_id)
            return f"Spotify repeat mode set to {repeat_val}, sir."

        elif action in ("search", "find"):
            results = client.search(query, search_type=search_type, limit=5)
            if not results:
                return f"No Spotify results found for '{query}', sir."
            else:
                lines = [f"Spotify search results for '{query}':"]
                for i, r in enumerate(results, 1):
                    popularity = r.get('popularity', 0)
                    lines.append(f"{i}. {r['name']} — {r['artist']} [Popularity: {popularity}/100] ({r['uri']})")
                return "\n".join(lines)

        elif action in ("current_track", "what_is_playing", "now_playing"):
            cur = client.get_current_playback()
            if cur and cur.get("name"):
                return f"Currently playing: {cur['name']} by {cur.get('artist', 'Unknown')}."
            else:
                return "No Spotify track currently reported as playing, sir."

        elif action in ("restore_tron", "tron_music", "default_music"):
            if player:
                if hasattr(player, "restore_tron_music"):
                    player.restore_tron_music()
                elif hasattr(player, "_bg_music") and player._bg_music:
                    player._bg_music.clear_spotify_and_restore_tron()
            return "Restored default TRON Legacy background score, sir."

        else:
            return f"Unknown Spotify action: '{action}'. Available: play, pause, resume, next, prev, queue, set_volume, get_devices, shuffle, repeat, search, current_track, close, restore_tron."

    except Exception as e:
        logger.error(f"Error executing Spotify action '{action}': {e}", exc_info=True)
        return f"Spotify action '{action}' encountered an issue, sir: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "spotify_control",
    "description": (
        "Controls Spotify playback, search, and queue. By default, requests to play songs or music target Spotify. "
        "Use for: playing songs/tracks/albums/playlists, pause, resume, skip next, skip previous, volume, queue management, "
        "closing Spotify, and restoring the default TRON Legacy background score."
    ),
    "scheduling": "WHEN_IDLE",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "play | pause | resume | next | prev | queue | set_volume | "
                    "get_devices | shuffle | repeat | search | current_track | close | restore_tron (default: play)"
                )
            },
            "query": {
                "type": "STRING",
                "description": "Song name, artist, album, or playlist search query"
            },
            "search_type": {
                "type": "STRING",
                "description": "track | album | artist | playlist (default: track)"
            },
            "uri": {
                "type": "STRING",
                "description": "Spotify URI (e.g. spotify:track:..., spotify:album:..., spotify:playlist:...)"
            },
            "device_id": {
                "type": "STRING",
                "description": "Optional target Spotify device ID"
            },
            "volume_percent": {
                "type": "INTEGER",
                "description": "Volume percentage 0 to 100"
            },
            "state": {
                "type": "STRING",
                "description": "For shuffle: 'true'/'false'. For repeat: 'track'|'context'|'off'"
            }
        },
        "required": []
    },
    "handler": spotify_control,
}


# ── Interactive OAuth Authorization Flow ─────────────────────────────────────

import http.server
import urllib.parse


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    auth_error: Optional[str] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                _OAuthCallbackHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = (
                    "<html><body style='font-family:sans-serif;background:#0d1117;color:#58a6ff;text-align:center;padding:50px;'>"
                    "<h2>ALFRED Spotify Authorization Successful!</h2>"
                    "<p style='color:#c9d1d9;'>Your user authorization token has been captured. Direct Web API playback is now fully unlocked.</p>"
                    "<p style='color:#8b949e;'>You can close this tab and return to ALFRED.</p>"
                    "</body></html>"
                )
                self.wfile.write(html.encode("utf-8"))
            elif "error" in params:
                _OAuthCallbackHandler.auth_error = params["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Authorization failed or was denied.")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def authorize_user(port: int = 8888) -> bool:
    """
    Launches browser for Spotify User Authorization (OAuth 2.0 PKCE / Authorization Code),
    listens on http://127.0.0.1:8888/callback, exchanges the code for a refresh token,
    and saves it to config/api_keys.json.
    """
    client = get_spotify_client()
    client_id = client._client_id
    client_secret = client._client_secret
    if not client_id or not client_secret:
        print("[Spotify] Missing spotify_client_id or spotify_client_secret in config/api_keys.json")
        return False

    redirect_uri = f"http://127.0.0.1:{port}/callback"
    scopes = [
        "user-modify-playback-state",
        "user-read-playback-state",
        "user-read-currently-playing",
        "streaming",
        "playlist-read-private",
        "app-remote-control"
    ]
    scope_str = quote_plus(" ".join(scopes))
    auth_url = (
        f"https://accounts.spotify.com/authorize?"
        f"client_id={client_id}&response_type=code&redirect_uri={quote_plus(redirect_uri)}&scope={scope_str}"
    )

    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.auth_error = None

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
        server.timeout = 120
    except Exception as e:
        print(f"[Spotify] Could not bind local callback server on port {port}: {e}")
        return False

    print(f"[Spotify] Opening browser for Spotify User Authorization...")
    webbrowser.open(auth_url)

    while _OAuthCallbackHandler.auth_code is None and _OAuthCallbackHandler.auth_error is None:
        server.handle_request()

    server.server_close()

    code = _OAuthCallbackHandler.auth_code
    if not code:
        print(f"[Spotify] Authorization failed: {_OAuthCallbackHandler.auth_error}")
        return False

    # Exchange authorization code for user-scoped tokens
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            refresh_token = data.get("refresh_token")
            access_token = data.get("access_token")
            if refresh_token and API_CONFIG_PATH.exists():
                cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                cfg["spotify_refresh_token"] = refresh_token
                if access_token:
                    cfg["spotify_access_token"] = access_token
                API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
                print("\n[Spotify] Authorization successful!")
                print("[Spotify] spotify_refresh_token has been saved to config/api_keys.json.")
                print("[Spotify] Direct Web API playback is now active!\n")
                client._refresh_token = refresh_token
                client._access_token = access_token or ""
                client._token_expires_at = time.time() + data.get("expires_in", 3600)
                return True
        else:
            print(f"[Spotify] Token exchange failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"[Spotify] Error during token exchange: {e}")
    return False


if __name__ == "__main__":
    print("Initiating Spotify User Authorization...")
    authorize_user()
