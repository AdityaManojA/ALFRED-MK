"""macOS system controls: sound, display, power, lock, network, appearance, apps.

Where a public or long-stable private API exists it is called directly
(DisplayServices for brightness, login.framework for locking, CoreBrightness
for Night Shift, NSWorkspace for apps) — no keystroke simulation, so these
work without Accessibility permission and regardless of which app is in front.
"""
from __future__ import annotations

import ctypes
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from core.mac.osa import OSAError, applescript, q, run

# ── Sound ─────────────────────────────────────────────────────────────────────

def volume_get() -> dict:
    out = applescript("get volume settings")
    level = re.search(r"output volume:(\d+|missing value)", out)
    muted = "output muted:true" in out
    lv = level.group(1) if level else "missing value"
    return {"volume": None if lv == "missing value" else int(lv), "muted": muted}


def volume_set(level: float) -> dict:
    level = max(0, min(100, int(round(level))))
    applescript(f"set volume output volume {level}\nset volume without output muted")
    return volume_get()


def volume_step(delta: int) -> dict:
    cur = volume_get().get("volume") or 0
    return volume_set(cur + delta)


def set_muted(muted: bool | None) -> dict:
    """muted=None toggles."""
    if muted is None:
        muted = not volume_get()["muted"]
    applescript("set volume with output muted" if muted else "set volume without output muted")
    return volume_get()


# ── Display brightness (built-in panel) ───────────────────────────────────────

def _displays():
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    ds = ctypes.CDLL("/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices")
    cg.CGDisplayIsBuiltin.argtypes = [ctypes.c_uint32]
    cg.CGDisplayIsBuiltin.restype = ctypes.c_bool
    ds.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
    ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
    ids = (ctypes.c_uint32 * 16)()
    n = ctypes.c_uint32()
    cg.CGGetOnlineDisplayList(16, ids, ctypes.byref(n))
    out = []
    for i in range(n.value):
        b = ctypes.c_float(-1)
        if ds.DisplayServicesGetBrightness(ids[i], ctypes.byref(b)) == 0:
            out.append((ids[i], bool(cg.CGDisplayIsBuiltin(ids[i])), b.value))
    return ds, out


def brightness_get() -> dict:
    _, disp = _displays()
    if not disp:
        return {"brightness": None, "note": "No display with software brightness control (external monitors use their own buttons)."}
    return {"brightness": round(disp[0][2] * 100)}


def brightness_set(percent: float) -> dict:
    ds, disp = _displays()
    if not disp:
        raise OSAError("No display here supports software brightness control.")
    v = max(0.0, min(1.0, float(percent) / 100.0))
    for did, _builtin, _cur in disp:
        ds.DisplayServicesSetBrightness(did, ctypes.c_float(v))
    return brightness_get()


def brightness_step(delta: float) -> dict:
    cur = brightness_get().get("brightness")
    if cur is None:
        raise OSAError("No display here supports software brightness control.")
    return brightness_set(cur + delta)


# ── Power / session ───────────────────────────────────────────────────────────

def lock_screen() -> str:
    login = ctypes.CDLL("/System/Library/PrivateFrameworks/login.framework/Versions/Current/login")
    login.SACLockScreenImmediate()
    return "Screen locked."


def sleep_now() -> str:
    # Detach so the reply can be spoken before the machine actually sleeps.
    subprocess.Popen(["/bin/sh", "-c", "sleep 3; pmset sleepnow"], start_new_session=True)
    return "Putting the Mac to sleep in 3 seconds."


def display_off() -> str:
    subprocess.Popen(["/bin/sh", "-c", "sleep 2; pmset displaysleepnow"], start_new_session=True)
    return "Turning the display off."


def power_action(kind: str) -> str:
    """restart | shutdown | logout — System Events asks apps to save first."""
    verb = {"restart": "restart", "shutdown": "shut down", "logout": "log out"}[kind]
    subprocess.Popen(["/bin/sh", "-c", f"sleep 4; osascript -e 'tell application \"System Events\" to {verb}'"],
                     start_new_session=True)
    return f"Okay — {verb} in a few seconds. Apps with unsaved work will ask first."


_CAFFEINATE_PID = Path.home() / "Library/Application Support/ALFRED/caffeinate.pid"


def keep_awake(minutes: float | None) -> str:
    allow_sleep()
    secs = int(minutes * 60) if minutes else 0
    args = ["caffeinate", "-d", "-i"] + (["-t", str(secs)] if secs else [])
    p = subprocess.Popen(args, start_new_session=True)
    _CAFFEINATE_PID.parent.mkdir(parents=True, exist_ok=True)
    _CAFFEINATE_PID.write_text(str(p.pid))
    return f"Keeping the Mac awake for {int(minutes)} minutes." if secs else "Keeping the Mac awake until you say otherwise."


def allow_sleep() -> str:
    try:
        pid = int(_CAFFEINATE_PID.read_text())
        os.kill(pid, signal.SIGTERM)
        _CAFFEINATE_PID.unlink()
        return "The Mac can sleep normally again."
    except Exception:
        return "The Mac was already allowed to sleep."


def battery() -> dict:
    out = run(["pmset", "-g", "batt"])
    m = re.search(r"(\d+)%;\s*([^;]+);\s*([^\s]+)?", out)
    src = "AC power" if "AC Power" in out else "battery"
    if not m:
        return {"source": src, "note": "No battery found."}
    remaining = m.group(3) if m.group(3) and ":" in m.group(3) else None
    return {"percent": int(m.group(1)), "state": m.group(2).strip(), "source": src,
            "time_remaining": remaining}


# ── Appearance ────────────────────────────────────────────────────────────────

def dark_mode(state: str) -> dict:
    if state in ("on", "off"):
        applescript('tell application "System Events" to tell appearance preferences to set dark mode to '
                    + ("true" if state == "on" else "false"), app="System Events")
    elif state == "toggle":
        applescript('tell application "System Events" to tell appearance preferences to set dark mode to not dark mode',
                    app="System Events")
    out = applescript('tell application "System Events" to tell appearance preferences to get dark mode',
                      app="System Events")
    return {"dark_mode": out == "true"}


def night_shift(on: bool) -> dict:
    import objc
    ns = {}
    objc.loadBundle("CoreBrightness", ns, bundle_path="/System/Library/PrivateFrameworks/CoreBrightness.framework")
    client = ns["CBBlueLightClient"].alloc().init()
    client.setEnabled_(bool(on))
    return {"night_shift": bool(on)}


# ── Network ───────────────────────────────────────────────────────────────────

def _wifi_device() -> str:
    out = run(["networksetup", "-listallhardwareports"])
    m = re.search(r"Hardware Port: (?:Wi-Fi|AirPort)\nDevice: (\w+)", out)
    return m.group(1) if m else "en0"


def wifi(state: str) -> dict:
    dev = _wifi_device()
    if state in ("on", "off"):
        run(["networksetup", "-setairportpower", dev, state])
    elif state == "toggle":
        cur = "On" in run(["networksetup", "-getairportpower", dev])
        run(["networksetup", "-setairportpower", dev, "off" if cur else "on"])
    power = "On" in run(["networksetup", "-getairportpower", dev])
    info = {"wifi": "on" if power else "off"}
    summary = run(["ipconfig", "getsummary", dev])
    m = re.search(r"\n\s*SSID : (.+)", summary)
    if m and "redacted" not in m.group(1):
        info["network"] = m.group(1).strip()
    return info


_BT_HELPER = (
    "import ctypes,sys\n"
    "bt=ctypes.CDLL('/System/Library/Frameworks/IOBluetooth.framework/IOBluetooth')\n"
    "a=sys.argv[1]\n"
    "if a in('0','1'): bt.IOBluetoothPreferenceSetControllerPowerState(int(a))\n"
    "print(bt.IOBluetoothPreferenceGetControllerPowerState())\n"
)


def bluetooth(state: str) -> dict:
    """Run in a child: IOBluetooth aborts any process lacking the Bluetooth
    usage string, and a crash there must not take the agent down with it."""
    def call(arg: str) -> int | None:
        p = subprocess.run([sys.executable, "-c", _BT_HELPER, arg], capture_output=True, text=True, timeout=10)
        try:
            return int(p.stdout.strip().splitlines()[-1])
        except Exception:
            return None
    cur = call("get")
    if cur is None:
        raise OSAError("Bluetooth control needs ALFRED's Bluetooth permission (System Settings → Privacy & Security → Bluetooth).")
    if state == "toggle":
        state = "off" if cur else "on"
    if state in ("on", "off"):
        cur = call("1" if state == "on" else "0")
        time.sleep(0.5)
        cur = call("get")
    return {"bluetooth": "on" if cur else "off"}


# ── Media keys (work for whatever app owns Now Playing: browsers, Spotify, Music…) ──

_MEDIA_KEYS = {"play_pause": 16, "next": 17, "previous": 18, "fast_forward": 19, "rewind": 20}


def media_key(name: str) -> str:
    import Quartz
    from AppKit import NSEvent
    code = _MEDIA_KEYS[name]
    for down in (True, False):
        flags = 0xA00 if down else 0xB00
        data1 = (code << 16) | ((0xA if down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            14, (0, 0), flags, 0, 0, None, 8, data1, -1)
        Quartz.CGEventPost(0, ev.CGEvent())
    return f"Sent {name.replace('_', ' ')}."


def screenshot(target: str = "desktop") -> str:
    folder = Path.home() / ("Desktop" if target != "clipboard" else "")
    if target == "clipboard":
        run(["screencapture", "-x", "-c"])
        return "Screenshot copied to the clipboard."
    path = folder / time.strftime("Screenshot %Y-%m-%d at %H.%M.%S.png")
    run(["screencapture", "-x", str(path)])
    return f"Screenshot saved to {path}." if path.exists() else \
        "Screen capture failed — ALFRED may need Screen Recording permission."


# ── Apps ──────────────────────────────────────────────────────────────────────

def _find_app(name: str):
    from core.mac.osa import running_apps
    want = name.lower().strip().removesuffix(".app")
    apps = running_apps()
    for a in apps:
        if (a.localizedName() or "").lower() == want:
            return a
    for a in apps:
        if want in (a.localizedName() or "").lower() or want in (a.bundleIdentifier() or "").lower():
            return a
    return None


def list_apps() -> list[str]:
    from core.mac.osa import running_apps
    return sorted({a.localizedName() for a in running_apps() if a.localizedName()})


def frontmost() -> dict:
    from AppKit import NSWorkspace
    a = NSWorkspace.sharedWorkspace().frontmostApplication()
    return {"app": a.localizedName() if a else None, "bundle_id": a.bundleIdentifier() if a else None}


def open_app(name: str) -> str:
    r = subprocess.run(["open", "-a", name], capture_output=True, text=True)
    if r.returncode == 0:
        return f"Opened {name}."
    # Fall back to a Spotlight lookup of the app bundle.
    found = run(["mdfind", f"kMDItemContentType == 'com.apple.application-bundle' && kMDItemDisplayName == '*{name}*'cd"]).splitlines()
    if found:
        subprocess.run(["open", found[0]])
        return f"Opened {Path(found[0]).stem}."
    raise OSAError(f"I couldn't find an app called {name}.")


def quit_app(name: str, force: bool = False) -> str:
    a = _find_app(name)
    if a is None:
        return f"{name} isn't running."
    title = a.localizedName()
    ok = a.forceTerminate() if force else a.terminate()
    return f"{'Force quit' if force else 'Quit'} {title}." if ok else f"{title} refused to quit."


def hide_app(name: str) -> str:
    a = _find_app(name)
    if a is None:
        return f"{name} isn't running."
    a.hide()
    return f"Hid {a.localizedName()}."


def focus_app(name: str) -> str:
    a = _find_app(name)
    if a is None:
        return open_app(name)
    a.unhide()
    a.activateWithOptions_(1 << 1)   # NSApplicationActivateIgnoringOtherApps
    return f"Switched to {a.localizedName()}."


def open_url(url: str) -> str:
    subprocess.run(["open", url])
    return f"Opened {url}."
