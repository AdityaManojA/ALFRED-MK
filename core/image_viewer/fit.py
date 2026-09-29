"""
core/image_viewer/fit.py — Pure geometric sizing calculations for Image Viewer v2.

Enforces:
- Constant bounds: VIEWER_MAX_SCREEN_FRAC, VIEWER_MIN_PX, VIEWER_MAX_DECODE_PX
- Never crops and never upscales beyond native size (unless below VIEWER_MIN_PX)
- Clamped to available screen geometry
- Preserves native aspect ratio
- No GUI dependencies (pure mathematical calculations)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
VIEWER_MAX_SCREEN_FRAC: float = 0.85
VIEWER_MIN_PX: int = 240
VIEWER_MAX_DECODE_PX: int = 3840


def fit_size(
    img_w: int,
    img_h: int,
    avail_w: int,
    avail_h: int,
    frac: float = VIEWER_MAX_SCREEN_FRAC,
    dpr: float = 1.0,
) -> tuple[int, int]:
    """Calculate the fitted (width, height) for an image window.

    Parameters
    ----------
    img_w : int
        Native image width in pixels.
    img_h : int
        Native image height in pixels.
    avail_w : int
        Available screen width in pixels (or DIPs).
    avail_h : int
        Available screen height in pixels (or DIPs).
    frac : float
        Maximum fraction of the screen the viewer may occupy.
    dpr : float
        Device pixel ratio (for high-DPI scaling).

    Returns
    -------
    tuple[int, int]
        (fitted_width, fitted_height) preserving aspect ratio.
    """
    if img_w <= 0 or img_h <= 0:
        return (VIEWER_MIN_PX, VIEWER_MIN_PX)

    if avail_w <= 0 or avail_h <= 0:
        return (VIEWER_MIN_PX, VIEWER_MIN_PX)

    # 1. Downscale huge images exceeding max decode limit (e.g. 8K)
    curr_w = float(img_w)
    curr_h = float(img_h)
    if curr_w > VIEWER_MAX_DECODE_PX or curr_h > VIEWER_MAX_DECODE_PX:
        decode_scale = min(VIEWER_MAX_DECODE_PX / curr_w, VIEWER_MAX_DECODE_PX / curr_h)
        curr_w = max(1.0, curr_w * decode_scale)
        curr_h = max(1.0, curr_h * decode_scale)

    # 2. Compute maximum allowable dimensions on screen
    max_w = max(float(VIEWER_MIN_PX), float(avail_w) * frac)
    max_h = max(float(VIEWER_MIN_PX), float(avail_h) * frac)

    # 3. Downscale if exceeding available screen geometry (never upscale beyond native)
    screen_scale = min(1.0, max_w / curr_w, max_h / curr_h)
    fitted_w = curr_w * screen_scale
    fitted_h = curr_h * screen_scale

    # 4. Usability minimum: if both or either dimension is below VIEWER_MIN_PX,
    # scale up preserving aspect ratio up to max bounds so the window chrome is usable.
    if fitted_w < VIEWER_MIN_PX or fitted_h < VIEWER_MIN_PX:
        min_scale = max(VIEWER_MIN_PX / fitted_w, VIEWER_MIN_PX / fitted_h)
        # But do not exceed max screen fraction
        max_possible_scale = min(max_w / fitted_w, max_h / fitted_h)
        applied_scale = min(min_scale, max_possible_scale)
        fitted_w *= applied_scale
        fitted_h *= applied_scale

    return (int(round(fitted_w)), int(round(fitted_h)))
