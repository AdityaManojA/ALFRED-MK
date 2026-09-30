"""Tab control for the user's real browsers, plus exclusive YouTube playback.

Safari, the Chromium family (Chrome, Brave, Edge, Vivaldi, Opera, Chromium)
and Arc are driven through their AppleScript dictionaries via JXA, using bulk
property reads (one Apple event per window rather than per tab). Firefox has
no tab dictionary, so it gets URL opening, tab listing from its session file
and keyboard switching.

Nothing here launches a browser just to look at it: listing and switching only
touch browsers that are already running.

Running JavaScript in a tab (pausing a video) additionally needs the browser's
"Allow JavaScript from Apple Events" switch; when it is off the error says
exactly where it is.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote_plus

from core.mac.osa import OSAError, is_running, jxa

BROWSERS = {
    "safari":   {"app": "Safari",         "bundle": "com.apple.Safari",           "kind": "safari"},
    "chrome":   {"app": "Google Chrome",  "bundle": "com.google.Chrome",          "kind": "chromium"},
    "brave":    {"app": "Brave Browser",  "bundle": "com.brave.Browser",          "kind": "chromium"},
    "edge":     {"app": "Microsoft Edge", "bundle": "com.microsoft.edgemac",      "kind": "chromium"},
    "arc":      {"app": "Arc",            "bundle": "company.thebrowser.Browser", "kind": "arc"},
    "vivaldi":  {"app": "Vivaldi",        "bundle": "com.vivaldi.Vivaldi",        "kind": "chromium"},
    "opera":    {"app": "Opera",          "bundle": "com.operasoftware.Opera",    "kind": "chromium"},
    "chromium": {"app": "Chromium",       "bundle": "org.chromium.Chromium",      "kind": "chromium"},
    "firefox":  {"app": "Firefox",        "bundle": "org.mozilla.firefox",        "kind": "firefox"},
}
_ALIASES = {"google chrome": "chrome", "google": "chrome", "microsoft edge": "edge", "brave browser": "brave",
            "ff": "firefox", "mozilla": "firefox", "apple": "safari"}

_JS_HELP = {
    "safari": "Safari: Settings → Advanced → tick “Show features for web developers”, then "
              "Develop → Developer Settings… → “Allow JavaScript from Apple Events”.",
    "chromium": "{app}: View → Developer → “Allow JavaScript from Apple Events”.",
    "arc": "Arc: View → Developer → “Allow JavaScript from Apple Events”.",
}

YOUTUBE_RE = re.compile(r"https?://([a-z0-9-]+\.)?(youtube\.com|youtu\.be)/", re.I)

# Installed into every YouTube tab: when a video starts in one tab, every other
# tab of the same browser pauses. BroadcastChannel is same-origin and in-page,
# so this costs nothing and needs no polling.
EXCLUSIVE_JS = r"""(function(){
  if (window.__alfredExclusive) return 'present';
  window.__alfredExclusive = true;
  var me = Math.random().toString(36).slice(2);
  var ch = new BroadcastChannel('alfred-exclusive-media');
  document.addEventListener('play', function(){ ch.postMessage(me); }, true);
  ch.onmessage = function(m){
    if (m.data === me) return;
    document.querySelectorAll('video,audio').forEach(function(v){ if (!v.paused) v.pause(); });
  };
  return 'installed';
})()"""

PAUSE_JS = r"""(function(){var n=0;document.querySelectorAll('video,audio').forEach(function(v){if(!v.paused){v.pause();n++;}});return String(n);})()"""
PLAY_JS = r"""(function(){var v=document.querySelector('video');if(!v)return 'none';v.play();return 'playing';})()"""


def resolve(name: str | None) -> str | None:
    if not name:
        return None
    k = name.lower().strip()
    k = _ALIASES.get(k, k)
    if k in BROWSERS:
        return k
    for key, b in BROWSERS.items():
        if k in b["app"].lower():
            return key
    return None


def installed(key: str) -> bool:
    from AppKit import NSWorkspace
    return NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(BROWSERS[key]["bundle"]) is not None


def running() -> list[str]:
    return [k for k, b in BROWSERS.items() if is_running(b["bundle"])]


def default_browser() -> str:
    try:
        from AppKit import NSWorkspace
        from Foundation import NSURL, NSBundle
        url = NSWorkspace.sharedWorkspace().URLForApplicationToOpenURL_(NSURL.URLWithString_("https://example.com"))
        bid = NSBundle.bundleWithURL_(url).bundleIdentifier() if url else ""
        for k, b in BROWSERS.items():
            if b["bundle"] == bid:
                return k
    except Exception:
        pass
    return "safari"


def _app(key: str) -> str:
    return json.dumps(BROWSERS[key]["app"])


# ── Listing ──────────────────────────────────────────────────────────────────

def _list_js(key: str) -> str:
    kind = BROWSERS[key]["kind"]
    if kind == "safari":
        body = "var t=w.tabs.name(),u=w.tabs.url(),a=w.currentTab().index();"
    elif kind == "arc":
        body = "var t=w.tabs.title(),u=w.tabs.url(),ids=w.tabs.id(),a=ids.indexOf(w.activeTab.id())+1;"
    else:
        body = "var t=w.tabs.title(),u=w.tabs.url(),a=w.activeTabIndex();"
    return (f"(function(){{var app=Application({_app(key)});var out=[];var ws=app.windows();"
            f"for(var i=0;i<ws.length;i++){{var w=ws[i];try{{{body}"
            f"out.push({{wid:w.id(),t:t,u:u,a:a}});}}catch(e){{}}}}return JSON.stringify(out);}})()")


def _firefox_tabs() -> list[dict]:
    """Firefox writes its open tabs to an lz4 'mozlz4' session file every few seconds."""
    try:
        import lz4.block
    except ImportError:
        return []
    out = []
    for f in (Path.home() / "Library/Application Support/Firefox/Profiles").glob("*/sessionstore-backups/recovery.jsonlz4"):
        try:
            raw = f.read_bytes()
            data = json.loads(lz4.block.decompress(raw[8:]))
        except Exception:
            continue
        for wi, w in enumerate(data.get("windows", [])):
            sel = w.get("selected", 1)
            for ti, tab in enumerate(w.get("tabs", []), start=1):
                entries = tab.get("entries") or [{}]
                e = entries[max(0, min(len(entries), tab.get("index", 1)) - 1)]
                out.append({"browser": "firefox", "window": wi + 1, "window_id": wi, "index": ti,
                            "title": e.get("title", ""), "url": e.get("url", ""), "active": ti == sel})
    return out


def list_tabs(browser: str | None = None) -> list[dict]:
    keys = [browser] if browser else running()
    tabs: list[dict] = []
    for key in keys:
        if not is_running(BROWSERS[key]["bundle"]):
            continue
        if BROWSERS[key]["kind"] == "firefox":
            tabs += _firefox_tabs()
            continue
        try:
            wins = jxa(_list_js(key), app=BROWSERS[key]["app"]) or []
        except OSAError as e:
            tabs.append({"browser": key, "error": str(e)})
            continue
        for wi, w in enumerate(wins, start=1):
            for ti, (t, u) in enumerate(zip(w["t"], w["u"]), start=1):
                tabs.append({"browser": key, "window": wi, "window_id": w["wid"], "index": ti,
                             "title": t or "", "url": u or "", "active": ti == w["a"]})
    return tabs


def _score(tab: dict, query: str) -> float:
    ql = query.lower().strip()
    hay = f"{tab.get('title', '')} {tab.get('url', '')}".lower()
    if not ql:
        return 0
    if ql in hay:
        return 10 + (5 if ql in tab.get("title", "").lower() else 0)
    words = [w for w in re.findall(r"[a-z0-9]+", ql) if len(w) > 1]
    if not words:
        return 0
    return sum(1 for w in words if w in hay) / len(words) * 8


def find_tab(query: str, browser: str | None = None) -> dict | None:
    tabs = [t for t in list_tabs(browser) if "error" not in t]
    scored = sorted(((_score(t, query), t) for t in tabs), key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] >= 4 else None


# ── Acting on tabs ───────────────────────────────────────────────────────────

def _tab_expr(key: str, tab: dict) -> str:
    return f"app.windows.byId({json.dumps(tab['window_id'])}).tabs[{tab['index'] - 1}]"


def switch_to(tab: dict) -> str:
    key = tab["browser"]
    kind = BROWSERS[key]["kind"]
    if kind == "firefox":
        subprocess.run(["open", "-a", "Firefox"])
        if tab["index"] <= 8:
            from core.mac.osa import applescript
            applescript(f'delay 0.3\ntell application "System Events" to keystroke "{tab["index"]}" using command down',
                        app="System Events")
        return f"Switched to Firefox tab {tab['index']}."
    w = f"app.windows.byId({json.dumps(tab['window_id'])})"
    if kind == "safari":
        act = f"var w={w};w.currentTab=w.tabs[{tab['index'] - 1}];w.index=1;"
    elif kind == "arc":
        act = f"var w={w};w.tabs[{tab['index'] - 1}].select();w.index=1;"
    else:
        act = f"var w={w};w.activeTabIndex={tab['index']};w.index=1;"
    jxa(f"(function(){{var app=Application({_app(key)});{act}app.activate();return 'ok';}})()", app=BROWSERS[key]["app"])
    return f"Switched to “{tab['title'][:80]}” in {BROWSERS[key]['app']}."


def new_tab(url: str, browser: str | None = None, background: bool = False) -> dict:
    key = browser or default_browser()
    b = BROWSERS[key]
    if b["kind"] == "firefox" or not installed(key):
        subprocess.run(["open", "-a", b["app"], url] if installed(key) else ["open", url])
        return {"browser": key, "url": url}
    if b["kind"] == "safari":
        body = (f"if(app.windows.length===0){{app.Document().make();delay(0.4);app.windows[0].currentTab.url={json.dumps(url)};}}"
                f"else{{var w=app.windows[0];w.tabs.push(app.Tab({{url:{json.dumps(url)}}}));"
                + ("" if background else "w.currentTab=w.tabs[w.tabs.length-1];") + "}")
    elif b["kind"] == "arc":
        body = (f"if(app.windows.length===0){{app.Window().make();delay(0.4);}}"
                f"var w=app.windows[0];w.tabs.push(app.Tab({{url:{json.dumps(url)}}}));")
    else:
        body = (f"if(app.windows.length===0){{app.Window().make();delay(0.4);}}"
                f"var w=app.windows[0];w.tabs.push(app.Tab({{url:{json.dumps(url)}}}));"
                + ("" if background else "w.activeTabIndex=w.tabs.length;"))
    was_running = is_running(b["bundle"])
    if not was_running:
        subprocess.run(["open", "-g", "-a", b["app"]])
        time.sleep(1.2)
    jxa(f"(function(){{var app=Application({_app(key)});{body}"
        + ("" if background else "app.activate();") + "return 'ok';})()", app=b["app"], timeout=20)
    return {"browser": key, "url": url}


def close_tab(tab: dict) -> str:
    key = tab["browser"]
    if BROWSERS[key]["kind"] == "firefox":
        switch_to(tab)
        from core.mac.osa import applescript
        applescript('tell application "System Events" to keystroke "w" using command down', app="System Events")
    else:
        jxa(f"(function(){{var app=Application({_app(key)});{_tab_expr(key, tab)}.close();return 'ok';}})()",
            app=BROWSERS[key]["app"])
    return f"Closed “{tab['title'][:80]}”."


def active_tab(browser: str | None = None) -> dict | None:
    """The tab the user is looking at: frontmost window of the given (or frontmost) browser."""
    from core.mac.system import frontmost
    if browser is None:
        bid = frontmost().get("bundle_id")
        browser = next((k for k, b in BROWSERS.items() if b["bundle"] == bid), None)
        browser = browser or (running()[0] if running() else None)
    if browser is None:
        return None
    tabs = [t for t in list_tabs(browser) if t.get("active") and "error" not in t]
    return min(tabs, key=lambda t: t["window"]) if tabs else None


def run_js(tab: dict, code: str) -> str:
    key = tab["browser"]
    kind = BROWSERS[key]["kind"]
    if kind == "firefox":
        raise OSAError("Firefox can't run scripts from other apps.")
    if kind == "safari":
        call = f"app.doJavaScript({json.dumps(code)},{{in:{_tab_expr(key, tab)}}})"
    else:
        call = f"{_tab_expr(key, tab)}.execute({{javascript:{json.dumps(code)}}})"
    try:
        res = jxa(f"(function(){{var app=Application({_app(key)});return JSON.stringify(String({call}));}})()",
                  app=BROWSERS[key]["app"])
    except OSAError as e:
        if "javascript" in str(e).lower() or "apple events" in str(e).lower():
            raise OSAError("JavaScript from Apple Events is turned off. " + js_help(key))
        raise
    return str(res)


def js_help(key: str) -> str:
    b = BROWSERS[key]
    return _JS_HELP.get(b["kind"], "").format(app=b["app"])


def navigate(tab: dict, action: str) -> str:
    key = tab["browser"]
    kind = BROWSERS[key]["kind"]
    if kind in ("chromium", "arc") and action in ("reload", "back", "forward"):
        meth = {"reload": "reload", "back": "goBack", "forward": "goForward"}[action]
        jxa(f"(function(){{var app=Application({_app(key)});{_tab_expr(key, tab)}.{meth}();return 'ok';}})()",
            app=BROWSERS[key]["app"])
    elif kind == "safari" and action == "reload":
        jxa(f"(function(){{var app=Application({_app(key)});var t={_tab_expr(key, tab)};t.url=t.url();return 'ok';}})()",
            app="Safari")
    else:
        run_js(tab, {"reload": "location.reload()", "back": "history.back()", "forward": "history.forward()"}[action])
    return f"{action.capitalize()} done."


# ── Media across tabs ────────────────────────────────────────────────────────

def _media_script(key: str, js: str, only_youtube: bool, skip_url: str | None) -> str:
    kind = BROWSERS[key]["kind"]
    exec_ = (f"app.doJavaScript({json.dumps(js)},{{in:t}})" if kind == "safari"
             else f"t.execute({{javascript:{json.dumps(js)}}})")
    urlprop = "w.tabs.url()"
    test = "/(youtube\\.com|youtu\\.be)\\//i.test(u[j])" if only_youtube else "/^https?:/.test(u[j])"
    skip = f"&&u[j]!=={json.dumps(skip_url)}" if skip_url else ""
    return (f"(function(){{var app=Application({_app(key)});var r={{done:0,err:''}};var ws=app.windows();"
            f"for(var i=0;i<ws.length;i++){{var w=ws[i];var u;try{{u={urlprop};}}catch(e){{continue;}}"
            f"for(var j=0;j<u.length;j++){{if({test}{skip}){{var t=w.tabs[j];"
            f"try{{var x={exec_};if(x&&x!=='0'&&x!=='none')r.done+=(parseInt(x)||1);}}catch(e){{r.err=String(e);}}}}}}}}"
            f"return JSON.stringify(r);}})()")


def media_all(js: str, only_youtube: bool = True, skip_url: str | None = None,
              browsers: list[str] | None = None) -> dict:
    """Run `js` in matching tabs of every running scriptable browser."""
    result = {"affected": 0, "blocked": []}
    for key in browsers or running():
        if BROWSERS[key]["kind"] == "firefox":
            continue
        try:
            r = jxa(_media_script(key, js, only_youtube, skip_url), app=BROWSERS[key]["app"]) or {}
        except OSAError as e:
            result["blocked"].append({"browser": key, "reason": str(e)})
            continue
        result["affected"] += int(r.get("done", 0))
        err = str(r.get("err", ""))
        if err and ("javascript" in err.lower() or "apple events" in err.lower()):
            result["blocked"].append({"browser": key, "reason": "JavaScript from Apple Events is off. " + js_help(key)})
    return result


def pause_other_youtube(except_url: str | None = None) -> dict:
    return media_all(PAUSE_JS, only_youtube=True, skip_url=except_url)


def install_exclusive(browsers: list[str] | None = None) -> dict:
    return media_all(EXCLUSIVE_JS, only_youtube=True, browsers=browsers)


# ── YouTube ─────────────────────────────────────────────────────────────────

def find_video(query: str) -> str | None:
    """First non-Shorts result for a search, as a watch URL."""
    import requests
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAQ%3D%3D"
    try:
        html = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"}).text
    except Exception:
        return None
    seen = set()
    for vid in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html):
        if vid in seen or f"/shorts/{vid}" in html:
            seen.add(vid)
            continue
        return f"https://www.youtube.com/watch?v={vid}"
    return None


def _pause_hud_video() -> None:
    try:
        from core.registry import lookup
        ui = lookup("mac_ui")
        if ui is not None:
            ui.pause_hud_video()
    except Exception:
        pass


def play_youtube(query: str = "", url: str = "", browser: str | None = None, reuse_tab: bool = False) -> dict:
    """Open a video in a real browser and pause every other YouTube video (browser tabs and the HUD)."""
    if not url:
        url = find_video(query) or f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    key = resolve(browser) or default_browser()
    paused = pause_other_youtube()
    _pause_hud_video()

    opened_in = None
    if reuse_tab and BROWSERS[key]["kind"] != "firefox":
        yt = [t for t in list_tabs(key) if YOUTUBE_RE.match(t.get("url", "")) and "error" not in t]
        if yt:
            tab = sorted(yt, key=lambda t: (not t["active"], t["window"]))[0]
            jxa(f"(function(){{var app=Application({_app(key)});{_tab_expr(key, tab)}.url={json.dumps(url)};return 'ok';}})()",
                app=BROWSERS[key]["app"])
            switch_to(tab)
            opened_in = "existing tab"
    if not opened_in:
        new_tab(url, key)
        opened_in = "new tab"

    # Arm same-browser exclusivity in every YouTube tab once the page exists.
    threading.Thread(target=lambda: (time.sleep(3), install_exclusive([key])), daemon=True).start()
    out = {"playing": url, "browser": BROWSERS[key]["app"], "opened_in": opened_in,
           "paused_elsewhere": paused["affected"]}
    if paused["blocked"]:
        out["could_not_pause_in"] = paused["blocked"]
    return out
