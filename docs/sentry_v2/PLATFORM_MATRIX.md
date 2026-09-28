# PLATFORM MATRIX — SENTRY MODE V2: CROSS-PLATFORM SPECIFICATION
**Repository:** ALFRED-MK-V  
**Date:** 2026-09-29  
**Specification Level:** Mandatory Cross-Platform Implementation (Windows, Linux, macOS)  

---

## 1. Operating System Targets & Architectures

| OS Target | Versions Supported | Architectures | Dev Environment Status | Target Role |
|---|---|---|---|---|
| **Windows** | Windows 10 (20H2+), Windows 11 | x86_64, arm64 (via emu) | **Host Dev Machine** (Win 11 x86_64) | Tier 1 (Immediate implementation) |
| **Linux** | Ubuntu 22.04+, Fedora 38+, Arch, Debian 12+ (glibc 2.31+) | x86_64, aarch64 | Native Cross-Platform Deliverable | Tier 1 (Native implementation) |
| **macOS** | macOS 12 (Monterey), 13 (Ventura), 14 (Sonoma), 15 (Sequoia) | Apple Silicon (arm64), Intel (x86_64) | Native Cross-Platform Deliverable | Tier 1 (Native implementation) |

---

## 2. Linux Display Sessions & Compositor Matrix

Under Linux, X11 and Wayland diverge fundamentally in window inspection capabilities. Sentry v2 rejects fake implementations (e.g. calling `xdotool` inside a Wayland session) and defines explicit compositor integrations:

| Session / Compositor | Mechanism / API Protocol | Foreground Window / PID | Browser Host Extraction | Capabilities & Requirements |
|---|---|---|---|---|
| **X11 (All WMs)** | Xlib / EWMH (`_NET_ACTIVE_WINDOW`, `_NET_WM_PID`) via `xprop` or `xdotool` | Native (`_NET_WM_PID` → `psutil`) | Window Title parsing + Address Bar UIA-equivalent via AT-SPI2 | Full support; fallback to window title regex when AT-SPI2 disabled |
| **Wayland: GNOME Shell (Mutter)** | DBus: `org.gnome.Shell.Introspect` (`GetWindows`) & `org.freedesktop.portal.RemoteDesktop` | Native DBus query returns focused window ID, app ID, and title | Read active window title via DBus; browser tabs via browser remote debugging or AT-SPI2 DBus | Full support; requires GNOME Shell 40+ |
| **Wayland: KDE Plasma (KWin)** | DBus: `org.kde.KWin` (`/KWin` scripting interface) | Query `workspace.activeWindow.pid` and `desktopFileName` | KWin scripting query or AT-SPI2 DBus bridge | Full support; requires KWin scripting interface |
| **Wayland: wlroots (Sway / Hyprland)** | IPC Socket (`swaymsg -t get_tree` / `hyprctl activewindow -j`) | Native IPC JSON parse returns focused node, pid, and app_id | IPC tree parse gives focused window; host extraction via title heuristic or AT-SPI2 | Full support |
| **Wayland: Generic / Fallback** | `xdg-desktop-portal` (`org.freedesktop.portal.ScreenCast`) | Query portal focused window if available, else declare capability `UNAVAILABLE` | Explicit `CAPABILITY_DEGRADED` (app-only lock verified via portal or AT-SPI2) | Unknown/failed reads return explicit capability enums, never false drift events |

---

## 3. Supported Browser Matrix

| Browser | Windows Mechanism | macOS Mechanism | Linux (X11/Wayland) Mechanism |
|---|---|---|---|
| **Google Chrome** | Windows UI Automation (`uiautomation` / `IUIAutomation`) targeting address bar (`ControlType.Edit` / `Name="Address and search bar"`) with `READER_TIMEOUT_MS` | AppleScript: `tell application "Google Chrome" to get URL of active tab of front window` | AT-SPI2 accessibility tree query or active title URL host heuristic |
| **Microsoft Edge** | Windows UI Automation targeting address bar (`AutomationId="view_1020"` or Edit control in top window) | AppleScript: `tell application "Microsoft Edge" to get URL of active tab of front window` | AT-SPI2 accessibility tree query |
| **Brave** | Windows UI Automation targeting address bar | AppleScript: `tell application "Brave Browser" to get URL of active tab of front window` | AT-SPI2 accessibility tree query |
| **Mozilla Firefox** | Windows UI Automation targeting address bar or Acc/Accessible interface | AppleScript: UI scripting via System Events (or window title heuristic) | AT-SPI2 / `xprop` title heuristic |
| **Arc / Chromium** | Windows UI Automation | AppleScript targeting application bundle ID | AT-SPI2 |

---

## 4. Required Dependencies & System Permissions

### Windows
- **Dependencies:** `pywin32` (`win32gui`, `win32process`), `psutil`, `ctypes` (standard library). Optional/conditional: `uiautomation` / `comtypes` for UIA address bar.
- **Permissions:** Standard interactive desktop execution (no admin required). Must attach thread desktop via `ctypes.windll.user32.SetThreadDesktop` if spawned from background service.

### macOS
- **Dependencies:** `pyobjc-framework-Quartz` (optional; falls back cleanly to CLI), `psutil`, `subprocess` (standard library for `osascript` and `lsappinfo`).
- **Permissions:**
  - **Accessibility (`AXUIElement`):** Required for UI scripting if querying System Events.
  - **Automation (Apple Events):** macOS prompt on first run allowing ALFRED to script "Google Chrome", "System Events", etc. Denied permissions produce clean `PERM_DENIED` capability state without crashing or repeated popups.

### Linux
- **Dependencies:** `psutil`, `python-xlib` (optional conditional), standard tools (`xdotool`, `xprop` on X11; `dbus-python` / `dasbus` / `gio` on Wayland).
- **Permissions:** User session access (`DBUS_SESSION_BUS_ADDRESS`, `WAYLAND_DISPLAY` or `DISPLAY`). No root/sudo required.

---

## 5. Architectural Capability & Error Isolation

Across all three operating systems:
1. **Bounded Execution:** Every native read must complete within `READER_TIMEOUT_MS = 250`. Stuck threads or hanging IPC calls are timed out and discarded.
2. **Strict Privacy Whitelisting:** Client-visible states are restricted to booleans, counters, and capability enums:
   - `CAPABILITY_FULL` (app + tab host verified)
   - `CAPABILITY_APP_ONLY` (app verified, tab host unavailable)
   - `CAPABILITY_UNKNOWN` (foreground read failed / permissions missing)
   - `PERM_DENIED` (platform accessibility or automation denied)
3. **Card-Retargeting Path (`from_card=True`):**
   - Windows: Enumerate top-level browser windows via `EnumWindows`, query address bar of the most recently active browser window via UIA.
   - macOS: Target front window of active browser process via AppleScript directly, bypassing the frontmost check since ALFRED HUD is currently frontmost.
   - Linux: Query active browser window from EWMH window stack (`_NET_CLIENT_LIST_STACKING`) or Wayland compositor window list.

---

## 6. Implementation Order & Testing Plan

1. **Phase 1 & 2:** Mode Manager, Dropdown UI, and Monitor Targets (shared cross-platform foundation).
2. **Phase 3 (Core & Backends):**
   - Abstract `BasePlatformReader` interface.
   - Implement `win.py` (verified live on host development machine).
   - Implement `mac.py` (clean conditional imports, bounded `osascript` subprocess calls, error handling).
   - Implement `linux.py` (X11 xprop/xdotool + Wayland GNOME/KDE/wlroots DBus readers with runtime environment detection).
3. **Phase 4 & 5:** Focus drift logic, canned pools, deferred locking, and card-retargeting exceptions across all backends.
4. **Phase 9 Acceptance Gate:** Automated unit tests covering all three backends (using mock injection and platform simulation), timeout handling, permission denials, and privacy enforcement.
