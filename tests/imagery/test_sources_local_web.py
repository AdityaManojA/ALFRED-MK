"""Behavioural tests for core.imagery.sources.local and core.imagery.sources.web."""
from unittest import mock

import pytest

from core.imagery.sources import local as local_mod
from core.imagery.sources import web as web_mod
from core.imagery.sources.base import ImageResult
from core.imagery.sources.local import LocalSource
from core.imagery.sources.web import WEB_IMAGE_TIMEOUT_S, WEB_RESULTS_LIMIT, WebSource


# ── LocalSource ──────────────────────────────────────────────────────────────

@pytest.fixture
def pics(tmp_path):
    root = tmp_path / "Pictures"
    (root / "trips").mkdir(parents=True)
    (root / "trips" / "img_red_car_1.jpg").write_bytes(b"x")
    (root / "trips" / "img_blue_car_2.PNG").write_bytes(b"x")
    (root / "notes.txt").write_text("not an image")
    (root / "cat.webp").write_bytes(b"x")
    return root


def test_local_direct_path_returns_single_local_result(pics):
    target = pics / "cat.webp"
    src = LocalSource(roots=[pics])
    res = src.search(str(target), limit=5)
    assert res == [ImageResult(str(target), "cat.webp", "local", True)]


def test_local_direct_path_with_non_image_extension_falls_through(pics):
    src = LocalSource(roots=[pics])
    # notes.txt is a file but not an image ext; token search on full path yields nothing
    assert src.search(str(pics / "notes.txt"), limit=5) == []


def test_local_index_filters_extensions_case_insensitively(pics):
    src = LocalSource(roots=[pics])
    src._refresh()
    names = sorted(p.name for p in src._index)
    assert names == ["cat.webp", "img_blue_car_2.PNG", "img_red_car_1.jpg"]


def test_local_token_search_requires_all_tokens(pics):
    src = LocalSource(roots=[pics])
    # underscores are treated as spaces, so "car" is its own token
    names = sorted(r.attribution for r in src.search("car", limit=10))
    assert names == ["img_blue_car_2.PNG", "img_red_car_1.jpg"]
    only = src.search("RED car", limit=10)
    assert [r.attribution for r in only] == ["img_red_car_1.jpg"]
    assert all(r.is_local and r.licence == "local" for r in only)
    assert src.search("volcano", limit=10) == []


@pytest.mark.xfail(
    reason="Tokens are split on whitespace only: the last word keeps its extension "
           "('sunset.jpg') and the first is fused with the directory path, so a bare "
           "keyword matching a filename's first/last word never matches.",
    strict=True,
)
def test_local_keyword_matches_last_word_of_filename(tmp_path):
    (tmp_path / "beach_sunset.jpg").write_bytes(b"x")
    src = LocalSource(roots=[tmp_path])
    assert [r.attribution for r in src.search("sunset", limit=10)] == ["beach_sunset.jpg"]


def test_local_search_respects_limit(pics):
    src = LocalSource(roots=[pics])
    assert len(src.search("car", limit=1)) == 1


def test_local_missing_root_is_ignored(tmp_path, pics):
    src = LocalSource(roots=[tmp_path / "does-not-exist", pics])
    assert len(src.search("car", limit=10)) == 2


def test_local_index_cached_within_ttl(pics, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(local_mod.time, "monotonic", lambda: clock[0])
    src = LocalSource(roots=[pics])
    src._refresh()
    assert len(src._index) == 3
    (pics / "img_new_car_3.bmp").write_bytes(b"x")
    clock[0] += local_mod.LOCAL_INDEX_TTL_S - 1
    src._refresh()
    assert len(src._index) == 3  # still cached
    clock[0] += 2
    src._refresh()
    assert len(src._index) == 4  # TTL expired -> rescanned


def test_local_default_roots_point_at_home():
    assert all(p.parent == local_mod.Path.home() for p in local_mod.LOCAL_IMAGE_ROOTS)


# ── WebSource ────────────────────────────────────────────────────────────────

def _resp(payload):
    r = mock.Mock()
    r.json.return_value = payload
    return r


def test_web_parses_results_and_skips_missing_urls():
    payload = {"results": [
        {"url": "https://a/1.jpg", "creator": "Ann", "license": "by"},
        {"url": "", "creator": "Bob"},
        {"creator": "NoUrl"},
        {"url": "https://a/2.jpg"},
    ]}
    with mock.patch.object(web_mod.requests, "get", return_value=_resp(payload)) as get:
        res = WebSource().search("bats", limit=3)
    assert res == [
        ImageResult("https://a/1.jpg", "Ann", "by", False),
        ImageResult("https://a/2.jpg", "Openverse", "", False),
    ]
    _, kwargs = get.call_args
    assert kwargs["params"] == {"q": "bats", "page_size": 3}
    assert kwargs["timeout"] == WEB_IMAGE_TIMEOUT_S


def test_web_page_size_capped():
    with mock.patch.object(web_mod.requests, "get", return_value=_resp({})) as get:
        assert WebSource().search("x", limit=100) == []
    assert get.call_args.kwargs["params"]["page_size"] == WEB_RESULTS_LIMIT


@pytest.mark.parametrize("exc", [web_mod.requests.ConnectionError("down"), ValueError("bad json")])
def test_web_errors_return_empty(exc):
    with mock.patch.object(web_mod.requests, "get", side_effect=exc):
        assert WebSource().search("x") == []
