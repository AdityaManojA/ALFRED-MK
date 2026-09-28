"""
Screen & webcam capture for ALFRED vision with OS window context grounding.

Provides:
- `capture_screen()` / `_capture_screen()`: Captures screen and active window context.
- `get_active_window_info()`: Queries foreground window, app name, and tab title.
- `get_active_window_context()`: Returns formatted [WINDOW_CONTEXT] block.
- `format_visual_payload()`: Formats visual frame payload for Gemini Live API.
- `_capture_camera()`: Webcam frame capture.
"""
from __future__ import annotations

import base64
import ctypes
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# OS-native window API imports with graceful fallbacks
_WIN32 = False
if sys.platform.startswith("win"):
    try:
        import win32gui
        import win32process
        import psutil
        _WIN32 = True
    except ImportError:
        _WIN32 = False
else:
    try:
        import psutil
    except ImportError:
        pass

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config_key(key: str, value) -> None:
    try:
        cfg = _load_config()
        cfg[key] = value
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"\033[91m[Vision]\033[0m \033[91m[warn]\033[0m Could not save config key '{key}': {e}")


def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()


_IMG_MAX_W = 1280
_IMG_MAX_H = 720
_JPEG_Q    = 82


def _compress(img_bytes: bytes, source_format: str = "PNG") -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, f"image/{source_format.lower()}"

    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"\033[91m[Vision]\033[0m \033[91m[warn]\033[0m Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"


# =========================================================================
# OS-Native Active Window Context Querying (<15ms latency)
# =========================================================================

def _get_windows_window_info(monitor_id: int | str = 1) -> tuple[str, str, int]:
    """Query foreground window handle, title, and process name on Windows."""
    # Ensure current thread is attached to the interactive user desktop
    try:
        user32 = ctypes.windll.user32
        h_default = user32.OpenDesktopW("Default", 0, False, 0x0100)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception:
        pass

    app = "Unknown"
    title = ""
    hwnd = 0

    if not _WIN32:
        return app, title, hwnd

    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                try:
                    import psutil
                    proc = psutil.Process(pid)
                    raw_name = proc.name()
                    low = raw_name.lower()
                    if "code" in low:
                        app = "VS Code"
                    elif "chrome" in low:
                        app = "Google Chrome"
                    elif "msedge" in low:
                        app = "Microsoft Edge"
                    elif "brave" in low:
                        app = "Brave"
                    elif "firefox" in low:
                        app = "Firefox"
                    elif low.endswith(".exe"):
                        app = raw_name[:-4]
                    else:
                        app = raw_name
                except Exception:
                    app = "Unknown"
    except Exception:
        app = "Unknown"
        title = ""
        hwnd = 0

    return app, title, hwnd


def _get_macos_window_info(monitor_id: int | str = 1) -> tuple[str, str, int]:
    """Query active frontmost window on macOS via Quartz or AppleScript fallback."""
    # 1. Try Quartz API
    try:
        import Quartz
        opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        win_list = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
        for w in (win_list or []):
            if w.get(Quartz.kCGWindowLayer, 0) == 0 and w.get(Quartz.kCGWindowAlpha, 0) > 0:
                app = w.get(Quartz.kCGWindowOwnerName, "Unknown")
                title = w.get(Quartz.kCGWindowName, "")
                wid = int(w.get(Quartz.kCGWindowNumber, 0))
                if app != "Unknown" or title:
                    return app, title, wid
    except Exception:
        pass

    # 2. AppleScript Fallback
    try:
        import subprocess
        scpt = (
            'tell application "System Events"\n'
            'set frontApp to first application process whose frontmost is true\n'
            'set frontAppName to name of frontApp\n'
            'set winTitle to ""\n'
            'try\n'
            'set winTitle to name of front window of frontApp\n'
            'end try\n'
            'return frontAppName & ":::" & winTitle\n'
            'end tell'
        )
        res = subprocess.run(["osascript", "-e", scpt], capture_output=True, text=True, timeout=0.012)
        if res.returncode == 0 and ":::" in res.stdout:
            parts = res.stdout.strip().split(":::", 1)
            return parts[0] or "Unknown", parts[1] or "", 0
    except Exception:
        pass

    return "Unknown", "", 0


def _get_linux_window_info(monitor_id: int | str = 1) -> tuple[str, str, int]:
    """Query active window on Linux via xdotool or wmctrl."""
    import subprocess
    try:
        res = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=0.012)
        if res.returncode == 0 and res.stdout.strip():
            wid_str = res.stdout.strip()
            wid = int(wid_str)
            title_res = subprocess.run(["xdotool", "getwindowname", wid_str], capture_output=True, text=True, timeout=0.012)
            title = title_res.stdout.strip() if title_res.returncode == 0 else ""
            app = "Unknown"
            pid_res = subprocess.run(["xdotool", "getwindowpid", wid_str], capture_output=True, text=True, timeout=0.012)
            if pid_res.returncode == 0 and pid_res.stdout.strip():
                try:
                    import psutil
                    app = psutil.Process(int(pid_res.stdout.strip())).name()
                except Exception:
                    pass
            return app, title, wid
    except Exception:
        pass

    try:
        res = subprocess.run(["wmctrl", "-a"], capture_output=True, text=True, timeout=0.012)
    except Exception:
        pass

    return "Unknown", "", 0


def get_active_window_info(monitor_id: int | str = 1) -> dict:
    """
    Queries active OS window handle, application name, and window/tab title.
    Guaranteed to complete under 15ms with graceful fallback to 'App: Unknown'.
    """
    t0 = time.perf_counter()
    plat = sys.platform

    app = "Unknown"
    title = ""
    hwnd = 0

    try:
        if plat.startswith("win"):
            app, title, hwnd = _get_windows_window_info(monitor_id)
        elif plat.startswith("darwin"):
            app, title, hwnd = _get_macos_window_info(monitor_id)
        else:
            app, title, hwnd = _get_linux_window_info(monitor_id)
    except Exception:
        app = "Unknown"
        title = ""
        hwnd = 0

    elapsed_ms = (time.perf_counter() - t0) * 1000
    app_str = app.strip() if app else "Unknown"
    title_str = title.strip() if title else "None"
    context_str = f"[WINDOW_CONTEXT] App: {app_str} | Title: {title_str} | Monitor: {monitor_id}"

    return {
        "app": app_str,
        "title": title_str,
        "monitor": monitor_id,
        "handle": hwnd,
        "latency_ms": elapsed_ms,
        "context": context_str,
    }


def format_window_context(app: str, title: str, monitor: int | str = 1) -> str:
    """Format the standard metadata block: [WINDOW_CONTEXT] App: <Name> | Title: <Title> | Monitor: <ID>."""
    app_str = app.strip() if app else "Unknown"
    title_str = title.strip() if title else "None"
    return f"[WINDOW_CONTEXT] App: {app_str} | Title: {title_str} | Monitor: {monitor}"


def get_active_window_context(monitor_id: int | str = 1) -> str:
    """Convenience entry point to retrieve formatted active window context string."""
    info = get_active_window_info(monitor_id)
    return info["context"]


def format_visual_payload(
    img_bytes: bytes,
    mime_type: str,
    window_context: str = "",
    question: str = "What do you see?",
    source_label: str = "[IMAGE SOURCE: SCREEN CAPTURE]",
) -> dict:
    """
    Prepares the visual frame payload dictionary for the Gemini Live API client_content.
    Prepends the [WINDOW_CONTEXT] block directly to the visual frame text payload.
    """
    b64 = base64.b64encode(img_bytes).decode("ascii")
    header = window_context.strip() if window_context else ""
    if header:
        text_content = f"{header}\n\n{source_label}\n\n{question}".strip()
    else:
        text_content = f"{source_label}\n\n{question}".strip()

    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": b64,
        },
        "text": text_content,
        "window_context": header,
    }


class ScreenCapturePayload(tuple):
    """
    Hybrid return payload for screen captures.
    - Behaves as a 3-tuple `(img_bytes, mime_type, window_context)` for standard unpacking.
    - Provides dict-like item access (`sc["text"]`, `sc["inline_data"]`) and properties
      (`.img_bytes`, `.mime_type`, `.window_context`, `.text`, `.payload`) for direct stream consumption.
    """
    def __new__(cls, img_bytes: bytes, mime_type: str, window_context: str = "", payload: dict | None = None):
        return super().__new__(cls, (img_bytes, mime_type, window_context))

    def __init__(self, img_bytes: bytes, mime_type: str, window_context: str = "", payload: dict | None = None):
        self.img_bytes = img_bytes
        self.mime_type = mime_type
        self.window_context = window_context
        self._payload = payload or format_visual_payload(img_bytes, mime_type, window_context)

    @property
    def payload(self) -> dict:
        return self._payload

    @property
    def text(self) -> str:
        return self._payload.get("text", self.window_context)

    def get(self, key, default=None):
        if key in ("context", "window_context"):
            return self.window_context
        return self._payload.get(key, default)

    def __contains__(self, item):
        if item in ("context", "window_context"):
            return True
        if isinstance(item, str) and item in self._payload:
            return True
        return super().__contains__(item)

    def __getitem__(self, item):
        if item in ("context", "window_context"):
            return self.window_context
        if isinstance(item, str):
            return self._payload[item]
        return super().__getitem__(item)


# =========================================================================
# Screen Capture Entry Points
# =========================================================================

def capture_screen(monitor: int = 1) -> ScreenCapturePayload:
    """
    Captures primary or specified monitor, queries active OS window context,
    compresses image to JPEG, and returns a ScreenCapturePayload with metadata
    and visual frame payload.
    """
    # 1. Query OS-native active window context before taking the screenshot
    win_info = get_active_window_info(monitor_id=monitor)
    context_str = win_info["context"]

    # 2. Grab screen via mss
    if not _MSS:
        raise RuntimeError("mss is not installed. Run: pip install mss")

    _mss_factory = getattr(mss, "MSS", getattr(mss, "mss", None))
    with _mss_factory() as sct:
        monitors = sct.monitors  # [0] = all combined, [1..n] = real screens
        idx = monitor if monitor < len(monitors) else 0
        target = monitors[idx] if len(monitors) > 1 else monitors[0]
        shot = sct.grab(target)
        png = mss.tools.to_png(shot.rgb, shot.size)

    # 3. Compress frame
    img_b, mime_t = _compress(png, "PNG")

    # 4. Construct visual frame payload with prepended [WINDOW_CONTEXT]
    payload = format_visual_payload(img_b, mime_t, window_context=context_str)

    return ScreenCapturePayload(img_b, mime_t, context_str, payload)


def _capture_screen() -> ScreenCapturePayload:
    """Default entry point used by main.py."""
    return capture_screen(monitor=1)


# =========================================================================
# Camera Capture
# =========================================================================

def _cv2_backend() -> int:
    """Return the best OpenCV camera backend for the current OS."""
    if not _CV2:
        return 0
    os_name = _get_os()
    if os_name == "windows":
        return cv2.CAP_DSHOW
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def _probe_camera(index: int, backend: int, warmup: int = 5) -> bool:
    if not _CV2:
        return False
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return False
    for _ in range(warmup):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return False
    return bool(np.mean(frame) > 8)


def _detect_camera_index() -> int:
    backend = _cv2_backend()
    print("\033[91m[Vision]\033[0m \033[91m[search]\033[0m Auto-detecting camera...")
    for idx in range(6):
        if _probe_camera(idx, backend):
            print(f"\033[91m[Vision]\033[0m \033[91m[ok]\033[0m Camera found at index {idx}")
            _save_config_key("camera_index", idx)
            return idx
        print(f"\033[91m[Vision]\033[0m \033[91m[warn]\033[0m Camera index {idx}: no usable frame")

    print("\033[91m[Vision]\033[0m \033[91m[warn]\033[0m No camera found — defaulting to index 0")
    _save_config_key("camera_index", 0)
    return 0


def _get_camera_index() -> int:
    cfg = _load_config()
    if "camera_index" in cfg:
        return int(cfg["camera_index"])
    return _detect_camera_index()


def _capture_camera() -> tuple[bytes, str]:
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    index   = _get_camera_index()
    backend = _cv2_backend()
    cap     = cv2.VideoCapture(index, backend)

    if not cap.isOpened():
        raise RuntimeError(f"Camera index {index} could not be opened.")

    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Camera returned no frame.")

    if _PIL:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q)
        return buf.getvalue(), "image/jpeg"

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
    return buf.tobytes(), "image/jpeg"
