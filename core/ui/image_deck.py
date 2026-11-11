"""Worker-backed HUD image deck; paint work is delegated to QLabel."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


IMAGE_PANEL_MAX_W = 480
IMAGE_PANEL_MAX_H = 360
IMAGE_PANEL_MARGIN = 12


class _LoadSignals(QObject):
    """Qt signals emitted by an image load task: loaded with the scaled image, or failed."""
    loaded = pyqtSignal(QImage)
    failed = pyqtSignal()


class _ImageLoadTask(QRunnable):
    """Thread-pool task that loads an image from disk and scales it to a target size."""
    def __init__(self, path: str, size) -> None:
        """Store the image path, target size and a fresh signals object."""
        super().__init__()
        self.path, self.size, self.signals = path, size, _LoadSignals()

    @pyqtSlot()
    def run(self) -> None:
        """Load the image; emit failed if it is null, otherwise emit loaded with an aspect-preserving smooth scale."""
        image = QImage(self.path)
        if image.isNull():
            self.signals.failed.emit()
            return
        self.signals.loaded.emit(image.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))


class ImageDeckPanel(QFrame):
    """Draggable themed panel whose image decode and scale occur off the UI thread."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        """Build the fixed-size frameless deck panel with a header, close button, image label and caption."""
        super().__init__(parent)
        self.setFixedSize(IMAGE_PANEL_MAX_W, IMAGE_PANEL_MAX_H)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._drag_offset = None
        self._pool = QThreadPool.globalInstance()
        self.setStyleSheet("QFrame { background: #06111f; border: 1px solid #00f0ff; } QLabel { color: #b8c9ff; border: none; } QPushButton { color: #00f0ff; background: transparent; border: none; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(IMAGE_PANEL_MARGIN, IMAGE_PANEL_MARGIN, IMAGE_PANEL_MARGIN, IMAGE_PANEL_MARGIN)
        header = QHBoxLayout(); header.addWidget(QLabel("IMG DECK")); header.addStretch()
        close = QPushButton("×"); close.clicked.connect(self.hide); header.addWidget(close); layout.addLayout(header)
        self.image = QLabel("Awaiting image…"); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.image, 1)
        self.caption = QLabel(""); self.caption.setWordWrap(True); layout.addWidget(self.caption)

    def show_image(self, path: str, caption: str = "") -> None:
        """Set the caption, decode/scale `path` on the thread pool, and show the panel."""
        self.caption.setText(caption)
        self.image.setText("Loading…")
        task = _ImageLoadTask(path, self.image.size())
        task.signals.loaded.connect(self._set_image)
        task.signals.failed.connect(lambda: self.image.setText("Image unavailable"))
        self._pool.start(task)
        self.show(); self.raise_()

    def _set_image(self, image: QImage) -> None:
        """Display the loaded image in the image label."""
        self.image.setPixmap(QPixmap.fromImage(image))

    def mousePressEvent(self, event) -> None:
        """Record the drag offset when the left mouse button is pressed."""
        if event.button() == Qt.MouseButton.LeftButton: self._drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:
        """Move the panel with the mouse while a drag is in progress."""
        if self._drag_offset is not None: self.move(self.pos() + event.position().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        """End any drag in progress."""
        self._drag_offset = None

    def hideEvent(self, event) -> None:
        """Emit the closed signal, then run the default hide handling."""
        self.closed.emit(); super().hideEvent(event)
