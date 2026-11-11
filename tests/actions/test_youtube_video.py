"""Behavioural tests for actions.youtube_video.

requests, the transcript API, Gemini and URL opening are mocked; no network
traffic and no browser windows.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.youtube_video as yt
from actions.youtube_video import youtube_video

VID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    monkeypatch.setattr(yt, "_REQUESTS_OK", True)
    opened = []
    monkeypatch.setattr(yt, "_open_url", lambda url: opened.append(url))
    return opened


def _html(text):
    """Patch the module's requests with a fake whose get() returns *text*."""
    fake = SimpleNamespace(get=MagicMock(return_value=SimpleNamespace(text=text)))
    return patch.object(yt, "requests", fake, create=True)


# ── URL helpers ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VID}&t=10",
        f"https://youtu.be/{VID}",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/v/{VID}",
    ],
)
def test_extract_video_id(url):
    assert yt._extract_video_id(url) == VID


def test_extract_video_id_invalid():
    assert yt._extract_video_id("https://www.youtube.com/") is None


def test_is_valid_youtube_url():
    assert yt._is_valid_youtube_url("https://youtu.be/x")
    assert not yt._is_valid_youtube_url("https://vimeo.com/1")
    assert not yt._is_valid_youtube_url(None)


# ── scraping ─────────────────────────────────────────────────────────────────

def test_scrape_first_video_skips_shorts_and_duplicates():
    html = (
        '"videoId":"SHORTSHORT1" /shorts/SHORTSHORT1 '
        '"videoId":"SHORTSHORT1" '
        f'"videoId":"{VID}"'
    )
    with _html(html) as req:
        assert yt._scrape_first_video_url("never gonna") == f"https://www.youtube.com/watch?v={VID}"
    url = req.get.call_args.args[0]
    assert "search_query=never+gonna" in url and f"sp={yt._YT_VIDEO_FILTER}" in url


def test_scrape_first_video_none_found_or_error(monkeypatch):
    with _html("no ids here"):
        assert yt._scrape_first_video_url("q") is None
    failing = SimpleNamespace(get=MagicMock(side_effect=OSError("offline")))
    monkeypatch.setattr(yt, "requests", failing, raising=False)
    assert yt._scrape_first_video_url("q") is None
    monkeypatch.setattr(yt, "_REQUESTS_OK", False)
    assert yt._scrape_first_video_url("q") is None


def test_scrape_video_info_formats_fields():
    html = (
        '"title":{"runs":[{"text":"Great Video"}]} '
        '"ownerChannelName":"Rick" "viewCount":"1234567" '
        '"lengthSeconds":"213" "label":"12,345 likes"'
    )
    with _html(html):
        info = yt._scrape_video_info(VID)
    assert info == {
        "title": "Great Video", "channel": "Rick", "views": "1,234,567",
        "duration": "3:33", "likes": "12,345 likes",
    }


def test_scrape_trending_dedupes_and_limits():
    titles = ["Hit One", "Hit One", "abc", "Hit Two", "Hit Three"]
    html = " ".join(f'"title":{{"runs":[{{"text":"{t}"}}]}}' for t in titles)
    html += ' "ownerText":{"runs":[{"text":"Chan A"' + ' "ownerText":{"runs":[{"text":"Chan B"'
    with _html(html) as req:
        out = yt._scrape_trending("us", max_results=2)
    assert "gl=US" in req.get.call_args.args[0]
    assert out == [
        {"rank": 1, "title": "Hit One", "channel": "Chan A"},
        {"rank": 2, "title": "Hit Two", "channel": "Unknown"},
    ]


# ── transcript ───────────────────────────────────────────────────────────────

def test_get_transcript_prefers_manual(monkeypatch):
    manual = MagicMock()
    manual.fetch.return_value = [{"text": "hello"}, {"text": "world"}]
    tlist = MagicMock()
    tlist.find_manually_created_transcript.return_value = manual
    api = SimpleNamespace(list_transcripts=MagicMock(return_value=tlist))
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", True)
    monkeypatch.setattr(yt, "YouTubeTranscriptApi", api, raising=False)
    assert yt._get_transcript(VID) == "hello world"
    tlist.find_generated_transcript.assert_not_called()


def test_get_transcript_falls_back_to_generated(monkeypatch):
    gen = MagicMock()
    gen.fetch.return_value = [{"text": "auto"}]
    tlist = MagicMock()
    tlist.find_manually_created_transcript.side_effect = Exception("none")
    tlist.find_generated_transcript.return_value = gen
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", True)
    monkeypatch.setattr(yt, "YouTubeTranscriptApi", SimpleNamespace(list_transcripts=lambda vid: tlist), raising=False)
    assert yt._get_transcript(VID) == "auto"


def test_get_transcript_unavailable(monkeypatch):
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", False)
    assert yt._get_transcript(VID) is None


# ── handlers ─────────────────────────────────────────────────────────────────

def test_play_opens_scraped_video(_no_side_effects):
    with patch.object(yt, "_scrape_first_video_url", return_value="https://www.youtube.com/watch?v=x"):
        assert youtube_video({"action": "play", "query": "lofi"}) == "Playing: lofi"
    assert _no_side_effects == ["https://www.youtube.com/watch?v=x"]


def test_play_falls_back_to_search_page(_no_side_effects):
    with patch.object(yt, "_scrape_first_video_url", return_value=None):
        out = youtube_video({"query": "lofi beats"})
    assert out == "Opened YouTube search for: lofi beats (manual selection required)"
    assert "search_query=lofi+beats" in _no_side_effects[0]


def test_play_requires_query():
    assert youtube_video({"action": "play"}) == "Please tell me what you'd like to watch, sir."


def test_summarize_paths(monkeypatch):
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", True)
    assert youtube_video({"action": "summarize"}).startswith("Please provide a YouTube video URL")
    with patch.object(yt, "_scrape_first_video_url", return_value=None):
        assert youtube_video({"action": "summarize", "query": "cats"}) == (
            "That doesn't appear to be a valid YouTube URL, sir."
        )
    with patch.object(yt, "_get_transcript", return_value=None):
        assert youtube_video({"action": "summarize", "url": f"https://youtu.be/{VID}"}) == (
            "I couldn't retrieve a transcript for that video, sir."
        )


def test_summarize_success_and_save(monkeypatch):
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", True)
    speak = MagicMock()
    with patch.object(yt, "_get_transcript", return_value="words") as gt, \
         patch.object(yt, "_summarize_with_gemini", return_value="Summary.") as sumz, \
         patch.object(yt, "_save_summary", return_value="/x/summary.txt") as save:
        out = youtube_video(
            {"action": "summarize", "url": f"https://youtu.be/{VID}", "save": True}, speak=speak
        )
    gt.assert_called_once_with(VID)
    sumz.assert_called_once_with("words", f"https://youtu.be/{VID}")
    save.assert_called_once_with("Summary.", f"https://youtu.be/{VID}")
    assert out == "Summary complete and saved to Desktop: /x/summary.txt"
    assert speak.call_args_list[-1].args[0] == "Summary."


def test_summarize_requires_library(monkeypatch):
    monkeypatch.setattr(yt, "_TRANSCRIPT_OK", False)
    assert youtube_video({"action": "summarize"}).startswith("youtube-transcript-api is not installed")


def test_get_info_formats_lines():
    info = {"title": "T", "views": "1,000", "duration": "1:05"}
    with patch.object(yt, "_scrape_video_info", return_value=info):
        out = youtube_video({"action": "get_info", "url": f"https://youtu.be/{VID}"})
    assert out == "Title: T\nViews: 1,000\nDuration: 1:05"


def test_get_info_failures():
    assert youtube_video({"action": "get_info", "url": "https://youtube.com/"}) == (
        "Could not extract video ID, sir."
    )
    with patch.object(yt, "_scrape_video_info", return_value={}):
        assert youtube_video({"action": "get_info", "url": f"https://youtu.be/{VID}"}) == (
            "Could not retrieve video information, sir."
        )


def test_trending_output_and_speech():
    trending = [{"rank": i, "title": f"V{i}", "channel": f"C{i}"} for i in range(1, 5)]
    speak = MagicMock()
    with patch.object(yt, "_scrape_trending", return_value=trending) as st:
        out = youtube_video({"action": "trending", "region": "in"}, speak=speak)
    st.assert_called_once_with(region="IN", max_results=8)
    assert out.splitlines()[0] == "Top trending videos in IN:"
    assert out.splitlines()[1] == "1. V1 — C1"
    spoken = speak.call_args.args[0]
    assert "Number 3: V3 by C3" in spoken and "V4" not in spoken


def test_trending_empty():
    with patch.object(yt, "_scrape_trending", return_value=[]):
        assert youtube_video({"action": "trending"}) == "Could not fetch trending videos for region TR, sir."


def test_unknown_action_and_handler_exception():
    assert youtube_video({"action": "rewind"}).startswith("Unknown YouTube action: 'rewind'")
    with patch.dict(yt._ACTION_MAP, {"trending": MagicMock(side_effect=RuntimeError("boom"))}):
        assert youtube_video({"action": "trending"}) == "YouTube trending failed, sir: boom"


def test_save_summary_writes_header(tmp_path, monkeypatch):
    monkeypatch.setattr(yt.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(yt, "is_windows", lambda: False)
    monkeypatch.setattr(yt, "is_mac", lambda: False)
    with patch.object(yt.subprocess, "Popen") as popen:
        path = yt._save_summary("Body text", "https://youtu.be/x")
    files = list((tmp_path / "Desktop").iterdir())
    assert len(files) == 1 and str(files[0]) == path
    content = files[0].read_text(encoding="utf-8")
    assert content.startswith("ALFRED — YouTube Summary")
    assert "URL    : https://youtu.be/x" in content
    assert content.endswith("Body text")
    assert popen.call_args.args[0][0] == "xdg-open"
