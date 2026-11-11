"""Behavioural tests for actions.news_brief (web_search and RSS are mocked)."""
import io
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import actions.news_brief as nb
from actions.news_brief import news_brief_action

RSS = b"""<?xml version="1.0"?>
<rss><channel>
<item><title> First headline </title></item>
<item><title></title></item>
<item><title>Second headline</title></item>
<item><title>Third headline</title></item>
</channel></rss>"""


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def _clear_cache():
    nb._CACHE.clear()
    yield
    nb._CACHE.clear()


def _fake_web_search(fn):
    mod = types.ModuleType("actions.web_search")
    mod.web_search = fn
    return patch.dict(sys.modules, {"actions.web_search": mod})


def test_fetch_uses_web_search_with_topic_query():
    search = MagicMock(return_value="• AI story")
    with _fake_web_search(search):
        assert nb._fetch_headlines("AI", 3) == "• AI story"
    search.assert_called_once_with({"query": "latest news headlines AI today", "num_results": 3})


def test_fetch_general_query_without_topic():
    search = MagicMock(return_value="x")
    with _fake_web_search(search):
        nb._fetch_headlines("", 5)
    assert search.call_args.args[0]["query"] == "top news headlines today"


def test_fetch_falls_back_to_rss_and_skips_blank_titles():
    with _fake_web_search(MagicMock(side_effect=RuntimeError("no search"))), \
         patch("urllib.request.urlopen", return_value=_Resp(RSS)):
        out = nb._fetch_headlines("", 3)
    # count limits the <item> elements read (3), one of which has an empty title
    assert out == "• First headline\n• Second headline"


def test_fetch_returns_none_when_everything_fails():
    with _fake_web_search(MagicMock(return_value={"not": "a string"})):
        assert nb._fetch_headlines("x", 1) is None
    with _fake_web_search(MagicMock(side_effect=RuntimeError)), \
         patch("urllib.request.urlopen", side_effect=OSError("offline")):
        assert nb._fetch_headlines("x", 1) is None


def test_action_formats_and_caches():
    with patch.object(nb, "_fetch_headlines", return_value="• one") as fetch:
        first = news_brief_action({"topic": "Tech", "count": 2})
        second = news_brief_action({"topic": "tech", "count": 2})
    assert first == "Current headlines on Tech:\n• one"
    assert second == first  # served from cache (key is lower-cased topic)
    fetch.assert_called_once_with("Tech", 2)


@pytest.mark.parametrize("raw, clamped", [(0, 1), (-3, 1), (50, 10), ("4", 4)])
def test_action_clamps_count(raw, clamped):
    with patch.object(nb, "_fetch_headlines", return_value="h") as fetch:
        news_brief_action({"count": raw})
    fetch.assert_called_once_with("", clamped)


def test_action_failure_message_is_not_cached():
    with patch.object(nb, "_fetch_headlines", return_value=None):
        out = news_brief_action({})
    assert out.startswith("Unable to fetch headlines")
    assert nb._CACHE == {}


def test_cache_expires_after_ttl():
    with patch.object(nb.time, "monotonic", return_value=1000.0):
        nb._cache_put("k", "v")
    with patch.object(nb.time, "monotonic", return_value=1000.0 + nb._CACHE_TTL - 1):
        assert nb._cache_get("k") == "v"
    with patch.object(nb.time, "monotonic", return_value=1000.0 + nb._CACHE_TTL + 1):
        assert nb._cache_get("k") is None
    assert "k" not in nb._CACHE
