"""Now-playing control: Music, Spotify, browsers — plus 'pause everything'."""
from core.mac import require_mac

require_mac()

from core.mac import apps, browsers                   # noqa: E402
from core.mac.system import media_key                 # noqa: E402
from core.mac.tooling import S, tool                  # noqa: E402


@tool
def mac_media(p, **_):
    a = str(p.get("action", "")).lower().strip()
    app = p.get("app")
    if a in ("play", "pause", "toggle", "next", "previous"):
        if (app or "").lower() in ("system", "any", "browser"):
            return media_key({"play": "play_pause", "pause": "play_pause", "toggle": "play_pause"}.get(a, a))
        return apps.music_control(a, app)
    if a == "now_playing":
        return apps.now_playing()
    if a == "play_music":
        q = str(p.get("query") or "").strip()
        if (app or "").lower() == "spotify" and q.startswith("spotify:"):
            return apps.spotify_play_uri(q)
        return apps.music_play(q)
    if a == "pause_everything":
        done = []
        for name in ("Music", "Spotify"):
            try:
                apps.music_control("pause", name)
                done.append(name)
            except Exception:
                pass
        vids = browsers.media_all(browsers.PAUSE_JS, only_youtube=False)
        browsers._pause_hud_video()
        out = {"paused_apps": done, "paused_browser_media": vids["affected"]}
        if vids["blocked"]:
            out["browsers_needing_permission"] = vids["blocked"]
        return out
    return "Unknown action. Use play, pause, toggle, next, previous, now_playing, play_music or pause_everything."


TOOL = {
    "name": "mac_media",
    "description": ("Media on this Mac: play/pause/next/previous (Music, Spotify, or whatever owns the media keys), "
                    "what's playing now, play a song/artist/playlist from the Music library, pause everything."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["play", "pause", "toggle", "next", "previous", "now_playing",
                                    "play_music", "pause_everything"]),
        "app": S("Optional: 'music', 'spotify', or 'system' to send the hardware media key instead."),
        "query": S("For play_music: song, artist, album or playlist name (or a spotify: URI with app=spotify)."),
    }, "required": ["action"]},
    "handler": mac_media,
}
