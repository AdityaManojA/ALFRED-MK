#!/usr/bin/env python3
"""
tools/bump_version.py — Automated Version Bumper for ALFRED.

Reads the current version from ui.py (APP_VERSION) and updates all registered
locations across the codebase to the target version (e.g. Mark-IX).

Usage:
    python tools/bump_version.py Mark-IX
    python tools/bump_version.py Mark-IX --dry-run
    python tools/bump_version.py Mark-IX --run-tests
    python tools/bump_version.py Mark-IX --update-graph
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Roman numeral helper tables
ROMAN_VALS = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
]


def int_to_roman(n: int) -> str:
    result = []
    for val, roman in ROMAN_VALS:
        while n >= val:
            result.append(roman)
            n -= val
    return "".join(result)


def roman_to_int(s: str) -> int:
    roman_map = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for char in reversed(s.upper()):
        val = roman_map.get(char, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


class VersionInfo(NamedTuple):
    num: int
    roman: str
    full_hyphen: str          # e.g. "Mark-VIII"
    full_hyphen_upper: str    # e.g. "MARK-VIII"
    short_hyphen: str         # e.g. "MK-VIII"
    space_case: str           # e.g. "Mark VIII"
    space_case_upper: str     # e.g. "MARK VIII"
    numeric_id: str           # e.g. "mk8"
    title_case: str           # e.g. "Alfred-Mark-VIII"
    title_case_upper: str     # e.g. "ALFRED-Mark-VIII"
    title_case_short: str     # e.g. "ALFRED-MK-VIII"


def parse_version_string(val: str) -> VersionInfo:
    """Normalize inputs like 'Mark-IX', 'mark-9', 'IX', '9', 'MK-IX'."""
    raw = val.strip()
    match = re.search(r"(\d+)", raw)
    if match:
        num = int(match.group(1))
        roman = int_to_roman(num)
    else:
        clean = re.sub(r"(?i)^(alfred-)?(mark|mk)[- ]?", "", raw).strip().upper()
        if not clean or not all(c in "IVXLCDM" for c in clean):
            raise ValueError(f"Could not parse valid version or Roman numeral from '{val}'")
        roman = clean
        num = roman_to_int(roman)

    return VersionInfo(
        num=num,
        roman=roman,
        full_hyphen=f"Mark-{roman}",
        full_hyphen_upper=f"MARK-{roman}",
        short_hyphen=f"MK-{roman}",
        space_case=f"Mark {roman}",
        space_case_upper=f"MARK {roman}",
        numeric_id=f"mk{num}",
        title_case=f"Alfred-Mark-{roman}",
        title_case_upper=f"ALFRED-Mark-{roman}",
        title_case_short=f"ALFRED-MK-{roman}",
    )


def detect_current_version(root: Path) -> VersionInfo:
    """Read current version from ui.py APP_VERSION."""
    ui_path = root / "ui.py"
    if not ui_path.exists():
        raise FileNotFoundError(f"Cannot find ui.py at {ui_path}")
    content = ui_path.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not m:
        raise ValueError("Could not find APP_VERSION definition in ui.py")
    return parse_version_string(m.group(1))


# Registered files relative to root
REGISTERED_FILES = [
    "readme.md",
    "ui.py",
    "main.py",
    "setup.py",
    "requirements.txt",
    "VERSION_LOCATIONS.md",
    "ui/overlays/setup_overlay.py",
    "dashboard/static/app.html",
    "dashboard/static/login.html",
    "core/llm_client.py",
    "core/image_viewer/fetch.py",
    "core/cache.py",
    "core/apis/oauth.py",
    "core/hud/visuals/slots/batcave.py",
    "core/batman_cowl.obj",
    "core/secrets/store.py",
    "core/ui/themes/apply.py",
    "core/ui/themes/registry.py",
    "core/ui/themes/__init__.py",
    "core/ui/themes/schema.py",
    "core/ui/themes/catalog.py",
    "actions/daily_brief.py",
    "actions/gmail_manager.py",
    "actions/update_app_icon.py",
    "actions/update_daily_briefing.py",
    "plugins/focus_protocol.py",
    "plugins/calendar_sync.py",
    "tools/benchmark_latency_pipeline.py",
    "tests/test_platform_stability.py",
    "tests/test_thematic_hud.py",
    "tests/test_screen_processor.py",
    "tests/test_clipboard_manager.py",
]


def build_replacement_pairs(src: VersionInfo, dst: VersionInfo) -> List[Tuple[str, str]]:
    """Build exact text replacement pairs ordered by longest-first to prevent partial collisions."""
    pairs = [
        # Full forms with Assistant name
        (f"ALFRED-{src.full_hyphen}", f"ALFRED-{dst.full_hyphen}"),
        (f"ALFRED-{src.full_hyphen_upper}", f"ALFRED-{dst.full_hyphen_upper}"),
        (f"ALFRED-{src.short_hyphen}", f"ALFRED-{dst.short_hyphen}"),
        (f"Alfred-{src.full_hyphen}", f"Alfred-{dst.full_hyphen}"),
        (f"ALFRED {src.full_hyphen_upper}", f"ALFRED {dst.full_hyphen_upper}"),
        (f"ALFRED {src.full_hyphen}", f"ALFRED {dst.full_hyphen}"),
        (f"ALFRED {src.short_hyphen}", f"ALFRED {dst.short_hyphen}"),
        (f"ALFRED.{src.short_hyphen}", f"ALFRED.{dst.short_hyphen}"),
        (f"ALFRED.{src.full_hyphen_upper}", f"ALFRED.{dst.full_hyphen_upper}"),
        # Window & path references
        (f"Wayne {src.full_hyphen}", f"Wayne {dst.full_hyphen}"),
        (f"WAYNE {src.full_hyphen_upper}", f"WAYNE {dst.full_hyphen_upper}"),
        (f"WAYNE {src.short_hyphen}", f"WAYNE {dst.short_hyphen}"),
        (f"BATWING {src.short_hyphen}", f"BATWING {dst.short_hyphen}"),
        # Section titles
        (f"What's New in {src.space_case}", f"What's New in {dst.space_case}"),
        (f"{src.space_case} New Actions", f"{dst.space_case} New Actions"),
        (f"{src.space_case}", f"{dst.space_case}"),
        (f"{src.space_case_upper}", f"{dst.space_case_upper}"),
        # Standard constants
        (src.full_hyphen_upper, dst.full_hyphen_upper),
        (src.full_hyphen, dst.full_hyphen),
        (src.short_hyphen, dst.short_hyphen),
        (f"[{src.short_hyphen}]", f"[{dst.short_hyphen}]"),
        # AppUserModelID numeric token
        (f"batcomputer.{src.numeric_id}", f"batcomputer.{dst.numeric_id}"),
    ]
    # Remove duplicates while preserving order
    seen = set()
    unique_pairs = []
    for k, v in pairs:
        if k not in seen and k != v:
            seen.add(k)
            unique_pairs.append((k, v))
    # Sort descending by length of target string to match longest first
    unique_pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return unique_pairs


def apply_version_bump(
    root: Path,
    target: VersionInfo,
    dry_run: bool = False
) -> Dict[str, int]:
    curr = detect_current_version(root)
    print(f"\n==================================================")
    print(f"  [ALFRED] VERSION BUMP CONTROLLER")
    print(f"==================================================")
    print(f"  Current Version Detected: {curr.full_hyphen_upper} (Roman: {curr.roman}, #{curr.num})")
    print(f"  Target Version:           {target.full_hyphen_upper} (Roman: {target.roman}, #{target.num})")
    print(f"  Mode:                     {'[DRY RUN - PREVIEW ONLY]' if dry_run else '[LIVE UPDATE]'}")
    print(f"==================================================\n")

    if curr.num == target.num and curr.roman == target.roman:
        print("ℹ Target version is identical to current version. No changes needed.")
        return {}

    replacements = build_replacement_pairs(curr, target)
    stats: Dict[str, int] = {}
    total_modifications = 0

    for rel_path in REGISTERED_FILES:
        file_path = root / rel_path
        if not file_path.exists():
            print(f"  ⚠️  Skipping missing file: {rel_path}")
            continue

        try:
            original = file_path.read_text(encoding="utf-8")
        except Exception:
            try:
                original = file_path.read_text(encoding="utf-8-sig")
            except Exception as e:
                print(f"  ❌ Error reading {rel_path}: {e}")
                continue

        modified = original
        changes_in_file = 0
        for pattern, repl in replacements:
            count = modified.count(pattern)
            if count > 0:
                modified = modified.replace(pattern, repl)
                changes_in_file += count

        if changes_in_file > 0:
            stats[rel_path] = changes_in_file
            total_modifications += changes_in_file
            action = "[WOULD UPDATE]" if dry_run else "[UPDATED]"
            print(f"  + {action:<14} {rel_path:<45} ({changes_in_file} replacement{'s' if changes_in_file > 1 else ''})")
            if not dry_run:
                file_path.write_text(modified, encoding="utf-8")
        else:
            print(f"  . [NO MATCH]     {rel_path}")

    print(f"\n--------------------------------------------------")
    print(f"  Total Files Affected:  {len(stats)}")
    print(f"  Total Replacements:    {total_modifications}")
    print(f"--------------------------------------------------\n")
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Automated version bumper for ALFRED Mark-VIII+ codebase."
    )
    parser.add_argument(
        "target",
        help="Target version title (e.g. Mark-IX, IX, 9, MK-IX)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview replacements without altering files.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Execute unit test suite after updating files.",
    )
    parser.add_argument(
        "--update-graph",
        action="store_true",
        help="Trigger 'graphify update .' after applying changes.",
    )

    args = parser.parse_args()

    try:
        target_info = parse_version_string(args.target)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    stats = apply_version_bump(PROJECT_ROOT, target_info, dry_run=args.dry_run)

    if not args.dry_run and stats:
        if args.run_tests:
            print("\n▶ Running unit tests...")
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=PROJECT_ROOT)

        if args.update_graph:
            print("\n▶ Updating Graphify knowledge graph...")
            subprocess.run([sys.executable, "-m", "graphify", "update", "."], cwd=PROJECT_ROOT)

        print("\n✅ Version bump complete!")


if __name__ == "__main__":
    main()
