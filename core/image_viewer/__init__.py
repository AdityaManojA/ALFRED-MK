"""
core/image_viewer — Image Viewer v2 (LAZY + FIT + FETCH).

Re-exports core primitives and provides a lazy registry factory.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtWidgets import QWidget

from core.image_viewer.fit import (
    fit_size,
    VIEWER_MAX_SCREEN_FRAC,
    VIEWER_MIN_PX,
    VIEWER_MAX_DECODE_PX,
)
from core.image_viewer.cache import (
    ImageViewerCache,
    IMAGE_CACHE_MAX_MB,
    IMAGE_CACHE_DIR,
)
from core.image_viewer.fetch import (
    fetch_image,
    validate_image_bytes,
    extract_host,
    FetchResult,
    ReferenceImageSession,
    FETCH_TIMEOUT_S,
    FETCH_MAX_MB,
    ALLOWED_CONTENT_TYPES,
)
from core.image_viewer.viewer import (
    ImageViewerWindow,
    Z_IMAGE_VIEWER,
)


def get_image_viewer(parent: Optional[QWidget] = None) -> ImageViewerWindow:
    """Retrieve or lazily construct the singleton ImageViewerWindow.

    Thread-safe / Qt-safe: lookups go through core.registry.
    Does NOT construct the viewer at boot — created strictly on first request.
    """
    from core.registry import lookup, register
    viewer = lookup("image_viewer")
    if viewer is None:
        viewer = ImageViewerWindow(parent=parent)

        def _handle_next():
            sess = lookup("reference_image_session")
            if sess is not None:
                res = sess.next_candidate()
                if res.success:
                    cand_info = f"{sess.current_index + 1}/{sess.total_candidates}" if sess.total_candidates > 1 else ""
                    viewer.show_image(res.file_path or res.data, caption=res.attribution, host=res.host, candidate_info=cand_info)

        def _handle_prev():
            sess = lookup("reference_image_session")
            if sess is not None:
                res = sess.previous_candidate()
                if res.success:
                    cand_info = f"{sess.current_index + 1}/{sess.total_candidates}" if sess.total_candidates > 1 else ""
                    viewer.show_image(res.file_path or res.data, caption=res.attribution, host=res.host, candidate_info=cand_info)

        viewer.next_requested.connect(_handle_next)
        viewer.prev_requested.connect(_handle_prev)
        register("image_viewer", viewer)
    elif parent is not None and viewer.parent() is None:
        viewer.setParent(parent)
    return viewer


__all__ = [
    "ImageViewerWindow",
    "ImageViewerCache",
    "FetchResult",
    "ReferenceImageSession",
    "get_image_viewer",
    "fit_size",
    "fetch_image",
    "validate_image_bytes",
    "extract_host",
    "VIEWER_MAX_SCREEN_FRAC",
    "VIEWER_MIN_PX",
    "VIEWER_MAX_DECODE_PX",
    "FETCH_TIMEOUT_S",
    "FETCH_MAX_MB",
    "ALLOWED_CONTENT_TYPES",
    "IMAGE_CACHE_MAX_MB",
    "IMAGE_CACHE_DIR",
    "Z_IMAGE_VIEWER",
]
