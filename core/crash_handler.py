"""User-controlled reporting for unhandled Python exceptions."""

import os
import platform
import sys
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

CRASH_LOG_FILE = Path.home() / ".alfred" / "crashes.log"
DEVELOPER_EMAIL = "Aditya.dev.org@gmail.com"


def _print(message):
    """Reporting must also work under pythonw or a closed console."""
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


def format_crash_report(exc_type, exc_value, exc_tb, *, limit=None):
    try:
        import psutil
        memory = f"{psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB"
    except Exception:
        memory = "unknown"
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb, limit=limit))
    return (
        f"CRASH REPORT\n============\nTimestamp: {datetime.now().isoformat()}\n"
        f"Python: {platform.python_version()}\n"
        f"OS: {platform.system()} {platform.release()}\nMemory: {memory}\n\n"
        f"Error: {exc_type.__name__}: {exc_value}\n\nTraceback:\n{details}"
    )


def log_crash(crash_report):
    try:
        CRASH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CRASH_LOG_FILE.open("a", encoding="utf-8") as stream:
            stream.write(crash_report + "\n\n" + "=" * 60 + "\n\n")
    except Exception as error:
        _print(f"Failed to write crash log: {error}")


def show_crash_dialog(crash_report):
    try:
        # Avoid Qt's process-level abort when no Linux display is available.
        if sys.platform.startswith("linux") and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        ):
            raise RuntimeError("No graphical display available")
        from PyQt6.QtCore import QThread, Qt
        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        if QThread.currentThread() != app.thread():
            raise RuntimeError("Crash dialog requires the GUI thread")
        msg = QMessageBox()
        msg.setWindowTitle("ALFRED Crashed")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setText("ALFRED encountered an error and had to close.")
        error_text = crash_report.split("\n\nError: ", 1)[-1].split("\n\nTraceback:", 1)[0]
        msg.setInformativeText(error_text[:1000])
        msg.setDetailedText(crash_report)
        report_button = msg.addButton("📧 Report to Developer", QMessageBox.ButtonRole.AcceptRole)
        close_button = msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(close_button)
        msg.setEscapeButton(close_button)
        msg.exec()
        return msg.clickedButton() is report_button
    except Exception:
        _print(f"ALFRED CRASHED\n{crash_report}\nTo report, email: {DEVELOPER_EMAIL}")
        return False


def open_email_client(crash_report):
    body = (
        "Hi Aditya,\n\nALFRED crashed. Here are the details:\n\n"
        + crash_report
        + f"\n\nFull log location (if saved): {CRASH_LOG_FILE}"
    )
    prefix = f"mailto:{DEVELOPER_EMAIL}?subject={quote('ALFRED Crash Report')}&body="
    # Bound the encoded URI using binary search to avoid O(N^2) quote overhead.
    suffix = "\n[Report truncated; see local crash log.]"
    max_len = 1900
    if len(prefix + quote(body, safe="")) > max_len:
        low, high = 0, len(body)
        best = 0
        while low <= high:
            mid = (low + high) // 2
            candidate = body[:mid] + suffix
            if len(prefix + quote(candidate, safe="")) <= max_len:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        body = body[:best] + suffix
    url = prefix + quote(body, safe="")
    try:
        if sys.platform == "win32":
            os.startfile(url)
        elif not webbrowser.open(url):
            raise RuntimeError("No email client accepted the request")
        return True
    except Exception as error:
        _print(f"Failed to open email client: {error}. Email {DEVELOPER_EMAIL}.")
        return False


def _show_and_report(report: str):
    if show_crash_dialog(report):
        open_email_client(report)


def _handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    try:
        report = format_crash_report(exc_type, exc_value, exc_tb)
        log_crash(report)
        dlg_report = format_crash_report(exc_type, exc_value, exc_tb, limit=-10)

        # Thread check for Qt GUI dialog
        try:
            from PyQt6.QtCore import QThread, QTimer
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None and QThread.currentThread() != app.thread():
                QTimer.singleShot(0, lambda: _show_and_report(dlg_report))
                return
        except Exception:
            pass

        _show_and_report(dlg_report)
    except Exception:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    raise SystemExit(1)


def install_crash_handler():
    sys.excepthook = _handle_exception
    import threading
    threading.excepthook = lambda args: _handle_exception(args.exc_type, args.exc_value, args.exc_traceback)
