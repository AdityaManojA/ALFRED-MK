"""macOS system controls: sound, brightness, power, lock, appearance, network, battery."""
from core.mac import require_mac

require_mac()

from core.mac import system as sysctl          # noqa: E402
from core.mac.tooling import B, N, S, needs_confirm, tool   # noqa: E402

_ACTIONS = ["volume", "volume_up", "volume_down", "mute", "unmute", "toggle_mute",
            "brightness", "brightness_up", "brightness_down",
            "sleep", "display_off", "lock", "restart", "shutdown", "logout",
            "dark_mode", "night_shift", "wifi", "bluetooth", "battery",
            "keep_awake", "allow_sleep", "screenshot", "status"]


@tool
def mac_system(p, **_):
    a = str(p.get("action", "")).lower().strip()
    v = p.get("value")
    state = str(p.get("state") or "").lower().strip()
    step = float(v) if v not in (None, "") else 10

    if a == "volume":
        return sysctl.volume_set(float(v)) if v not in (None, "") else sysctl.volume_get()
    if a == "volume_up":
        return sysctl.volume_step(int(step))
    if a == "volume_down":
        return sysctl.volume_step(-int(step))
    if a in ("mute", "unmute", "toggle_mute"):
        return sysctl.set_muted({"mute": True, "unmute": False}.get(a))
    if a == "brightness":
        return sysctl.brightness_set(float(v)) if v not in (None, "") else sysctl.brightness_get()
    if a == "brightness_up":
        return sysctl.brightness_step(step)
    if a == "brightness_down":
        return sysctl.brightness_step(-step)
    if a == "sleep":
        return sysctl.sleep_now()
    if a == "display_off":
        return sysctl.display_off()
    if a == "lock":
        return sysctl.lock_screen()
    if a in ("restart", "shutdown", "logout"):
        if not p.get("confirm"):
            return needs_confirm(f"{a.replace('logout', 'log out').replace('shutdown', 'shut down')} the Mac now?")
        return sysctl.power_action(a)
    if a == "dark_mode":
        return sysctl.dark_mode(state or "toggle")
    if a == "night_shift":
        return sysctl.night_shift(state != "off")
    if a == "wifi":
        if state == "off" and not p.get("confirm"):
            return needs_confirm("Turn Wi-Fi off? You will lose the internet connection — and me with it.")
        return sysctl.wifi(state or "status")
    if a == "bluetooth":
        if state in ("off", "toggle") and not p.get("confirm"):
            return needs_confirm("Turn Bluetooth off? Bluetooth keyboards, mice and headphones will disconnect.")
        return sysctl.bluetooth(state or "status")
    if a == "battery":
        return sysctl.battery()
    if a == "keep_awake":
        return sysctl.keep_awake(float(v) if v not in (None, "", 0) else None)
    if a == "allow_sleep":
        return sysctl.allow_sleep()
    if a == "screenshot":
        return sysctl.screenshot("clipboard" if state == "clipboard" else "desktop")
    if a == "status":
        out = {}
        for name, fn in (("sound", sysctl.volume_get), ("display", sysctl.brightness_get),
                         ("battery", sysctl.battery), ("network", lambda: sysctl.wifi("status"))):
            try:
                out[name] = fn()
            except Exception as e:
                out[name] = str(e)
        return out
    return f"Unknown action '{a}'. Use one of: {', '.join(_ACTIONS)}."


TOOL = {
    "name": "mac_system",
    "description": ("Control this Mac: volume/mute, screen brightness, sleep, lock screen, display off, "
                    "restart/shutdown/log out (confirm first), dark mode, Night Shift, Wi-Fi, Bluetooth, "
                    "battery level, keep awake, screenshots, overall status."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", _ACTIONS),
        "value": N("Volume/brightness percent 0-100 for volume/brightness; step size for *_up/*_down "
                   "(default 10); minutes for keep_awake (omit = until told otherwise)."),
        "state": S("on | off | toggle | status for dark_mode, night_shift, wifi, bluetooth; "
                   "'clipboard' for screenshot to clipboard."),
        "confirm": B("Only true after the user explicitly agreed to a restart/shutdown/logout or turning Wi-Fi/Bluetooth off."),
    }, "required": ["action"]},
    "handler": mac_system,
}
