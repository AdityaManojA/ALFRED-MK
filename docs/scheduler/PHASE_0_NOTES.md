# Scheduler Recon

Graphify nodes used: `ActionRegistry`, `actions/reminder.py`, `JarvisLive._dispatch_tool`, `MainWindow`, and `computer_settings.py`.

The action loader auto-discovers `TOOL` entries. Existing platform input uses `pyautogui`, clipboard support is available through `pyperclip`, Windows code already uses Win32 dependencies, macOS uses native scripting, and Linux commands use `xdotool` patterns.
