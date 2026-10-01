import time
import subprocess
import platform
import shutil

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_SYSTEM = platform.system()

_APP_ALIASES: dict[str, dict[str, str]] = {

    "chrome":             {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",                 "Darwin": "Firefox",              "Linux": "firefox"},
    "edge":               {"Windows": "msedge",                  "Darwin": "Microsoft Edge",       "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",                   "Darwin": "Brave Browser",        "Linux": "brave-browser"},
    "brave browser":      {"Windows": "brave",                   "Darwin": "Brave Browser",        "Linux": "brave-browser"},
    "safari":             {"Windows": "msedge",                  "Darwin": "Safari",               "Linux": "firefox"},
    "opera":              {"Windows": "opera",                   "Darwin": "Opera",                "Linux": "opera"},
    "whatsapp":           {"Windows": "WhatsApp",                "Darwin": "WhatsApp",             "Linux": "whatsapp"},
    "telegram":           {"Windows": "Telegram",                "Darwin": "Telegram",             "Linux": "telegram"},
    "discord":            {"Windows": "Discord",                 "Darwin": "Discord",              "Linux": "discord"},
    "slack":              {"Windows": "Slack",                   "Darwin": "Slack",                "Linux": "slack"},
    "zoom":               {"Windows": "Zoom",                    "Darwin": "zoom.us",              "Linux": "zoom"},
    "teams":              {"Windows": "msteams",                 "Darwin": "Microsoft Teams",      "Linux": "teams"},
    "skype":              {"Windows": "skype",                   "Darwin": "Skype",                "Linux": "skype"},
    "signal":             {"Windows": "signal",                  "Darwin": "Signal",               "Linux": "signal"},
    "spotify":            {"Windows": "Spotify",                 "Darwin": "Spotify",              "Linux": "spotify"},
    "vlc":                {"Windows": "vlc",                     "Darwin": "VLC",                  "Linux": "vlc"},
    "netflix":            {"Windows": "Netflix",                 "Darwin": "Netflix",              "Linux": "firefox"},
    "vscode":             {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "visual studio code": {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "code":               {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "terminal":           {"Windows": "wt",                      "Darwin": "Terminal",             "Linux": "x-terminal-emulator"},
    "cmd":                {"Windows": "cmd.exe",                 "Darwin": "Terminal",             "Linux": "bash"},
    "powershell":         {"Windows": "powershell.exe",          "Darwin": "Terminal",             "Linux": "bash"},
    "postman":            {"Windows": "Postman",                 "Darwin": "Postman",              "Linux": "postman"},
    "git":                {"Windows": "git-bash",                "Darwin": "Terminal",             "Linux": "bash"},
    "figma":              {"Windows": "Figma",                   "Darwin": "Figma",                "Linux": "figma"},
    "blender":            {"Windows": "blender",                 "Darwin": "Blender",              "Linux": "blender"},
    "word":               {"Windows": "winword",                 "Darwin": "Microsoft Word",       "Linux": "libreoffice --writer"},
    "excel":              {"Windows": "excel",                   "Darwin": "Microsoft Excel",      "Linux": "libreoffice --calc"},
    "powerpoint":         {"Windows": "powerpnt",                "Darwin": "Microsoft PowerPoint", "Linux": "libreoffice --impress"},
    "libreoffice":        {"Windows": "soffice",                 "Darwin": "LibreOffice",          "Linux": "libreoffice"},
    "notepad":            {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "textedit":           {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "explorer":           {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "file explorer":      {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "finder":             {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "task manager":       {"Windows": "taskmgr.exe",             "Darwin": "Activity Monitor",     "Linux": "gnome-system-monitor"},
    "settings":           {"Windows": "ms-settings:",            "Darwin": "System Preferences",   "Linux": "gnome-control-center"},
    "calculator":         {"Windows": "calc.exe",                "Darwin": "Calculator",           "Linux": "gnome-calculator"},
    "paint":              {"Windows": "mspaint.exe",             "Darwin": "Preview",              "Linux": "gimp"},
    "instagram":          {"Windows": "Instagram",               "Darwin": "Instagram",            "Linux": "firefox"},
    "tiktok":             {"Windows": "TikTok",                  "Darwin": "TikTok",               "Linux": "firefox"},
    "notion":             {"Windows": "Notion",                  "Darwin": "Notion",               "Linux": "notion"},
    "obsidian":           {"Windows": "Obsidian",                "Darwin": "Obsidian",             "Linux": "obsidian"},
    "capcut":             {"Windows": "CapCut",                  "Darwin": "CapCut",               "Linux": "capcut"},
    "steam":              {"Windows": "steam",                   "Darwin": "Steam",                "Linux": "steam"},
    "epic":               {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
    "epic games":         {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
}


def _normalize(raw: str) -> str:
    key = raw.lower().strip()

    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(_SYSTEM, raw)

    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(_SYSTEM, raw)

    return raw  

def _find_windows_app_path(app_name: str) -> str | None:
    """Resolve full executable path or Start Menu shortcut on Windows."""
    import os
    clean_name = app_name.strip()
    target_names = [clean_name]
    if not clean_name.lower().endswith(".exe"):
        target_names.append(f"{clean_name}.exe")

    # 1. Query Windows Registry App Paths (HKLM & HKCU)
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for t_name in target_names:
                try:
                    sub_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{t_name}"
                    with winreg.OpenKey(root, sub_key) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val and os.path.exists(val):
                            return val
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Query Windows Start Menu Shortcuts (.lnk files)
    start_dirs = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    query = clean_name.lower()
    for sfx in (" browser", " app", ".exe"):
        if query.endswith(sfx):
            query = query[:-len(sfx)].strip()

    best_match = None
    for s_dir in start_dirs:
        if not os.path.exists(s_dir):
            continue
        try:
            for root_dir, _, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        stem = f[:-4].lower()
                        if query == stem:
                            return os.path.join(root_dir, f)
                        if (query in stem or stem in query) and not best_match:
                            best_match = os.path.join(root_dir, f)
        except Exception:
            pass

    if best_match:
        return best_match

    # 3. Known application paths
    known_paths = [
        # Brave
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        # Chrome
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # Edge
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Firefox
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        # VS Code
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ]
    for p in known_paths:
        if os.path.exists(p):
            p_base = os.path.basename(p).lower()
            if query in p_base or p_base.startswith(query):
                return p

    # 4. PATH search via shutil.which
    for t_name in target_names:
        w = shutil.which(t_name)
        if w and os.path.exists(w):
            return w

    return None


def _launch_windows(app_name: str) -> bool:
    import os

    # 1. Protocol / URI scheme launch (e.g. ms-settings:, calc:, spotify:)
    if ":" in app_name and not ("\\" in app_name or "/" in app_name):
        try:
            os.startfile(app_name)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # 2. Exact path or shortcut resolution (Registry App Paths, Start Menu, or Known Locations)
    target = _find_windows_app_path(app_name)
    if target:
        try:
            os.startfile(target)
            time.sleep(1.2)
            return True
        except Exception as e:
            print(f"[open_app] os.startfile failed for '{target}': {e}")
            try:
                subprocess.Popen(
                    [target],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(1.2)
                return True
            except Exception as e2:
                print(f"[open_app] Popen failed for '{target}': {e2}")

    # 3. Direct os.startfile (ShellExecute checks App Paths and Shell associations)
    for name in (app_name, f"{app_name}.exe"):
        try:
            os.startfile(name)
            time.sleep(1.2)
            return True
        except Exception:
            pass

    # 4. cmd.exe /c start "" "target"
    for name in (app_name, f"{app_name}.exe"):
        try:
            res = subprocess.run(
                f'cmd.exe /c start "" "{name}"',
                shell=True,
                capture_output=True,
                timeout=5,
            )
            if res.returncode == 0:
                time.sleep(1.2)
                return True
        except Exception:
            pass

    # 5. Fallback: Start Menu search via pyautogui
    try:
        import pyautogui
        old_failsafe = getattr(pyautogui, "FAILSAFE", True)
        pyautogui.FAILSAFE = False
        try:
            pyautogui.press("win")
            time.sleep(0.7)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(0.9)
            pyautogui.press("enter")
            time.sleep(2.0)
            return True
        finally:
            pyautogui.FAILSAFE = old_failsafe
    except Exception as e:
        print(f"[open_app] Start Menu search failed: {e}")

    return False


def _launch_macos(app_name: str) -> bool:

    try:
        result = subprocess.run(
            ["open", "-a", app_name],
            capture_output=True, timeout=8
        )
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["open", "-a", f"{app_name}.app"],
            capture_output=True, timeout=8
        )
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen(
                [binary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1.0)
            return True
        except Exception:
            pass

    try:
        import pyautogui
        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[open_app] Spotlight failed: {e}")

    return False


_LINUX_TERMINAL_FALLBACKS = [
    "x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal",
    "xterm", "lxterminal", "mate-terminal", "tilix", "alacritty", "kitty",
]

def _launch_linux(app_name: str) -> bool:

    # terminal emulators: try common ones in order
    if app_name in ("x-terminal-emulator", "gnome-terminal", "terminal"):
        for term in _LINUX_TERMINAL_FALLBACKS:
            if shutil.which(term):
                try:
                    subprocess.Popen([term], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.0)
                    return True
                except Exception:
                    continue

    binary = (
        shutil.which(app_name) or
        shutil.which(app_name.lower()) or
        shutil.which(app_name.lower().replace(" ", "-")) or
        shutil.which(app_name.lower().replace(" ", "_"))
    )
    if binary:
        try:
            subprocess.Popen(
                [binary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1.0)
            return True
        except Exception:
            pass

    try:
        subprocess.run(
            ["xdg-open", app_name],
            capture_output=True, timeout=5
        )
        return True
    except Exception:
        pass

    for desktop_name in [
        app_name.lower(),
        app_name.lower().replace(" ", "-"),
        app_name.lower().replace(" ", ""),
    ]:
        try:
            result = subprocess.run(
                ["gtk-launch", desktop_name],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    return False


_OS_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin":  _launch_macos,
    "Linux":   _launch_linux,
}

def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
):
    params = parameters or {}
    app_name = str(params.get("app_name") or params.get("app") or params.get("name") or "").strip()

    if not app_name:
        return "No application name provided."

    from core.path_guard import is_heavenly_restricted, check_path_access
    if is_heavenly_restricted(app_name):
        return "Due to the heavenly restriction placed upon my creator, I cannot."
    if ":" in app_name or "\\" in app_name or "/" in app_name:
        ok, err = check_path_access(app_name)
        if not ok:
            return err

    launcher = _OS_LAUNCHERS.get(_SYSTEM)
    if launcher is None:
        return f"Unsupported operating system: {_SYSTEM}"

    normalized = _normalize(app_name)
    print(f"[open_app] Launching: '{app_name}' -> '{normalized}' ({_SYSTEM})")

    if player:
        player.write_log(f"[open_app] {app_name}")

    try:
        if launcher(normalized):
            return f"Opened {app_name}."
        if normalized.lower() != app_name.lower():
            if launcher(app_name):
                return f"Opened {app_name}."
        return (
            f"Could not confirm that {app_name} launched. "
            f"It may still be loading, or it might not be installed."
        )
    except Exception as e:
        print(f"[open_app] Error: {e}")
        return f"Failed to open {app_name}: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_app",
    "description": "Opens any application on the computer. Use this whenever the user asks to open, launch, or start any app, website, or program. Always call this tool — never just say you opened it.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
            }
        },
        "required": [
            "app_name"
        ]
    },
    "handler": open_app,
}
