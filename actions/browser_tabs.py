"""Tabs in the user's real browsers (Safari, Chrome, Brave, Edge, Arc, Vivaldi, Opera, Firefox),
and YouTube playback that pauses every other YouTube video."""
from core.mac import require_mac

require_mac()

from urllib.parse import quote_plus                    # noqa: E402

from core.mac import browsers as br                    # noqa: E402
from core.mac.osa import OSAError                      # noqa: E402
from core.mac.tooling import B, N, S, tool             # noqa: E402

_ACTIONS = ["list", "current", "switch", "open", "close", "reload", "back", "forward",
            "pause_video", "play_video", "pause_all_videos", "play_youtube", "focus"]


def _pick(p, browser):
    """The tab a request refers to: by query, by browser+index, else the active one."""
    query = str(p.get("query") or "").strip()
    if query:
        tab = br.find_tab(query, browser)
        if tab is None:
            raise OSAError(f"No open tab matches “{query}”.")
        return tab
    idx = p.get("index")
    if idx not in (None, ""):
        tabs = [t for t in br.list_tabs(browser) if "error" not in t]
        win = int(p.get("window") or 1)
        for t in tabs:
            if t["index"] == int(idx) and t["window"] == win:
                return t
        raise OSAError(f"There's no tab {idx} in that window.")
    tab = br.active_tab(browser)
    if tab is None:
        raise OSAError("No browser window is open.")
    return tab


def _url(text: str) -> str:
    t = text.strip()
    if "://" in t or t.startswith(("about:", "chrome:", "file:")):
        return t
    if " " not in t and "." in t:
        return "https://" + t
    return "https://www.google.com/search?q=" + quote_plus(t)


@tool
def browser_tabs(p, **_):
    a = str(p.get("action", "")).lower().strip()
    browser = br.resolve(p.get("browser"))
    if p.get("browser") and browser is None:
        return f"I don't know a browser called {p.get('browser')}."

    if a == "list":
        tabs = br.list_tabs(browser)
        if not tabs:
            return "No supported browser is open." if not browser else f"{br.BROWSERS[browser]['app']} isn't open."
        rows = [t if "error" in t else
                {"browser": t["browser"], "window": t["window"], "index": t["index"],
                 "title": t["title"][:90], "url": t["url"][:120], **({"active": True} if t["active"] else {})}
                for t in tabs]
        return {"count": len(rows), "tabs": rows[:80]}
    if a == "current":
        tab = br.active_tab(browser)
        return tab or "No browser window is open."
    if a == "switch":
        return br.switch_to(_pick(p, browser))
    if a == "open":
        target = str(p.get("url") or p.get("query") or "").strip()
        if not target:
            return "Tell me what to open."
        r = br.new_tab(_url(target), browser or br.default_browser(), background=bool(p.get("background")))
        return f"Opened {r['url']} in {br.BROWSERS[r['browser']]['app']}."
    if a == "close":
        return br.close_tab(_pick(p, browser))
    if a in ("reload", "back", "forward"):
        return br.navigate(_pick(p, browser), a)
    if a == "pause_video":
        n = br.run_js(_pick(p, browser), br.PAUSE_JS)
        return "Paused." if n.strip('"') not in ("0", "") else "Nothing was playing in that tab."
    if a == "play_video":
        r = br.run_js(_pick(p, browser), br.PLAY_JS)
        return "Playing." if "playing" in r else "There's no video in that tab."
    if a == "pause_all_videos":
        r = br.media_all(br.PAUSE_JS, only_youtube=not p.get("all_sites"))
        out = {"paused": r["affected"]}
        if r["blocked"]:
            out["blocked"] = r["blocked"]
        return out
    if a == "play_youtube":
        q = str(p.get("query") or "").strip()
        url = str(p.get("url") or "").strip()
        if not q and not url:
            return "Tell me what to play."
        return br.play_youtube(query=q, url=url, browser=browser, reuse_tab=bool(p.get("reuse_tab")))
    if a == "focus":
        return br.switch_to(_pick(p, browser))
    return f"Unknown action. Use one of: {', '.join(_ACTIONS)}."


TOOL = {
    "name": "browser_tabs",
    "description": ("Control tabs in the user's real browsers (Safari, Chrome, Brave, Edge, Arc, Vivaldi, Opera, Firefox): "
                    "list, switch to a tab by name, open URLs/searches in new tabs, close, reload, back/forward, "
                    "pause/play a tab's video, and play_youtube — plays a YouTube video and pauses all other YouTube videos."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", _ACTIONS),
        "browser": S("safari, chrome, brave, edge, arc, vivaldi, opera or firefox. Omit for all running "
                     "browsers (list) / the frontmost or default browser (others)."),
        "query": S("Words from the tab's title or URL (switch/close/pause…), a search or site (open), "
                   "or what to watch (play_youtube)."),
        "url": S("Exact URL to open or play."),
        "index": N("Tab number (1 = leftmost) as shown by list, used with window."),
        "window": N("Window number from list (1 = frontmost). Default 1."),
        "reuse_tab": B("play_youtube: navigate an existing YouTube tab instead of opening a new one."),
        "background": B("open: don't switch to the new tab."),
        "all_sites": B("pause_all_videos: pause media on every site, not only YouTube."),
    }, "required": ["action"]},
    "handler": browser_tabs,
}
