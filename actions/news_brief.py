# news_brief.py
"""
On-demand news headlines fetched via the existing web_search infrastructure
and formatted in Alfred's voice.

Unlike daily_brief (which is a scheduled morning read), news_brief answers:
  "What's happening in tech today?"
  "Give me the latest news on India"
  "Any headlines about AI?"
"""
from __future__ import annotations

import time
from typing import Optional

_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 900  # 15 minutes


def _cache_get(key: str) -> Optional[str]:
    if key in _CACHE:
        result, ts = _CACHE[key]  # type: ignore[misc]
        if time.monotonic() - ts < _CACHE_TTL:
            return result
        del _CACHE[key]
    return None


def _cache_put(key: str, value: str) -> None:
    _CACHE[key] = (value, time.monotonic())  # type: ignore[assignment]


def _fetch_headlines(topic: str, count: int) -> Optional[str]:
    """Use the existing web_search action to pull headlines."""
    try:
        from actions.web_search import web_search  # type: ignore[import]
        query = f"latest news headlines {topic} today" if topic else "top news headlines today"
        result = web_search({"query": query, "num_results": count})
        return result if isinstance(result, str) else None
    except Exception:
        pass

    # Minimal fallback via RSS if web_search is unavailable
    try:
        import urllib.request
        import xml.etree.ElementTree as ET
        feed_url = "https://feeds.bbci.co.uk/news/world/rss.xml"
        with urllib.request.urlopen(feed_url, timeout=8) as r:
            tree = ET.parse(r)
        items = tree.findall(".//item")[:count]
        lines = []
        for item in items:
            title = item.findtext("title", "").strip()
            if title:
                lines.append(f"• {title}")
        return "\n".join(lines) if lines else None
    except Exception:
        return None


def news_brief_action(parameters: dict, **kwargs) -> str:
    topic  = str(parameters.get("topic", "")).strip()
    count  = int(parameters.get("count", 5))
    count  = max(1, min(count, 10))

    cache_key = f"{topic.lower()}:{count}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    raw = _fetch_headlines(topic, count)
    if not raw:
        return (
            "Unable to fetch headlines at the moment — "
            "check your connection or try again shortly."
        )

    topic_label = f" on {topic}" if topic else ""
    result = f"Current headlines{topic_label}:\n{raw}"
    _cache_put(cache_key, result)
    return result


# ── Tool declaration ──────────────────────────────────────────────────────────
TOOL = {
    "name": "news_brief",
    "description": (
        "Fetch on-demand news headlines, optionally filtered by topic. "
        "Results are cached for 15 minutes. "
        "Use for: 'what's in the news', 'latest headlines on AI', "
        "'give me tech news', 'any news about India'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "description": (
                    "Optional topic filter — 'technology', 'India', 'AI', 'sports', etc. "
                    "Omit for general world headlines."
                ),
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of headlines to return (1–10, default: 5).",
            },
        },
        "required": [],
    },
    "handler": news_brief_action,
}
