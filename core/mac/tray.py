"""Menu-bar icon for the agent (macOS). Created on the Qt thread by JarvisUI.mac_attach."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QPolygonF
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

# The bat from config/batman_logo.png, traced in its own 512-px space.
_BAT = [(100, 212), (133, 183), (235, 200), (243, 172), (257, 190), (271, 172), (279, 200),
        (380, 183), (410, 212), (385, 262), (360, 250), (335, 290), (310, 282), (285, 322),
        (257, 345), (228, 322), (205, 282), (178, 290), (152, 250), (125, 262)]


def bat_icon() -> QIcon:
    """Black silhouette on transparent, flagged as a mask so macOS tints it for light/dark menu bars."""
    icon = QIcon()
    for size in (22, 44):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = size * 0.92
        scale = w / 310.0
        x0 = (size - w) / 2
        y0 = (size - 173 * scale) / 2
        poly = QPolygonF([QPointF(x0 + (x - 100) * scale, y0 + (y - 172) * scale) for x, y in _BAT])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0))
        p.drawPolygon(poly)
        p.end()
        icon.addPixmap(pm)
    icon.setIsMask(True)
    return icon


class MacTray:
    def __init__(self, ui, mac):
        self.ui = ui
        self.mac = mac
        self.tray = QSystemTrayIcon(bat_icon())
        self.tray.setToolTip("ALFRED")
        menu = QMenu()
        self.status = QAction("ALFRED")
        self.status.setEnabled(False)
        menu.addAction(self.status)
        menu.addSeparator()
        self._add(menu, "Show ALFRED", lambda: ui.mac_show_main())
        self._add(menu, "Talk now", lambda: mac._on_wake({"capturing": False}))
        self._add(menu, "Sleep now", self._sleep)
        menu.addSeparator()
        self.listen_action = self._add(menu, "Pause “Hey Alfred”", self._toggle_listening)
        menu.addSeparator()
        self._add(menu, "Quit ALFRED (keep listening)", self._quit_agent)
        self._add(menu, "Quit ALFRED and stop listening", self._quit_all)
        self.menu = menu
        self.tray.setContextMenu(menu)
        menu.aboutToShow.connect(self._refresh)
        self.tray.show()
        print("[mac] menu-bar icon ready")

    def _add(self, menu, text, fn):
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)
        return act

    def _refresh(self):
        c = self.mac.client
        st = c.request({"type": "status"}, timeout=1) if c else None
        listening = bool(st and st.get("listening", True))
        self.listen_action.setText("Pause “Hey Alfred”" if listening else "Resume “Hey Alfred”")
        state = "asleep — say “Hey Alfred”" if self.mac.dormant else "awake"
        if st and not listening:
            state += " (wake word paused)"
        alarms = (st or {}).get("alarms") or []
        if alarms:
            state += f" · {len(alarms)} alarm{'s' if len(alarms) != 1 else ''}"
        self.status.setText(f"ALFRED is {state}")

    def _sleep(self):
        self.mac.request_sleep()
        self.ui.mac_hide_main()

    def _toggle_listening(self):
        c = self.mac.client
        st = c.request({"type": "status"}, timeout=1) if c else None
        on = bool(st and st.get("listening", True))
        if c:
            c.request({"type": "listening", "enabled": not on}, timeout=2)

    def _quit_agent(self):
        self.mac.exit_process("quit from menu bar")

    def _quit_all(self):
        c = self.mac.client
        if c:
            c.request({"type": "quit_all"}, timeout=2)
        self.mac.exit_process("quit everything from menu bar")
