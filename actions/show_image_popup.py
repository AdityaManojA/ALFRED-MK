# actions/show_image_popup.py
"""
Action to show an image popup overlay.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QPixmap, QFont, QCursor
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPoint

from ui import tech_font, mono_font, C


class ImagePopupOverlay(QWidget):
    """Popup overlay to display an image with a dismiss button."""

    dismissed = pyqtSignal()

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self._drag_pos = QPoint()
        self._dragging = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(f"""
            ImagePopupOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Add a small grip area at the top for dragging hint
        self._drag_label = QLabel("⡿⠋⠉⠙⠚⠁")  # Braille pattern for visual grip hint
        self._drag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_label.setFixedHeight(16)
        self._drag_label.setStyleSheet(f"""
            QLabel {{
                color: {C.TEXT_DIM};
                font-size: 8px;
                padding: 2px;
            }}
        """)
        layout.addWidget(self._drag_label)

        # Image label
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale image to fit reasonably, max width/height 400px while keeping aspect ratio
            scaled = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText(f"[Image not found: {image_path}]")
            self._image_label.setStyleSheet(f"color: {C.TEXT_MED};")
        layout.addWidget(self._image_label)

        # Dismiss button
        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setFont(tech_font(9, QFont.Weight.Bold))
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setFixedHeight(28)
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
        """)
        dismiss_btn.clicked.connect(self.hide)
        dismiss_btn.clicked.connect(self.dismissed.emit)
        layout.addWidget(dismiss_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.accept()

    def show_centered(self, parent: QWidget):
        """Show the popup centered over the parent widget."""
        try:
            if parent:
                self.move(
                    parent.x() + (parent.width() - self.width()) // 2,
                    parent.y() + (parent.height() - self.height()) // 2,
                )
            self.show()
            self.raise_()
            self.activateWindow()
        except Exception as e:
            # Fallback position if centering fails
            self.move(100, 100)
            self.show()


def action(parameters: dict, player=None, speak=None, response=None, session_memory=None) -> str:
    """Show an image popup overlay."""
    try:
        image_path = parameters.get("image_path")
        if not image_path:
            return "Error: image_path parameter is required for show_image_popup action."

        # Resolve relative paths relative to the project root
        if not os.path.isabs(image_path):
            # Assume relative to the project root (two levels up from this file)
            project_root = Path(__file__).resolve().parent.parent
            image_path = str((project_root / image_path).resolve())

        if not os.path.exists(image_path):
            return f"Error: Image file not found: {image_path}"

        if player is None:
            return "Error: Player context not available to show overlay."

        # Get the central widget to parent the overlay
        if hasattr(player, '_win') and hasattr(player._win, 'centralWidget'):
            central_widget = player._win.centralWidget()
        elif hasattr(player, 'centralWidget'):
            central_widget = player.centralWidget()
        else:
            return "Error: Could not get central widget."

        if central_widget is None:
            return "Error: Could not get central widget."

        # Create and show the overlay
        overlay = ImagePopupOverlay(image_path, parent=central_widget)
        # Keep a reference to prevent garbage collection
        player._image_popup_overlay = overlay
        overlay.show_centered(central_widget)

        return f"Showing image popup: {image_path}"
    except Exception as e:
        return f"Error showing image popup: {str(e)}"


TOOL = {
    "name": "show_image_popup",
    "description": "Show an image popup overlay with a dismiss button. Parameters: image_path (string, path to image file).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "image_path": {
                "type": "STRING",
                "description": "Path to the image file to display (can be relative to project root)."
            }
        },
        "required": ["image_path"]
    },
    "scheduling": "WHEN_IDLE",  # Does not block speech
    "handler": action
}