"""Answer Parser: Converts natural language monitoring requests into MonitorTargets."""
from __future__ import annotations

import re
import uuid
from typing import List

from core.sentry.monitor.targets.base import MonitorTarget
from core.sentry.monitor.targets.terminal import TerminalTarget
from core.sentry.monitor.targets.window_title import WindowTitleTarget
from core.sentry.monitor.targets.file_log import FileLogTarget
from core.sentry.monitor.targets.process import ProcessTarget
from core.sentry.monitor.targets.command import CommandTarget
from core.sentry.monitor.targets.clipboard import ClipboardTarget
from core.sentry.monitor.targets.screen_region import ScreenRegionTarget
from core.sentry.monitor.targets.market import MarketTarget
from core.market.rules import AlertRule, RuleType


def parse_monitoring_request(request: str) -> list[MonitorTarget]:
    """Parse a user prompt into one or more MonitorTarget instances."""
    cleaned = (request or "").strip()
    if not cleaned:
        return [TerminalTarget(target_id=str(uuid.uuid4())[:8], name="Terminal task")]

    # Split compound requests on coordinating conjunctions
    clauses = [c.strip() for c in re.split(r"\b(?:and then|and also|and|plus)\b", cleaned, flags=re.I) if c.strip()]
    if not clauses:
        clauses = [cleaned]

    targets: list[MonitorTarget] = []
    for idx, clause in enumerate(clauses, 1):
        target = _parse_clause(clause, index=idx)
        if target:
            targets.append(target)

    return targets if targets else [TerminalTarget(target_id=str(uuid.uuid4())[:8], name=cleaned[:40])]


def _parse_clause(clause: str, index: int = 1) -> MonitorTarget:
    uid = str(uuid.uuid4())[:8]

    # Pattern: Market monitoring — "watch NVDA above 140" / "alert me if TSLA drops 5 percent"
    mkt_thresh = re.search(
        r"(?:watch|track|monitor|alert me if)?\s*([a-zA-Z0-9\^=\-]+)\s*(?:above|over|exceeds|crosses above|>=|>)\s*\$?([0-9]+(?:\.[0-9]+)?)",
        clause,
        re.I,
    )
    if mkt_thresh and mkt_thresh.group(1).lower() not in ("process", "window", "file", "tab", "app", "log", "clipboard", "screen"):
        sym = mkt_thresh.group(1).strip()
        val = float(mkt_thresh.group(2))
        return MarketTarget(
            target_id=f"mkt_{uid}",
            symbol=sym,
            rule=AlertRule(rule_type=RuleType.THRESHOLD_ABOVE, threshold_value=val),
        )

    mkt_thresh_below = re.search(
        r"(?:watch|track|monitor|alert me if)?\s*([a-zA-Z0-9\^=\-]+)\s*(?:below|under|drops below|crosses below|<=|<)\s*\$?([0-9]+(?:\.[0-9]+)?)",
        clause,
        re.I,
    )
    if mkt_thresh_below and mkt_thresh_below.group(1).lower() not in ("process", "window", "file", "tab", "app", "log", "clipboard", "screen"):
        sym = mkt_thresh_below.group(1).strip()
        val = float(mkt_thresh_below.group(2))
        return MarketTarget(
            target_id=f"mkt_{uid}",
            symbol=sym,
            rule=AlertRule(rule_type=RuleType.THRESHOLD_BELOW, threshold_value=val),
        )

    mkt_pct = re.search(
        r"(?:watch|alert me if)?\s*([a-zA-Z0-9\^=\-]+)\s*(?:drops|grows|moves|changes|falls|rises)?\s*(?:by)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:percent|%|pct)",
        clause,
        re.I,
    )
    if mkt_pct and mkt_pct.group(1).lower() not in ("process", "window", "file", "tab", "app", "log", "clipboard", "screen"):
        sym = mkt_pct.group(1).strip()
        val = float(mkt_pct.group(2))
        return MarketTarget(
            target_id=f"mkt_{uid}",
            symbol=sym,
            rule=AlertRule(rule_type=RuleType.PCT_DELTA, threshold_value=val),
        )

    # Pattern: "tell me when Chrome's title says Deployed" / "Chrome title is X"
    win_match = re.search(
        r"(?:tell me when|when|if)?\s*([a-zA-Z0-9_\-\.]+)(?:'s)?\s*(?:window|tab|title)?\s*(?:says|is|has|matches|shows)\s*['\"]?([^'\"]+)['\"]?",
        clause,
        re.I,
    )
    if win_match:
        app_raw = win_match.group(1).replace("'s", "").strip()
        pattern = win_match.group(2).strip()
        return WindowTitleTarget(
            target_id=f"win_{uid}",
            name=f"{app_raw} title",
            app_name=app_raw,
            title_pattern=pattern,
        )

    # Pattern: "tail log file /path/to/file for ERROR" / "watch file.log"
    log_match = re.search(
        r"(?:tail|watch|monitor)?\s*(?:log|file)\s+['\"]?([^'\"\s]+\.[a-zA-Z0-9]+)['\"]?(?:\s+(?:for|matching)\s+['\"]?([^'\"]+)['\"]?)?",
        clause,
        re.I,
    )
    if log_match:
        fpath = log_match.group(1).strip()
        pattern = log_match.group(2).strip() if log_match.group(2) else ""
        return FileLogTarget(
            target_id=f"log_{uid}",
            name=f"Log {fpath}",
            file_path=fpath,
            pattern=pattern,
        )

    # Pattern: "watch process python.exe" / "pid 1234"
    proc_match = re.search(r"(?:watch|monitor)?\s*process\s+['\"]?([^'\"\s]+)['\"]?", clause, re.I)
    if proc_match:
        pname = proc_match.group(1).strip()
        pid = int(pname) if pname.isdigit() else None
        return ProcessTarget(
            target_id=f"proc_{uid}",
            name=pname,
            pid=pid,
        )

    # Pattern: "run command 'pytest' every 5s"
    cmd_match = re.search(r"(?:run|command)\s+['\"]([^'\"]+)['\"]", clause, re.I)
    if cmd_match:
        cmd = cmd_match.group(1).strip()
        return CommandTarget(
            target_id=f"cmd_{uid}",
            name=cmd[:30],
            command=cmd,
        )

    # Pattern: "watch clipboard for pattern"
    if "clipboard" in clause.lower():
        pat_match = re.search(r"clipboard\s*(?:for|matching)?\s*['\"]?([^'\"]*)['\"]?", clause, re.I)
        pat = pat_match.group(1).strip() if pat_match else ""
        return ClipboardTarget(
            target_id=f"clip_{uid}",
            name="Clipboard Monitor",
            pattern=pat,
        )

    # Pattern: "watch screen region" / "screen for X"
    if "screen" in clause.lower() and "terminal" not in clause.lower():
        return ScreenRegionTarget(
            target_id=f"screen_{uid}",
            name=clause[:35],
            goal=clause,
        )

    # Default to TerminalTarget
    return TerminalTarget(
        target_id=f"term_{uid}",
        name=clause[:40],
    )
