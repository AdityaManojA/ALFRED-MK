from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.sentry.focus.state import Cadence

_NUM_WORDS = {
    0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four',
    5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten'
}

def _num_word(n: int) -> str:
    return _NUM_WORDS.get(n, str(n))


class FocusLedger:
    def __init__(self, filepath: Optional[str | Path] = None) -> None:
        if filepath is None:
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            self.filepath = repo_root / 'data' / 'focus_ledger.json'
        else:
            self.filepath = Path(filepath)

        self._data: Dict[str, Any] = {
            'total_sessions': 0,
            'total_planned_seconds': 0,
            'total_on_target_seconds': 0,
            'total_drift_count': 0,
            'clean_streak': 0,
            'best_clean_streak': 0,
            'daily_buckets': {},
        }
        self.load()

    def load(self) -> None:
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, dict):
                    self._data.update(content)
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=self.filepath.parent, delete=False, encoding='utf-8') as tf:
                json.dump(self._data, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, self.filepath)
        except Exception:
            pass

    @property
    def clean_streak(self) -> int:
        return int(self._data.get('clean_streak', 0))

    @property
    def best_clean_streak(self) -> int:
        return int(self._data.get('best_clean_streak', 0))

    @property
    def total_sessions(self) -> int:
        return int(self._data.get('total_sessions', 0))

    def record_session(
        self,
        planned_seconds: int,
        on_target_seconds: int,
        drift_count: int,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        ts = timestamp if timestamp is not None else time.time()
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

        prev_streak = self.clean_streak
        new_streak = prev_streak
        streak_broken = False

        if drift_count == 0:
            new_streak = prev_streak + 1
            best = max(self.best_clean_streak, new_streak)
            self._data['clean_streak'] = new_streak
            self._data['best_clean_streak'] = best
        else:
            if prev_streak >= 3:
                streak_broken = True
            new_streak = 0
            self._data['clean_streak'] = 0

        self._data['total_sessions'] = self._data.get('total_sessions', 0) + 1
        self._data['total_planned_seconds'] = self._data.get('total_planned_seconds', 0) + int(planned_seconds)
        self._data['total_on_target_seconds'] = self._data.get('total_on_target_seconds', 0) + int(on_target_seconds)
        self._data['total_drift_count'] = self._data.get('total_drift_count', 0) + int(drift_count)

        buckets = self._data.setdefault('daily_buckets', {})
        day_bucket = buckets.setdefault(date_str, {'sessions': 0, 'on_target_s': 0, 'drift_count': 0})
        day_bucket['sessions'] += 1
        day_bucket['on_target_s'] += int(on_target_seconds)
        day_bucket['drift_count'] += int(drift_count)

        self.save()

        return {
            'previous_streak': prev_streak,
            'clean_streak': new_streak,
            'streak_broken': streak_broken,
            'best_clean_streak': self._data['best_clean_streak'],
        }

    def generate_report_card(
        self,
        planned_seconds: int,
        on_target_seconds: int,
        drift_count: int,
        cadence: Cadence | str,
        previous_streak: int,
        clean_streak: int,
        streak_broken: bool,
    ) -> str:
        planned_m = max(1, round(planned_seconds / 60))
        on_target_m = round(on_target_seconds / 60)
        c = cadence.value if isinstance(cadence, Cadence) else str(cadence)

        if c == Cadence.GENTLE.value:
            if drift_count == 0:
                streak_str = _num_word(clean_streak)
                return f'Well done, sir. {planned_m} minutes wrapped up, with complete focus. Clean streak is now {streak_str}.'
            elif streak_broken:
                prev_str = _num_word(previous_streak)
                slip_str = 'one small slip' if drift_count == 1 else f'{_num_word(drift_count)} small slips'
                return f'Session wrapped up, sir. {planned_m} minutes planned, with {slip_str}. Clean streak broken at {prev_str}. Take a breath.'
            elif drift_count == 1:
                return f'Well done, sir. {planned_m} minutes wrapped up, with only one small slip. Take a breath.'
            else:
                slips = f'{_num_word(drift_count)} small slips'
                return f'Well done, sir. {planned_m} minutes wrapped up, with only {slips}. Take a breath.'

        elif c == Cadence.DRILL_SERGEANT.value:
            if drift_count == 0:
                streak_str = _num_word(clean_streak)
                return f'Session complete. {on_target_m} of {planned_m} minutes locked on target. Zero slips. Clean streak is now {streak_str}.'
            elif streak_broken:
                prev_str = _num_word(previous_streak)
                slip_w = _num_word(drift_count)
                slips_text = f'{slip_w} slips is {slip_w} too many' if drift_count > 1 else 'One slip is one too many'
                return f'Session over. {on_target_m} of {planned_m} on target. {slips_text}. Clean streak broken at {prev_str}. Reset and go again.'
            else:
                slip_w = _num_word(drift_count)
                slips_text = f'{slip_w} slips is {slip_w} too many' if drift_count > 1 else 'One slip is one too many'
                return f'Session over. {on_target_m} of {planned_m} on target. {slips_text}. Reset and go again.'

        else:
            # Normal cadence
            detours_str = 'no detours' if drift_count == 0 else ('one brief detour' if drift_count == 1 else ('two brief detours' if drift_count == 2 else f'{_num_word(drift_count)} brief detours'))
            streak_suffix = ''
            if drift_count == 0:
                streak_suffix = f' Clean streak is now {_num_word(clean_streak)}.'
            elif streak_broken:
                streak_suffix = f' Clean streak broken at {_num_word(previous_streak)}.'
            return f'Session complete, sir. {planned_m} minutes planned, {on_target_m} on target, {detours_str}.{streak_suffix}'
