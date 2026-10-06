"""
core/speaker/profile_store.py — Persistent, versioned storage for enrolled speaker profiles.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import stat
import sys
import threading
from typing import Dict, List, Optional

from core.speaker.types import SpeakerProfile

_LOGGER = logging.getLogger("core.speaker.profile_store")

DEFAULT_STORAGE_DIR = Path.home() / ".alfred" / "voice_profiles"


class SpeakerProfileStore:
    """Thread-safe persistent store for local speaker profiles.

    Stores versioned JSON profiles in per-user application-data directory
    (~/.alfred/voice_profiles) using atomic writes and corruption guards.
    """

    def __init__(self, storage_dir: Optional[Path | str] = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
        self._lock = threading.RLock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            # Restrict directory permissions to user on POSIX
            if sys.platform != "win32":
                try:
                    os.chmod(self.storage_dir, stat.S_IRWXU)  # 0700
                except Exception:
                    pass
        except Exception as e:
            _LOGGER.warning(f"Could not initialize speaker profile storage dir: {e}")

    def _profile_path(self, profile_id: str) -> Path:
        safe_id = "".join(c for c in profile_id if c.isalnum() or c in ("-", "_")).lower()
        return self.storage_dir / f"{safe_id}.json"

    def save_profile(self, profile: SpeakerProfile) -> bool:
        """Atomically persist an enrolled profile to disk."""
        with self._lock:
            self._ensure_dir()
            target_path = self._profile_path(profile.profile_id)
            tmp_path = target_path.with_suffix(".tmp")
            try:
                data = profile.to_dict()
                payload = json.dumps(data, indent=2)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(payload)

                if sys.platform != "win32":
                    try:
                        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
                    except Exception:
                        pass

                # Atomic replace
                tmp_path.replace(target_path)
                return True
            except Exception as e:
                _LOGGER.error(f"Failed to save profile {profile.profile_id}: {e}")
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                return False

    def get_profile(self, profile_id: str) -> Optional[SpeakerProfile]:
        """Load a profile by ID or user name."""
        with self._lock:
            # Check normalized profile id first
            norm_id = profile_id.strip().lower().replace(" ", "_")
            path = self._profile_path(norm_id)
            if not path.is_file():
                # Try exact
                path = self._profile_path(profile_id)
            if not path.is_file():
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SpeakerProfile.from_dict(data)
            except Exception as e:
                _LOGGER.warning(f"Corrupt or unreadable profile at {path}: {e}")
                return None

    load_profile = get_profile

    def list_profiles(self) -> List[SpeakerProfile]:
        """List all valid enrolled profiles."""
        profiles = []
        with self._lock:
            if not self.storage_dir.is_dir():
                return profiles

            for f in sorted(self.storage_dir.glob("*.json")):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    profiles.append(SpeakerProfile.from_dict(data))
                except Exception as e:
                    _LOGGER.warning(f"Ignoring invalid profile {f.name}: {e}")
        return profiles

    def delete_profile(self, profile_id: str) -> bool:
        """Delete an enrolled profile."""
        with self._lock:
            path = self._profile_path(profile_id)
            if path.is_file():
                try:
                    path.unlink()
                    return True
                except Exception as e:
                    _LOGGER.error(f"Failed to delete profile {profile_id}: {e}")
                    return False
            return False

    def has_enrolled_profiles(self) -> bool:
        """True if at least one valid enrolled profile exists."""
        return len(self.list_profiles()) > 0


LocalProfileStore = SpeakerProfileStore
ProfileStore = SpeakerProfileStore

_DEFAULT_STORE: Optional[SpeakerProfileStore] = None
_STORE_LOCK = threading.Lock()


def get_default_profile_store(storage_dir: Optional[Path | str] = None) -> SpeakerProfileStore:
    """Get the process-wide default SpeakerProfileStore singleton."""
    global _DEFAULT_STORE
    with _STORE_LOCK:
        if _DEFAULT_STORE is None or storage_dir is not None:
            _DEFAULT_STORE = SpeakerProfileStore(storage_dir=storage_dir)
        return _DEFAULT_STORE
