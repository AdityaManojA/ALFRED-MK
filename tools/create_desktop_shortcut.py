"""
tools/create_desktop_shortcut.py — Standalone utility to diagnose and create desktop shortcuts for ALFRED.

Usage:
    python tools/create_desktop_shortcut.py
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

_SYSTEM = platform.system()
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_real_desktop_dir() -> Path:
    """Resolve the user's real desktop directory (supporting OneDrive redirection)."""
    home = Path.home()
    if _SYSTEM == "Windows":
        # 1. SHGetKnownFolderPath (FOLDERID_Desktop)
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            fid = GUID(
                0xB4BFCC3A,
                0xDB2C,
                0x424C,
                (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
            )
            buf = ctypes.c_wchar_p()
            if (
                ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(fid), 0, None, ctypes.byref(buf)
                )
                == 0
            ):
                p = Path(buf.value)
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if p.is_dir():
                    return p
        except Exception:
            pass

        # 2. Windows Registry User Shell Folders
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "Desktop")
            p = Path(os.path.expandvars(val))
            if p.is_dir():
                return p
        except Exception:
            pass

    elif _SYSTEM == "Linux":
        try:
            out = subprocess.run(
                ["xdg-user-dir", "DESKTOP"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            p = Path(out.stdout.strip())
            if p.is_dir():
                return p
        except Exception:
            pass

    return home / "Desktop"


def resolve_icon_path() -> Path:
    """Locate the best available icon file for the shortcut."""
    cfg_dir = _PROJECT_ROOT / "config"
    for candidate in ("alfred.ico", "jarvis.ico", "batman_logo.ico"):
        p = cfg_dir / candidate
        if p.exists():
            return p

    # Fallback to generating one via ui module if Pillow is available
    out_ico = cfg_dir / "alfred.ico"
    try:
        from ui import MainWindow

        if MainWindow._build_jarvis_icon(out_ico):
            return out_ico
    except Exception:
        pass
    return out_ico


def create_windows_lnk(
    lnk_path: Path,
    target_exe: Path,
    script_path: Path,
    work_dir: Path,
    icon_path: Path,
) -> tuple[bool, str]:
    """Create a Windows .lnk shortcut using pywin32, WScript, or PowerShell."""
    lnk = str(lnk_path)
    target = str(target_exe)
    args = str(script_path)
    work = str(work_dir)
    icon_loc = str(icon_path) if icon_path.exists() else f"{target},0"

    # Method 1: pywin32 COM
    try:
        from win32com.client import Dispatch  # type: ignore

        sh = Dispatch("WScript.Shell")
        sc = sh.CreateShortCut(lnk)
        sc.TargetPath = target
        sc.Arguments = f'"{args}"'
        sc.WorkingDirectory = work
        sc.Description = "ALFRED AI Assistant"
        sc.IconLocation = icon_loc
        sc.save()
        if lnk_path.exists():
            return True, "Created via pywin32 COM Dispatch"
    except Exception as e:
        pywin_err = str(e)
    else:
        pywin_err = "File not generated"

    # Method 2: WScript.Shell via wscript.exe + VBScript
    try:
        import tempfile

        vbs_lines = [
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work}"',
            'sc.Description = "ALFRED AI Assistant"',
            f'sc.IconLocation = "{icon_loc}"',
            "sc.Save",
        ]
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(vbs_lines))
            proc = subprocess.Popen(
                ["wscript.exe", "/nologo", tmp],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            proc.wait(timeout=5)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
        if lnk_path.exists():
            return True, "Created via WScript host"
    except Exception:
        pass

    # Method 3: Built-in PowerShell COM (universal fallback on Windows 10/11)
    try:
        p_lnk = lnk.replace("'", "''")
        p_target = target.replace("'", "''")
        p_args = args.replace("'", "''")
        p_work = work.replace("'", "''")
        p_icon = icon_loc.replace("'", "''")

        ps_cmd = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{p_lnk}'); "
            f"$s.TargetPath = '{p_target}'; "
            f"$s.Arguments = '\"{p_args}\"'; "
            f"$s.WorkingDirectory = '{p_work}'; "
            f"$s.Description = 'ALFRED AI Assistant'; "
            f"$s.IconLocation = '{p_icon}'; "
            f"$s.Save()"
        )
        res = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_cmd,
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            capture_output=True,
            timeout=10,
            check=False,
        )
        if lnk_path.exists():
            return True, "Created via native Windows PowerShell COM fallback"
    except Exception as e:
        return False, f"All methods failed. pywin32 error: {pywin_err}; ps error: {e}"

    return False, f"All methods failed. pywin32: {pywin_err}"


def main() -> int:
    print("=" * 60)
    print("  🦇 ALFRED Desktop Shortcut Diagnostic & Deployment")
    print("=" * 60)
    print(f"Platform: {_SYSTEM}")
    print(f"Python:   {sys.executable} ({sys.version.split()[0]})")

    desktop_dir = get_real_desktop_dir()
    print(f"Desktop:  {desktop_dir}")
    if not desktop_dir.exists():
        print(f"⚠️  Warning: Desktop folder '{desktop_dir}' does not exist.")
        desktop_dir.mkdir(parents=True, exist_ok=True)

    main_script = _PROJECT_ROOT / "main.py"
    if not main_script.exists():
        print(f"❌ Error: main.py not found at {main_script}")
        return 1

    icon_path = resolve_icon_path()
    print(f"Icon:     {icon_path} (exists={icon_path.exists()})")

    if _SYSTEM == "Windows":
        # Check pywin32 status
        try:
            import win32com.client  # noqa: F401

            print("COM:      pywin32 (win32com.client) is installed and functional.")
        except Exception as e:
            print(f"COM:      pywin32 not registered ({e}).")
            print("          (PowerShell COM fallback will be used automatically.)")

        py = Path(sys.executable)
        pythonw = py.parent / "pythonw.exe"
        target_exe = pythonw if pythonw.exists() else py
        lnk_path = desktop_dir / "A.L.F.R.E.D.lnk"

        print(f"Target:   {target_exe}")
        print(f"Shortcut: {lnk_path}")

        ok, msg = create_windows_lnk(
            lnk_path, target_exe, main_script, _PROJECT_ROOT, icon_path
        )
        if ok and lnk_path.exists():
            print(f"\n✅ SUCCESS: {msg}")
            print(f"   Created '{lnk_path.name}' on Desktop.")
            return 0
        else:
            print(f"\n❌ FAILED: {msg}")
            return 1

    elif _SYSTEM == "Darwin":
        # macOS App bundle
        app = desktop_dir / "A.L.F.R.E.D.app"
        mac_dir = app / "Contents" / "MacOS"
        mac_dir.mkdir(parents=True, exist_ok=True)
        launcher = mac_dir / "ALFRED"
        launcher.write_text(
            "#!/usr/bin/env bash\n"
            f'cd "{_PROJECT_ROOT}"\n'
            f'exec "{sys.executable}" "{main_script}"\n'
        )
        import stat

        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
        print(f"\n✅ SUCCESS: Created macOS application at {app}")
        return 0

    else:
        # Linux .desktop
        desk = desktop_dir / "ALFRED.desktop"
        desk.write_text(
            "[Desktop Entry]\n"
            "Name=ALFRED\n"
            f"Exec={sys.executable} {main_script}\n"
            f"Path={_PROJECT_ROOT}\n"
            "Type=Application\n"
            "Terminal=false\n"
            "Categories=Utility;\n"
        )
        import stat

        desk.chmod(desk.stat().st_mode | stat.S_IEXEC)
        print(f"\n✅ SUCCESS: Created Linux desktop entry at {desk}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
