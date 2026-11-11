"""Suite-wide fixtures.

Keeps tests from writing persistent window state into the real repo
(data/ui_state.json): any MainWindow a test builds saves its position
to a per-test temp file instead.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_ui_state(tmp_path, monkeypatch):
    try:
        import ui.drag_handler as drag_handler
    except Exception:  # GUI deps unavailable: nothing to isolate
        yield
        return
    monkeypatch.setattr(drag_handler, "UI_STATE_FILE", tmp_path / "ui_state.json")
    monkeypatch.setattr(drag_handler, "DATA_DIR", tmp_path)
    yield
