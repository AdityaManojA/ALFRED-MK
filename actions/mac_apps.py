"""Open, quit, hide and switch between Mac apps."""
from core.mac import require_mac

require_mac()

from core.mac import system as sysctl                      # noqa: E402
from core.mac.tooling import B, S, needs_confirm, tool     # noqa: E402


@tool
def mac_apps(p, **_):
    a = str(p.get("action", "")).lower().strip()
    app = str(p.get("app") or "").strip()
    if a in ("open", "launch"):
        return sysctl.open_app(app)
    if a in ("quit", "close"):
        return sysctl.quit_app(app)
    if a == "force_quit":
        if not p.get("confirm"):
            return needs_confirm(f"Force quit {app}? Unsaved work in it will be lost.")
        return sysctl.quit_app(app, force=True)
    if a == "hide":
        return sysctl.hide_app(app)
    if a in ("focus", "switch"):
        return sysctl.focus_app(app)
    if a == "list":
        return {"running": sysctl.list_apps()}
    if a == "frontmost":
        return sysctl.frontmost()
    if a == "open_url":
        return sysctl.open_url(str(p.get("url") or app))
    return "Unknown action. Use open, quit, force_quit, hide, focus, list, frontmost or open_url."


TOOL = {
    "name": "mac_apps",
    "description": "Open, quit (gracefully), force quit, hide or switch to a Mac app; list running apps; which app is in front.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["open", "quit", "force_quit", "hide", "focus", "list", "frontmost", "open_url"]),
        "app": S("App name, e.g. 'Safari', 'Spotify', 'System Settings'."),
        "url": S("For open_url: a URL or URL scheme to open with its default app."),
        "confirm": B("Only for force_quit, after the user agreed."),
    }, "required": ["action"]},
    "handler": mac_apps,
}
