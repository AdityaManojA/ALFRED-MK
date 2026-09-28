"""
ui_overlay.py — Minimalist Floating HUD Widget for Telemetry Display
A transparent, always-on-top widget that displays key system metrics
"""

import sys
import time
import psutil
from datetime import datetime
from pathlib import Path

# Qt6 imports with graceful fallbacks
try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QFrame, QGraphicsDropShadowEffect, QSystemTrayIcon, QMenu
    )
    from PyQt6.QtGui import (
        QFont, QPalette, QColor, QPainter, QLinearGradient, QBrush,
        QPainterPath, QPolygonF, QIcon, QAction
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, pyqtSlot, QObject, QPoint, QRect, QSize,
        QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup,
        QParallelAnimationGroup
    )
    QT_AVAILABLE = True
except Exception as e:
    print(f"[UI Overlay] Qt6 not available: {e}")
    QT_AVAILABLE = False


class TelemetryHUD(QWidget):
    """A minimalist floating HUD widget for displaying telemetry data."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALFRED Telemetry HUD")
        self._setup_ui()
        self._setup_timer()
        self._setup_tray_icon()

        # Track last network I/O for calculating speeds
        self._last_net_io = psutil.net_io_counters()
        self._last_net_time = time.time()

    def _setup_ui(self):
        """Set up the HUD user interface."""
        # Window properties - always on top, frameless, transparent background
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Size and position
        self.resize(200, 120)
        self.move(50, 50)  # Start in top-left corner

        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        self.setLayout(layout)

        # Title bar with drag handle
        title_layout = QHBoxLayout()
        title_label = QLabel("ALFRED HUD")
        title_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Close button
        close_btn = QLabel("✕")
        close_btn.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-weight: bold;
                font-size: 9pt;
            }
            QLabel:hover {
                color: #ff5252;
            }
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.mousePressEvent = lambda event: self.close()
        title_layout.addWidget(close_btn)

        layout.addLayout(title_layout)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: rgba(0, 212, 255, 0.3); max-height: 1px;")
        layout.addWidget(line)

        # Telemetry data labels
        self.cpu_label = QLabel("CPU: --%")
        self.ram_label = QLabel("RAM: --%")
        self.temp_label = QLabel("Temp: --°C")
        self.net_label = QLabel("Net: -- KB/s")
        self.time_label = QLabel("--:--:--")

        # Style all labels
        label_style = """
            QLabel {
                color: #dde3ed;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                padding: 2px;
            }
        """
        for label in [self.cpu_label, self.ram_label, self.temp_label, self.net_label, self.time_label]:
            label.setStyleSheet(label_style)
            layout.addWidget(label)

        # Apply drop shadow for depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # Set overall widget style
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 20, 30, 0.85);
                border-radius: 12px;
                border: 1px solid rgba(0, 212, 255, 0.2);
            }
        """)

        # Make widget movable
        self.oldPos = self.pos()

    def _setup_timer(self):
        """Set up the update timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1000)  # Update every second

    def _setup_tray_icon(self):
        """Set up system tray icon for control."""
        if QT_AVAILABLE and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))

            # Create tray menu
            tray_menu = QMenu()
            show_action = QAction("Show HUD", self)
            hide_action = QAction("Hide HUD", self)
            quit_action = QAction("Quit", self)

            show_action.triggered.connect(self.show)
            hide_action.triggered.connect(self.hide)
            quit_action.triggered.connect(QApplication.instance().quit)

            tray_menu.addAction(show_action)
            tray_menu.addAction(hide_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def _update_telemetry(self):
        """Update all telemetry displays."""
        try:
            # Update time
            current_time = datetime.now().strftime("%H:%M:%S")
            self.time_label.setText(current_time)

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_label.setText(f"CPU: {cpu_percent:5.1f}%")

            # Memory usage
            memory = psutil.virtual_memory()
            self.ram_label.setText(f"RAM: {memory.percent:5.1f}%")

            # Temperature (if available)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try to get CPU temperature
                    temp_keys = ['coretemp', 'cpu_thermal', 'k10temp']
                    temp_c = None
                    for key in temp_keys:
                        if key in temps:
                            temp_c = temps[key][0].current
                            break
                    if temp_c is None:
                        # Use first available temperature
                        for key, entries in temps.items():
                            if entries:
                                temp_c = entries[0].current
                                break
                    if temp_c is not None:
                        self.temp_label.setText(f"Temp: {temp_c:5.1f}°C")
                    else:
                        self.temp_label.setText("Temp: --°C")
                else:
                    self.temp_label.setText("Temp: --°C")
            except Exception:
                self.temp_label.setText("Temp: --°C")

            # Network speed
            net_io = psutil.net_io_counters()
            current_time = time.time()
            time_delta = current_time - self._last_net_time

            if time_delta > 0:
                bytes_sent = net_io.bytes_sent - self._last_net_io.bytes_sent
                bytes_recv = net_io.bytes_recv - self._last_net_io.bytes_recv

                send_kbps = (bytes_sent / 1024) / time_delta
                recv_kbps = (bytes_recv / 1024) / time_delta

                total_kbps = send_kbps + recv_kbps
                self.net_label.setText(f"Net: {total_kbps:6.1f} KB/s")

                self._last_net_io = net_io
                self._last_net_time = current_time
            else:
                self.net_label.setText("Net: -- KB/s")

        except Exception as e:
            # In case of any error, show error state
            self.cpu_label.setText("CPU: ERR")
            self.ram_label.setText("RAM: ERR")
            self.temp_label.setText("Temp: ERR")
            self.net_label.setText("Net: ERR")


def main():
    """Main entry point for the HUD widget."""
    if not QT_AVAILABLE:
        print("[UI Overlay] Qt6 is required but not available.")
        print("[UI Overlay] Please install PyQt6: pip install PyQt6")
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Create and show the HUD
    hud = TelemetryHUD()
    hud.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())