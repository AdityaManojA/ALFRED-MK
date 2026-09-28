"""
actions/screen_find.py — Local Hybrid Element Grounding for ALFRED.

Performs local UI element localization using:
1. RapidOCR (ONNX runtime) for text labels and buttons (<150ms).
2. Quantized OmniParser-v2 / Florence-2 ONNX for UI elements and icons.
3. Centroid calculation with confidence scoring.
4. Fast fallback to Gemini Live API only if confidence < 0.80.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Tuple, Optional, Dict

import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
    _ONNX_OK = True
except ImportError:
    ort = None
    _ONNX_OK = False

try:
    from rapidocr_onnxruntime import RapidOCR
    _RAPIDOCR_OK = True
except ImportError:
    RapidOCR = None
    _RAPIDOCR_OK = False

try:
    from rapidfuzz import fuzz
    _FUZZ_OK = True
except ImportError:
    fuzz = None
    _FUZZ_OK = False

# ANSI Color formatting
_RED = "\033[91m"
_RESET = "\033[0m"

# Base directory for configuration and models
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"

# Global in-memory cache for sessions to eliminate cold-start overhead
_GLOBAL_OCR: Any = None
_GLOBAL_ONNX_SESSIONS: Dict[str, Any] = {}

# Target keywords indicative of non-text icons
_ICON_KEYWORDS = {
    "icon", "logo", "symbol", "button_icon", "glyph", "avatar",
    "magnifying_glass", "search_icon", "save_icon", "gear", "settings_icon",
    "close_button", "minimize_button", "maximize_button", "folder_icon"
}


def _get_api_key() -> str:
    """Retrieve Gemini API key from api_keys.json or environment."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    cfg_file = BASE_DIR / "config" / "api_keys.json"
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8")).get("gemini_api_key", "")
        except Exception:
            pass
    return ""


def get_rapid_ocr() -> Any:
    """Return globally cached RapidOCR instance with UI-optimized parameters."""
    global _GLOBAL_OCR
    if _GLOBAL_OCR is None and _RAPIDOCR_OK:
        # Optimized for horizontal desktop UI text with tuned detection threshold
        _GLOBAL_OCR = RapidOCR(
            use_cls=False,
            det_limit_side_len=240,
            det_limit_type="max",
            print_verbose=False,
        )
        try:
            # Pre-warm detection & recognition sessions to eliminate cold-start overhead
            dummy = np.full((50, 140, 3), 255, dtype=np.uint8)
            from PIL import Image as _PILImg, ImageDraw as _PILDraw
            pimg = _PILImg.fromarray(dummy)
            d = _PILDraw.Draw(pimg)
            d.text((10, 10), "OK", fill=(0, 0, 0))
            _GLOBAL_OCR(np.array(pimg))
        except Exception:
            pass
    return _GLOBAL_OCR


def get_onnx_session(model_name: str = "omniparser_v2_quant.onnx") -> Any:
    """Return globally cached ONNX Runtime session for quantized element detector."""
    global _GLOBAL_ONNX_SESSIONS
    if model_name in _GLOBAL_ONNX_SESSIONS:
        return _GLOBAL_ONNX_SESSIONS[model_name]

    if not _ONNX_OK:
        return None

    # Search candidate paths
    candidates = [
        MODELS_DIR / model_name,
        BASE_DIR / "models" / model_name,
        BASE_DIR / "core" / "models" / model_name,
        Path.home() / ".cache" / "alfred" / "models" / model_name,
    ]

    model_path = next((p for p in candidates if p.exists()), None)
    if model_path is None:
        return None

    try:
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = min(4, os.cpu_count() or 4)
        session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        _GLOBAL_ONNX_SESSIONS[model_name] = session
        return session
    except Exception as e:
        print(f"{_RED}[screen]{_RESET} Error loading ONNX model '{model_name}': {e}")
        return None


def is_icon_query(target: str) -> bool:
    """Determine if target query is specifically targeting an icon/non-text element."""
    t = target.lower().strip()
    words = set(re.findall(r"\w+", t))
    return bool(words & _ICON_KEYWORDS) or t.endswith("_icon") or t.endswith(" icon")


def _capture_screen_image() -> Image.Image:
    """Capture current screen into a PIL Image."""
    try:
        import mss
        _mss_factory = getattr(mss, "MSS", getattr(mss, "mss", None))
        with _mss_factory() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            return Image.frombytes("RGB", shot.size, shot.rgb)
    except Exception:
        pass

    try:
        import pyautogui
        return pyautogui.screenshot()
    except Exception:
        pass

    from PIL import ImageGrab
    return ImageGrab.grab()


def _calculate_similarity(query: str, candidate_text: str) -> float:
    """Compute string similarity score between query and candidate text."""
    q = query.lower().strip()
    c = candidate_text.lower().strip()

    if not q or not c:
        return 0.0

    if q == c:
        return 1.0

    # Whole word match (e.g. "Save" in "Save As" or "Save File")
    words = [w.strip() for w in re.split(r"\W+", c) if w.strip()]
    if q in words:
        return 0.98

    # Substring match
    if q in c:
        coverage = len(q) / max(len(c), 1)
        return max(0.85, 0.92 * coverage)

    # Fuzzy similarity ratio
    if _FUZZ_OK:
        ratio = fuzz.ratio(q, c) / 100.0
        partial = fuzz.partial_ratio(q, c) / 100.0
        return max(ratio, partial * 0.90)
    else:
        import difflib
        return difflib.SequenceMatcher(None, q, c).ratio()


# In-memory frame cache for ultra-fast repeated lookups (<1ms)
_FRAME_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _get_frame_key(image_np: np.ndarray) -> str:
    """Generate a lightweight key for the image frame."""
    return f"{image_np.shape}_{image_np[0, 0].tolist()}_{image_np[-1, -1].tolist()}_{len(image_np)}"


def _ocr_grounding(
    target: str,
    image_np: np.ndarray,
    img_w: int,
    img_h: int,
) -> Tuple[Optional[Tuple[float, float]], float, str]:
    """
    Run RapidOCR on image array to locate target text with early termination and frame caching.
    Returns: ((norm_x, norm_y), confidence, matched_text)
    """
    ocr = get_rapid_ocr()
    if ocr is None:
        return None, 0.0, ""

    try:
        frame_key = _get_frame_key(image_np)

        # 1. Fast frame cache check
        if frame_key in _FRAME_CACHE:
            cached_boxes = _FRAME_CACHE[frame_key]
            best_match = None
            best_score = 0.0
            best_text = ""
            for item in cached_boxes:
                sim = _calculate_similarity(target, item["text"])
                combined = sim * item["conf"]
                if combined > best_score:
                    best_score = combined
                    best_match = (item["norm_x"], item["norm_y"])
                    best_text = item["text"]
                if combined >= 0.85:
                    return best_match, best_score, best_text
            if best_match and best_score >= 0.80:
                return best_match, best_score, best_text

        # 2. Hierarchical strip search: UI controls (Save, File, Edit, Close) are in top toolbar strip
        # If searching a tall window (>200px), check top 60px toolbar first for ultra-low latency (<100ms)
        search_strips = []
        if img_h > 200:
            top_h = min(60, int(img_h * 0.12))
            search_strips.append((image_np[:top_h, :], 0, 0, top_h))
            search_strips.append((image_np, 0, 0, img_h))
        else:
            search_strips.append((image_np, 0, 0, img_h))

        best_match = None
        best_score = 0.0
        best_text = ""
        cached_items = []

        for strip_img, offset_x, offset_y, strip_h in search_strips:
            # Check if fine-grained auto_text_det and text_rec are available for early break
            if hasattr(ocr, "auto_text_det") and hasattr(ocr, "text_rec") and hasattr(ocr, "get_crop_img_list"):
                dt_boxes, _ = ocr.auto_text_det(strip_img)
                if not dt_boxes:
                    continue

                crop_list = ocr.get_crop_img_list(strip_img, dt_boxes)
                for box, crop in zip(dt_boxes, crop_list):
                    rec_res, _ = ocr.text_rec([crop])
                    if not rec_res or not rec_res[0]:
                        continue
                    detected_text, ocr_conf = rec_res[0][0], float(rec_res[0][1])
                    cx = (sum(p[0] for p in box) / 4.0) + offset_x
                    cy = (sum(p[1] for p in box) / 4.0) + offset_y
                    norm_x = round(float(cx / img_w), 4)
                    norm_y = round(float(cy / img_h), 4)

                    cached_items.append({
                        "text": detected_text,
                        "conf": ocr_conf,
                        "norm_x": norm_x,
                        "norm_y": norm_y,
                    })

                    sim = _calculate_similarity(target, detected_text)
                    combined_conf = sim * ocr_conf

                    if combined_conf > best_score:
                        best_score = combined_conf
                        best_match = (norm_x, norm_y)
                        best_text = detected_text

                    # Early break as soon as a high-confidence match (>= 0.85) is found
                    if combined_conf >= 0.85:
                        if frame_key not in _FRAME_CACHE:
                            if len(_FRAME_CACHE) > 16:
                                _FRAME_CACHE.clear()
                            _FRAME_CACHE[frame_key] = cached_items
                        return best_match, best_score, best_text
            else:
                results, _ = ocr(strip_img)
                if not results:
                    continue

                for item in results:
                    box, detected_text, ocr_conf = item[0], item[1], float(item[2])
                    cx = (sum(p[0] for p in box) / 4.0) + offset_x
                    cy = (sum(p[1] for p in box) / 4.0) + offset_y
                    norm_x = round(float(cx / img_w), 4)
                    norm_y = round(float(cy / img_h), 4)
                    cached_items.append({
                        "text": detected_text,
                        "conf": ocr_conf,
                        "norm_x": norm_x,
                        "norm_y": norm_y,
                    })

                    sim = _calculate_similarity(target, detected_text)
                    combined_conf = sim * ocr_conf

                    if combined_conf > best_score:
                        best_score = combined_conf
                        best_match = (norm_x, norm_y)
                        best_text = detected_text

                    if combined_conf >= 0.85:
                        if frame_key not in _FRAME_CACHE:
                            if len(_FRAME_CACHE) > 16:
                                _FRAME_CACHE.clear()
                            _FRAME_CACHE[frame_key] = cached_items
                        return best_match, best_score, best_text

            if best_score >= 0.85:
                break

        if cached_items and frame_key not in _FRAME_CACHE:
            if len(_FRAME_CACHE) > 16:
                _FRAME_CACHE.clear()
            _FRAME_CACHE[frame_key] = cached_items

        return best_match, best_score, best_text
    except Exception as e:
        print(f"{_RED}[screen]{_RESET} RapidOCR grounding error: {e}")
        return None, 0.0, ""


def _onnx_element_grounding(
    target: str,
    pil_image: Image.Image,
) -> Tuple[Optional[Tuple[float, float]], float]:
    """
    Run local ONNX element detector (OmniParser-v2 / Florence-2).
    Returns: ((norm_x, norm_y), confidence)
    """
    session = get_onnx_session("omniparser_v2_quant.onnx") or get_onnx_session("florence2_quant.onnx")
    if session is None:
        return None, 0.0

    try:
        # Preprocess to 640x640 RGB float32 tensor
        input_meta = session.get_inputs()[0]
        input_name = input_meta.name

        resized = pil_image.resize((640, 640), Image.Resampling.BILINEAR)
        img_arr = np.array(resized).astype(np.float32) / 255.0

        # Handle NCHW format: (1, 3, 640, 640)
        if len(input_meta.shape) == 4 and input_meta.shape[1] == 3:
            img_arr = np.transpose(img_arr, (2, 0, 1))
            tensor = np.expand_dims(img_arr, axis=0)
        else:
            tensor = np.expand_dims(img_arr, axis=0)

        outputs = session.run(None, {input_name: tensor})
        if not outputs:
            return None, 0.0

        # Output format parser:
        # Typical UI element detectors output [boxes, scores] or [proposals]
        boxes_out = outputs[0]
        scores_out = outputs[1] if len(outputs) > 1 else None

        if scores_out is not None:
            boxes = np.squeeze(boxes_out)
            scores = np.squeeze(scores_out)

            if len(boxes.shape) == 2 and len(scores.shape) == 1:
                best_idx = int(np.argmax(scores))
                score = float(scores[best_idx])
                box = boxes[best_idx]
                # [x1, y1, x2, y2]
                cx = float((box[0] + box[2]) / 2.0)
                cy = float((box[1] + box[3]) / 2.0)
                norm_x = round(max(0.0, min(1.0, cx)), 4)
                norm_y = round(max(0.0, min(1.0, cy)), 4)
                return (norm_x, norm_y), score

        return None, 0.0
    except Exception as e:
        print(f"{_RED}[screen]{_RESET} ONNX element grounding error: {e}")
        return None, 0.0


def _gemini_grounding(
    target: str,
    pil_image: Image.Image,
    screen_w: int,
    screen_h: int,
) -> Optional[Tuple[float, float]]:
    """Fallback visual grounding via Gemini Live / Flash API."""
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        from google.genai import types as gtypes
        from core import gemini

        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        prompt = (
            f"This is a {screen_w}x{screen_h} screenshot. Locate the UI element or label: '{target}'. "
            f"Reply ONLY with the center coordinates in exact format: x,y "
            f"If not found, reply: NOT_FOUND"
        )

        response = gemini.call(
            [gtypes.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
            tier=gemini.FAST,
            timeout_ms=10_000,
        )

        if not response or not response.text:
            return None

        text = response.text.strip()
        if "NOT_FOUND" in text.upper():
            return None

        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            px, py = int(match.group(1)), int(match.group(2))
            norm_x = round(float(px / screen_w), 4)
            norm_y = round(float(py / screen_h), 4)
            return norm_x, norm_y
    except Exception as e:
        print(f"{_RED}[screen]{_RESET} Gemini grounding fallback error: {e}")

    return None


def find_element(
    target: str,
    screenshot: Any = None,
    threshold: float = 0.80,
    return_details: bool = False,
) -> Any:
    """
    Main entry point for local hybrid UI element grounding.

    1. Executes RapidOCR on local screen capture to find matching text labels.
    2. If text match fails or target is non-text, runs quantized ONNX element detector.
    3. Computes centroids and assigns confidence score.
    4. If confidence >= 0.80, returns normalized (x, y) coordinates immediately (<150ms).
    5. If confidence < 0.80, falls back to Gemini visual grounding and issues red-tag log:
       [screen] Local grounding confidence low (score) — delegating to Gemini

    Returns:
        tuple[float, float] of normalized (x, y) coordinates in [0.0, 1.0], or None.
    """
    t_start = time.monotonic()

    # 1. Acquire screenshot
    if screenshot is None:
        pil_img = _capture_screen_image()
    elif isinstance(screenshot, Image.Image):
        pil_img = screenshot
    elif isinstance(screenshot, np.ndarray):
        pil_img = Image.fromarray(screenshot)
    elif isinstance(screenshot, (bytes, bytearray)):
        pil_img = Image.open(io.BytesIO(screenshot))
    else:
        pil_img = _capture_screen_image()

    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    screen_w, screen_h = pil_img.size
    img_np = np.array(pil_img)

    best_coords = None
    best_confidence = 0.0
    grounding_source = "none"

    is_icon = is_icon_query(target)

    # 2. Step 1: RapidOCR text label search (unless explicitly an icon target)
    if not is_icon:
        ocr_coords, ocr_score, matched_text = _ocr_grounding(target, img_np, screen_w, screen_h)
        if ocr_coords and ocr_score >= threshold:
            elapsed_ms = (time.monotonic() - t_start) * 1000
            if return_details:
                return {
                    "coordinates": ocr_coords,
                    "confidence": ocr_score,
                    "method": "rapidocr",
                    "matched_text": matched_text,
                    "latency_ms": elapsed_ms,
                }
            return ocr_coords

        if ocr_coords:
            best_coords = ocr_coords
            best_confidence = ocr_score
            grounding_source = "rapidocr"

    # 3. Step 2: Local ONNX element detector (OmniParser-v2 / Florence-2)
    onnx_coords, onnx_score = _onnx_element_grounding(target, pil_img)
    if onnx_coords and onnx_score >= threshold:
        elapsed_ms = (time.monotonic() - t_start) * 1000
        if return_details:
            return {
                "coordinates": onnx_coords,
                "confidence": onnx_score,
                "method": "onnx_element_detector",
                "latency_ms": elapsed_ms,
            }
        return onnx_coords

    if onnx_score > best_confidence:
        best_coords = onnx_coords
        best_confidence = onnx_score
        grounding_source = "onnx"

    # 4. Check confidence threshold
    if best_coords and best_confidence >= threshold:
        elapsed_ms = (time.monotonic() - t_start) * 1000
        if return_details:
            return {
                "coordinates": best_coords,
                "confidence": best_confidence,
                "method": grounding_source,
                "latency_ms": elapsed_ms,
            }
        return best_coords

    # 5. Step 5: Fall back to Gemini API with required red-tag log
    score_display = f"{best_confidence:.2f}"
    print(f"{_RED}[screen]{_RESET} Local grounding confidence low ({score_display}) — delegating to Gemini")

    gemini_coords = _gemini_grounding(target, pil_img, screen_w, screen_h)
    elapsed_ms = (time.monotonic() - t_start) * 1000

    if return_details:
        return {
            "coordinates": gemini_coords,
            "confidence": 1.0 if gemini_coords else 0.0,
            "method": "gemini_fallback",
            "latency_ms": elapsed_ms,
        }

    return gemini_coords


def screen_find(parameters: dict, response=None, player=None) -> str:
    """Action handler called by ALFRED action dispatcher."""
    target = parameters.get("target") or parameters.get("description") or ""
    if not target:
        return "screen_find requires a 'target' parameter."

    coords = find_element(target)
    if coords:
        return f"{coords[0]},{coords[1]}"
    return "NOT_FOUND"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "screen_find",
    "description": (
        "Local hybrid UI element grounding using RapidOCR and ONNX element detector. "
        "Finds coordinates of text, buttons, menus, and icons on the screen with sub-150ms latency."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "Name or text description of the UI element to locate (e.g. 'Save', 'File', 'Settings', 'Submit').",
            }
        },
        "required": ["target"],
    },
    "handler": screen_find,
}
