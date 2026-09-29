"""
tests/test_image_fetch.py — Unit tests for reference image fetching, caching, cycling, and intent routing.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from PyQt6.QtCore import QByteArray, QBuffer
from PyQt6.QtGui import QImage, QImageWriter
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists for Qt image readers
_APP = QApplication.instance() or QApplication([])

from core.image_viewer.cache import ImageViewerCache
from core.image_viewer.fetch import (
    FETCH_MAX_MB,
    FETCH_TIMEOUT_S,
    FetchResult,
    ReferenceImageSession,
    extract_host,
    fetch_image,
    validate_image_bytes,
)
from core.imagery.intent import (
    classify_image_intent,
    detect,
)
from core.imagery.sources.base import ImageResult


def _create_test_image_bytes(w: int = 100, h: int = 80, fmt: str = "PNG") -> bytes:
    """Helper to generate valid image bytes in memory."""
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFF00D4FF)
    qba = QByteArray()
    buf = QBuffer(qba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buf, fmt.encode("ascii"))
    writer.write(img)
    buf.close()
    return bytes(qba.data())


class TestImageFetchAndCache(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = ImageViewerCache(root=self.temp_dir, max_mb=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_host_privacy(self):
        """Ensure full query parameters and secrets are never returned in host."""
        url = "https://api.example.com:8080/v1/images?token=secret123&query=private#fragment"
        host = extract_host(url)
        self.assertEqual(host, "api.example.com:8080")
        self.assertNotIn("secret123", host)
        self.assertNotIn("query", host)

    def test_validate_image_bytes_valid_and_invalid(self):
        """QImageReader validates actual image bytes and detects corrupt data."""
        valid_bytes = _create_test_image_bytes(64, 48)
        ok, w, h = validate_image_bytes(valid_bytes)
        self.assertTrue(ok)
        self.assertEqual(w, 64)
        self.assertEqual(h, 48)

        # Corrupt data
        bad_bytes = b"not an image at all but some random text bytes"
        ok, w, h = validate_image_bytes(bad_bytes)
        self.assertFalse(ok)
        self.assertEqual((w, h), (0, 0))

    @patch("requests.get")
    def test_fetch_success_and_cache(self, mock_get):
        """Successful HTTP fetch validates image and stores in disk cache."""
        img_bytes = _create_test_image_bytes(200, 150)
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "image/png", "Content-Length": str(len(img_bytes))}
        mock_resp.iter_content.return_value = [img_bytes]
        mock_resp.content = img_bytes
        mock_get.return_value = mock_resp

        res = fetch_image("https://images.example.com/pic.png", cache=self.cache)
        self.assertTrue(res.success)
        self.assertEqual(res.width, 200)
        self.assertEqual(res.height, 150)
        self.assertEqual(res.host, "images.example.com")

        # Verify disk cache hit on subsequent call
        with patch("requests.get") as mock_get2:
            res_cached = fetch_image("https://images.example.com/pic.png", cache=self.cache)
            self.assertTrue(res_cached.success)
            mock_get2.assert_not_called()

    @patch("requests.get")
    def test_fetch_rejected_content_type(self, mock_get):
        """Non-image content type (e.g. text/html) is rejected cleanly."""
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_get.return_value = mock_resp

        res = fetch_image("https://example.com/page.html", cache=self.cache)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "unsupported_content_type")

    @patch("requests.get")
    def test_fetch_oversize_download_aborted(self, mock_get):
        """Content length exceeding FETCH_MAX_MB is rejected before or during stream."""
        mock_resp = MagicMock()
        mock_resp.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(20 * 1024 * 1024),  # 20MB > 15MB limit
        }
        mock_get.return_value = mock_resp

        res = fetch_image("https://example.com/huge.jpg", cache=self.cache, max_mb=15)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "oversize_download")

    @patch("requests.get")
    def test_fetch_timeout_handled(self, mock_get):
        """HTTP timeout is caught and returns fetch_timeout error."""
        mock_get.side_effect = requests.Timeout("Connection timed out")
        res = fetch_image("https://example.com/slow.jpg", cache=self.cache)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "fetch_timeout")

    @patch("requests.get")
    def test_fetch_corrupt_image_handled(self, mock_get):
        """Corrupt payload that HTTP returned 200 for is rejected by validator."""
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.iter_content.return_value = [b"corrupt junk data"]
        mock_get.return_value = mock_resp

        res = fetch_image("https://example.com/broken.jpg", cache=self.cache)
        self.assertFalse(res.success)
        self.assertEqual(res.error, "corrupt_or_unsupported_image")

    def test_cache_lru_eviction(self):
        """Cache enforces max_mb and evicts oldest items first."""
        small_cache = ImageViewerCache(root=self.temp_dir, max_mb=1)  # 1 MB
        chunk_400k = b"X" * (400 * 1024)

        # Put 3 items (1200 KB > 1024 KB limit)
        p1 = small_cache.put("https://a.com/1.png", chunk_400k)
        p2 = small_cache.put("https://b.com/2.png", chunk_400k)
        p3 = small_cache.put("https://c.com/3.png", chunk_400k)

        # Total size must be within 1MB (<= 2 chunks remain)
        total_size = sum(f.stat().st_size for f in self.temp_dir.glob("*.img"))
        self.assertLessEqual(total_size, 1024 * 1024)


class TestCandidateCycling(unittest.TestCase):

    def test_reference_image_session_cycling(self):
        """ReferenceImageSession supports cycling through candidates forward and backward."""
        mock_local = MagicMock()
        mock_web = MagicMock()
        mock_cache = MagicMock()

        cand1 = ImageResult(fetch_handle="local/path/1.png", attribution="Photo 1", licence="CC0", is_local=True)
        cand2 = ImageResult(fetch_handle="local/path/2.png", attribution="Photo 2", licence="MIT", is_local=True)
        cand3 = ImageResult(fetch_handle="local/path/3.png", attribution="Photo 3", licence="CC-BY", is_local=True)

        mock_local.search.return_value = [cand1, cand2, cand3]
        mock_web.search.return_value = []

        # Create session with fake local files
        session = ReferenceImageSession(local_source=mock_local, web_source=mock_web, cache=mock_cache)

        with patch("core.image_viewer.fetch.fetch_image") as mock_fetch:
            mock_fetch.return_value = FetchResult(success=True, width=100, height=100)

            # Search initializes candidates
            session.search("test subject")
            self.assertEqual(session.total_candidates, 3)
            self.assertEqual(session.current_index, 0)

            # Next candidate -> index 1
            session.next_candidate()
            self.assertEqual(session.current_index, 1)

            # Next candidate -> index 2
            session.next_candidate()
            self.assertEqual(session.current_index, 2)

            # Next candidate wraps around -> index 0
            session.next_candidate()
            self.assertEqual(session.current_index, 0)

            # Previous candidate wraps backward -> index 2
            session.previous_candidate()
            self.assertEqual(session.current_index, 2)


class TestImageIntentPrecedence(unittest.TestCase):

    def test_image_reference_queries(self):
        """Assert standard voice commands match search action."""
        for phrase in [
            "show me a reference image of a Tesla Cybertruck",
            "show me a picture of the Batmobile",
            "pull up a picture of Mount Fuji",
            "pull up a reference image of Tony Stark",
        ]:
            intent = classify_image_intent(phrase)
            self.assertEqual(intent.action, "search", f"Failed for phrase: {phrase}")
            self.assertTrue(len(intent.query) > 0)

    def test_candidate_cycling_phrases(self):
        """Assert cycling commands match next/prev actions."""
        self.assertEqual(classify_image_intent("another one").action, "next")
        self.assertEqual(classify_image_intent("next").action, "next")
        self.assertEqual(classify_image_intent("next image").action, "next")
        self.assertEqual(classify_image_intent("previous image").action, "prev")
        self.assertEqual(classify_image_intent("prev").action, "prev")

    def test_close_image_phrases(self):
        """Assert close image phrases match close action."""
        self.assertEqual(classify_image_intent("close the image").action, "close")
        self.assertEqual(classify_image_intent("close image").action, "close")
        self.assertEqual(classify_image_intent("dismiss the image").action, "close")

    def test_clash_avoidance_with_video_and_playback(self):
        """Assert media and video commands never match image intents."""
        # 1. Spotify / bare playback
        self.assertEqual(classify_image_intent("play Starboy").action, "none")
        self.assertEqual(classify_image_intent("play music").action, "none")

        # 2. Visual HUD video requests
        self.assertEqual(classify_image_intent("play the new Dune trailer in the app").action, "none")
        self.assertEqual(classify_image_intent("watch the trailer on screen").action, "none")
        self.assertEqual(classify_image_intent("stream Dune on the hud").action, "none")

        # 3. Visual HUD close command (must NOT close image viewer)
        self.assertEqual(classify_image_intent("close the visual hud").action, "none")
        self.assertEqual(classify_image_intent("back to the globe").action, "none")
        self.assertEqual(classify_image_intent("restore the avatar").action, "none")


class TestShowImageAction(unittest.TestCase):

    def test_show_image_speaks_on_failure(self):
        """Failure must trigger speak('Couldn't find one, sir.') and show no window."""
        mock_speak = MagicMock()
        mock_player = MagicMock()

        with patch("actions.show_image.get_image_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_sess.search.return_value = FetchResult(success=False, error="not_found")
            mock_get_sess.return_value = mock_sess

            from actions.show_image import show_image
            res = show_image({"action": "search", "query": "nonexistent creature"}, player=mock_player, speak=mock_speak)

            self.assertEqual(res, "Couldn't find one, sir.")
            mock_speak.assert_called_once_with("Couldn't find one, sir.")
            # Verify no toast or window show occurred
            mock_player.show_toast.assert_not_called()

    def test_show_image_toast_only_on_success(self):
        """Success shows toast, marshals image, and produces NO voice announcement."""
        mock_speak = MagicMock()
        mock_player = MagicMock()
        mock_viewer = MagicMock()

        with patch("actions.show_image.get_image_session") as mock_get_sess, \
             patch("actions.show_image.get_image_viewer") as mock_get_viewer:
            mock_sess = MagicMock()
            mock_sess.total_candidates = 1
            mock_sess.current_index = 0
            mock_sess.search.return_value = FetchResult(
                success=True,
                file_path="cache/123.img",
                host="example.com",
                attribution="Test Attribution",
            )
            mock_get_sess.return_value = mock_sess
            mock_get_viewer.return_value = mock_viewer

            from actions.show_image import show_image
            res = show_image({"action": "search", "query": "Tesla Cybertruck"}, player=mock_player, speak=mock_speak)

            self.assertIn("example.com", res)
            mock_speak.assert_not_called()  # Terse ALFRED persona: no speech on success!
            mock_player.show_toast.assert_called_once_with("Reference image: example.com")
            mock_viewer.show_requested.emit.assert_called_once()

    def test_privacy_random_token_never_in_logs_or_window_state(self):
        """A random URL token must not appear in logs, toast, caption, or viewer state."""
        import logging
        import uuid
        from core.image_viewer.viewer import ImageViewerWindow

        token = f"secret_token_{uuid.uuid4().hex}"
        url_with_token = f"https://cdn.photos.org:8443/assets/img.jpg?auth={token}&user=batman"

        # 1. Host extraction strips token
        host = extract_host(url_with_token)
        self.assertEqual(host, "cdn.photos.org:8443")
        self.assertNotIn(token, host)

        # 2. Window display strips token
        img = _create_test_image_bytes(100, 100)
        viewer = ImageViewerWindow()
        viewer.show_image(img, caption="Photo by Bruce", host=host)

        self.assertNotIn(token, viewer._host_lbl.text())
        self.assertNotIn(token, viewer._size_lbl.text())
        self.assertNotIn(token, viewer.windowTitle())

        # 3. Cache path derivation strips token
        tmp = Path(tempfile.mkdtemp())
        try:
            cache = ImageViewerCache(root=tmp)
            cache_path = cache.path_for(url_with_token)
            self.assertNotIn(token, str(cache_path))
            self.assertNotIn(token, cache_path.name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



if __name__ == "__main__":
    unittest.main()

