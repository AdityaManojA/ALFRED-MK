# Image Viewer v2 — Phase 1: Boot Fix Implementation Notes

## Changes Made
1. **Added `set_media_arbiter` to `JarvisUI` in `ui.py`**:
   - Signature: `set_media_arbiter(self, arbiter) -> None`
   - Forwards directly to `self._win.set_media_arbiter(arbiter)`.
   - Connects `MediaArbiter` audio state changes to `MainWindow` and `TronScoreBackgroundPlayer`.

2. **Added Missing Delegate Methods and Properties to `JarvisUI`**:
   - `toggle_mute(self) -> None`: Forwards to `self._win._toggle_mute()`, used by the mobile remote server in `main.py:3052`.
   - `on_wake_install`: Property getter/setter forwarding to `self._win.on_wake_install`.
   - `wake_is_ready`: Property getter/setter forwarding to `self._win.wake_is_ready`.
   - `request_say`: Property getter/setter forwarding to `self._win.request_say`.

3. **Regression Test Created (`tests/test_ui_mismatches_ast.py`)**:
   - Performs a complete AST walk of `main.py` finding all `self.ui.<attr>` and `ui.<attr>` accesses.
   - Asserts that every single attribute exists on `JarvisUI`.
   - Asserts `set_media_arbiter` has the expected signature `(self, arbiter)`.
   - Verified passing cleanly.

4. **Regression Verification**:
   - `JarvisLive` instantiation test passes with `set_media_arbiter` verified.
   - All 75 tests in `tests/hud_video/` remain passing.

## Graphify Nodes Referenced
- `ui_jarvisui_set_media_arbiter` (`JarvisUI.set_media_arbiter` in `ui.py`)
- `ui_mainwindow_set_media_arbiter` (`MainWindow.set_media_arbiter` in `ui.py`)
- `core_media_arbiter_get_media_arbiter` (`get_media_arbiter` in `core/media/arbiter.py`)
- `core_media_arbiter_mediaarbiter` (`MediaArbiter` in `core/media/arbiter.py`)
- `tests_test_ui_mismatches_ast` (`tests/test_ui_mismatches_ast.py`)
