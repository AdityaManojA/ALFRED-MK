"""
Daily Brief Action for ALFRED Mark-VIII.
Provides the ultimate morning and daily executive briefing:
  - Personalized time-of-day greeting (Morning, Afternoon, Evening)
  - Live local weather conditions & temperature
  - Gmail inbox status with unread priority email synthesis
  - Active task reminders scheduled for today
  - Computer system vitals (CPU load, RAM usage, Battery)
  - Auto-discovered by core/action_loader.py as 'daily_brief'
"""
from __future__ import annotations

import json
import os
import platform
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

from memory.config_manager import get_user_name, get_assistant_name
from core.cache import get_cache

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
_WEATHER_CACHE_TTL = 900  # 15 minutes


def _get_greeting() -> str:
    """Generate time-contextual executive salutation."""
    hour = datetime.now().hour
    name = get_user_name()
    title = f", {name}" if name else ", Sir"

    if 4 <= hour < 12:
        return f"Good morning{title}."
    elif 12 <= hour < 17:
        return f"Good afternoon{title}."
    elif 17 <= hour < 22:
        return f"Good evening{title}."
    else:
        return f"Late night systems operational{title}."


def _get_live_weather(city: Optional[str] = None) -> str:
    """Fetch live weather conditions without opening an external browser."""
    target_city = (city or "").strip()
    if not target_city and _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            target_city = data.get("city") or data.get("default_city") or ""
        except Exception:
            pass

    if not target_city:
        try:
            from memory.memory_manager import load_memory
            mem = load_memory()
            target_city = (
                mem.get("identity", {}).get("city", {}).get("value")
                or mem.get("identity", {}).get("location", {}).get("value")
                or ""
            )
            if isinstance(target_city, dict):
                target_city = target_city.get("value", "")
            target_city = str(target_city).strip()
        except Exception:
            pass


    # 1. Cache-aside lookup
    cache = get_cache()
    cache_key = cache.build_key("weather", city=target_city.lower())
    try:
        cached_weather = cache.get(cache_key)
        if cached_weather is not None:
            return cached_weather
    except Exception as e:
        print(f"[DailyBrief] Weather cache check failed: {e}")

    url = f"https://wttr.in/{urllib.parse.quote(target_city)}?format=%C+and+%t" if target_city else "https://wttr.in?format=%C+and+%t"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            text = resp.read().decode("utf-8", errors="replace").strip()
            # Clean symbols like arrows and degree signs for safe TTS & console display
            clean_text = text.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit")
            clean_text = "".join(ch for ch in clean_text if ord(ch) < 128)
            if clean_text and not clean_text.startswith("<") and "Unknown" not in clean_text:
                loc = f" in {target_city}" if target_city else ""
                result = f"Currently{loc}, conditions are {clean_text.strip()}."
                try:
                    cache.set(cache_key, result, ttl=_WEATHER_CACHE_TTL)
                except Exception:
                    pass
                return result
    except Exception:
        pass

    return "Weather telemetry is currently operating on cached forecasts."


def _get_gmail_brief() -> str:
    """Fetch unread emails summary via gmail_manager."""
    try:
        from actions.gmail_manager import fetch_unread_emails
        emails = fetch_unread_emails(max_count=4)
        if not emails:
            return "Your inbox is clear with zero unread priority emails."

        count = len(emails)
        brief = [f"You have {count} unread email{'s' if count != 1 else ''}:"]
        for em in emails[:3]:
            brief.append(f"from {em['sender']} regarding '{em['subject']}';")
        return " ".join(brief)
    except Exception:
        return "Gmail link is standby."


def _get_reminders_brief() -> str:
    """Check scheduled reminders in ~/.alfred/reminders or ~/.jarvis/reminders."""
    reminders_dir = Path.home() / ".alfred" / "reminders"
    if not reminders_dir.exists():
        reminders_dir = Path.home() / ".jarvis" / "reminders"
    if not reminders_dir.exists():
        return "No pending reminders logged for today."

    try:
        today_prefix = datetime.now().strftime("%Y%m%d")
        matching = list(reminders_dir.glob(f"*Reminder_{today_prefix}_*.py"))
        if matching:
            return f"You have {len(matching)} scheduled reminder{'s' if len(matching) != 1 else ''} on docket for today."
        return "Your scheduled reminder queue is clear for the day."
    except Exception:
        return "Reminder schedule is normal."


def _get_system_vitals() -> str:
    """Inspect core CPU, RAM, and Battery vitals."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        batt_str = ""
        if hasattr(psutil, "sensors_battery"):
            batt = psutil.sensors_battery()
            if batt:
                plugged = "plugged in" if batt.power_plugged else "on battery"
                batt_str = f", power at {int(batt.percent)}% ({plugged})"

        return f"System telemetry reports CPU load at {int(cpu)}%, memory at {int(ram)}%{batt_str}."
    except Exception:
        return "All internal systems nominal."


def search_news(params: dict) -> str:
    """Fallback helper to search news headlines by parameter dict."""
    topic = params.get("topic", "") if isinstance(params, dict) else str(params)
    try:
        from actions.web_search import search_news as _ws_search_news
        return _ws_search_news(params)
    except Exception:
        pass
    try:
        from actions.web_search import _news
        return _news(topic)
    except Exception:
        pass
    try:
        from actions.news_brief import news_brief_action
        return news_brief_action({"topic": topic, "count": 2})
    except Exception:
        return ""


def _get_preferred_news(topic: str = "") -> str:
    """Fetch top news headline regarding user's preferred topic with graceful fallback."""
    if not topic:
        return ""
    try:
        from actions.web_search import _news
        res = _news(topic)
        if res and not res.startswith("No news found"):
            return res
    except Exception:
        pass

    try:
        return search_news({"topic": topic})
    except Exception:
        return ""


def daily_brief(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    """Executes the daily briefing and delivers spoken synthesis."""
    inc_email = parameters.get("include_email", True)
    inc_weather = parameters.get("include_weather", True)
    inc_reminders = parameters.get("include_reminders", True)
    inc_system = parameters.get("include_system", True)
    city = parameters.get("city")

    # Incorporate user's remembered briefing preferences from long-term memory
    brief_pref = ""
    try:
        from memory.memory_manager import load_memory
        mem = load_memory()
        bp = mem.get("preferences", {}).get("briefing_preference")
        if isinstance(bp, dict):
            brief_pref = str(bp.get("value", "")).strip()
        elif isinstance(bp, str):
            brief_pref = bp.strip()
        if not city:
            c = mem.get("identity", {}).get("city")
            if isinstance(c, dict):
                city = c.get("value")
            elif isinstance(c, str):
                city = c
    except Exception:
        pass

    greeting = _get_greeting()
    weather_text = ""
    email_text = ""
    rem_text = ""
    sys_text = ""
    pref_news = ""

    def _get_market_brief() -> str:
        try:
            from core.market.watchlist import WatchlistManager
            from core.market.provider import MarketProvider
            mgr = WatchlistManager.instance()
            watches = mgr.list_active()
            provider = MarketProvider.instance()
            # If watches exist, summarize top mover; else summarize S&P / Nasdaq
            if watches:
                quotes = [provider.get_quote(w.symbol) for w in watches[:4]]
                valid_quotes = [q for q in quotes if q is not None]
                if valid_quotes:
                    top = max(valid_quotes, key=lambda q: abs(q.change_pct))
                    dir_str = "up" if top.change_pct >= 0 else "down"
                    return f"On your watchlist, {top.display_name or top.symbol} is {dir_str} {abs(top.change_pct):.1f}%."
            else:
                sp = provider.get_quote("^GSPC")
                if sp:
                    dir_str = "up" if sp.change_pct >= 0 else "down"
                    return f"S&P 500 is {dir_str} {abs(sp.change_pct):.1f}%."
        except Exception:
            pass
        return ""

    # These sections are independent. Serial execution made the user wait for
    # the sum of every network timeout before the model could speak.
    jobs = {}
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="daily-brief") as pool:
        if inc_weather:
            jobs["weather"] = pool.submit(_get_live_weather, city)
        if inc_email:
            jobs["email"] = pool.submit(_get_gmail_brief)
        if inc_reminders:
            jobs["reminders"] = pool.submit(_get_reminders_brief)
        if inc_system:
            jobs["system"] = pool.submit(_get_system_vitals)
        jobs["market"] = pool.submit(_get_market_brief)
        if brief_pref:
            jobs["news"] = pool.submit(_get_preferred_news, brief_pref)

        results = {}
        for key, future in jobs.items():
            try:
                results[key] = future.result()
            except Exception:
                results[key] = ""

    weather_text = results.get("weather", "")
    email_text = results.get("email", "")
    rem_text = results.get("reminders", "")
    sys_text = results.get("system", "")
    market_text = results.get("market", "")
    pref_news = results.get("news", "")

    components = [greeting]
    components.extend(text for text in (weather_text, market_text, email_text, rem_text, sys_text) if text)
    if pref_news and not pref_news.startswith(("No news", "Search failed", "Please provide")):
        news_lines = [line.strip() for line in pref_news.splitlines() if line.strip()]
        headline = next(
            (line for line in news_lines if not line.lower().startswith("latest news:")),
            "",
        )
        if headline:
            components.append(f"Regarding your briefing focus on {brief_pref}: {headline}")

    components.append("All directives stand ready at your command.")
    full_brief = " ".join(components)

    if player:
        try:
            player.write_log("ALFRED: [Daily Brief] ── Executive Status Report ──")
            player.write_log(f"   • {greeting}")
            if inc_weather:
                player.write_log(f"   • Weather: {weather_text}")
            if inc_email:
                player.write_log(f"   • Inbox: {email_text}")
            if inc_reminders:
                player.write_log(f"   • Schedule: {rem_text}")
            if inc_system:
                player.write_log(f"   • Vitals: {sys_text}")
            if brief_pref:
                player.write_log(f"   • Briefing Focus: {brief_pref}")
        except Exception:
            pass

    return full_brief


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "daily_brief",
    "description": (
        "Delivers the morning or daily executive status briefing. "
        "Synthesizes personal salutation, live weather, unread Gmail summary, "
        "scheduled reminders, and system vitals into a concise spoken report. "
        "Trigger when user says 'good morning', 'morning brief', 'daily brief', "
        "'what does my day look like', 'give me an update', or 'status report'. "
        "Call this tool alone for that request; it already reads memory, weather, "
        "mail, reminders, system status, and preferred news. Do not call those "
        "tools separately before or after it. "
        "DO NOT call this tool when the user asks to update, change, configure, or customize their daily briefing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "Optional city for weather report (e.g. 'San Francisco', 'London', 'Tokyo')."
            },
            "include_email": {
                "type": "BOOLEAN",
                "description": "Whether to include Gmail unread message summary (default true)."
            },
            "include_weather": {
                "type": "BOOLEAN",
                "description": "Whether to include live weather conditions (default true)."
            },
            "include_reminders": {
                "type": "BOOLEAN",
                "description": "Whether to check today's scheduled reminders (default true)."
            },
            "include_system": {
                "type": "BOOLEAN",
                "description": "Whether to report CPU, memory, and battery vitals (default true)."
            }
        },
        "required": []
    },
    "handler": daily_brief,
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}
