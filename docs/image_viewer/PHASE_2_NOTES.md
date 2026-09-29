# Image Viewer v2 — Phase 2: Lazy Viewer Implementation Notes

## Changes Made
1. **Removed Eager Initialization in `MainWindow.__init__`**:
   - Replaced eager `self._image_deck = ImageDeckPanel(self)` in `ui.py:8012` with `self._image_deck = None`.
   - The viewer window and image load tasks are no longer constructed at boot, ensuring idle CPU and memory remain ~0.

2. **Implemented Lazy Registry Factory (`core/image_viewer/__init__.py`)**:
   - Added `get_image_viewer(parent=None) -> ImageViewerWindow`.
   - Looks up `"image_viewer"` in `core.registry`. If absent, instantiates `ImageViewerWindow` and registers it.
   - Connected `MainWindow.show_image_deck(path, caption)` to lazily fetch the viewer on first invocation.

3. **Memory Cleanup on Close**:
   - `ImageViewerWindow.close_viewer()` hides the window and calls `_canvas.clear()`, setting `_raw_image = None` and `_cached_pixmap = None`.
   - Memory is completely released upon dismissal.

4. **Unit Tests (`tests/test_lazy_viewer.py`)**:
   - Asserted that clean boot constructs no viewer in registry.
   - Asserted that first request lazily constructs and registers the viewer.
   - Asserted that showing an image allocates pixmap and closing frees all pixmap and image buffers.

## Graphify Nodes Referenced
- `core_image_viewer_get_image_viewer` (`get_image_viewer` in `core/image_viewer/__init__.py`)
- `core_image_viewer_imageviewerwindow` (`ImageViewerWindow` in `core/image_viewer/viewer.py`)
- `core_registry_lookup` (`lookup` in `core/registry.py`)
- `ui_mainwindow_show_image_deck` (`MainWindow.show_image_deck` in `ui.py`)
