"""
core/secrets/store.py — Encrypted Secrets Store for ALFRED-MK-VIII.

Provides:
- Machine-local encrypted storage at ~/.alfred/secrets.env using cryptography.Fernet.
- Master key generation and storage in system keyring (falling back to PBKDF2 machine fingerprint).
- Atomic file writes and thread-safe get/set/delete operations.
- Format validation with custom regex patterns.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

# ── Named Constants ──────────────────────────────────────────────────────────
KEYRING_SERVICE: str = "alfred-ai"
KEYRING_USERNAME: str = "alfred-master-key"
MASTER_KEY_LENGTH: int = 32
DEFAULT_SECRETS_DIR: Path = Path.home() / ".alfred"
SECRETS_FILE_NAME: str = "secrets.env"


def get_secrets_file_path() -> Path:
    """Return the absolute path to secrets.env."""
    override = os.environ.get("ALFRED_SECRETS_FILE")
    if override:
        return Path(override)
    d = DEFAULT_SECRETS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / SECRETS_FILE_NAME


class SecretStore:
    """
    Thread-safe, encrypted key-value store for API tokens and credentials.
    """
    _instance: Optional[SecretStore] = None
    _lock = threading.RLock()

    def __init__(self, secrets_path: Optional[Path] = None):
        self._path = secrets_path or get_secrets_file_path()
        self._cache: dict[str, str] = {}
        self._fernet: Optional[Fernet] = None
        self._rw_lock = threading.RLock()
        self._init_encryption()
        self._load()

    @classmethod
    def get_instance(cls) -> SecretStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_machine_fingerprint(self) -> bytes:
        """Derive a reproducible deterministic machine-local seed."""
        components = [
            socket.gethostname(),
            platform.machine(),
            platform.node(),
            platform.processor(),
            str(Path.home()),
        ]
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    components.append(str(guid))
            except Exception:
                pass
        raw = "|".join(components).encode("utf-8")
        return hashlib.sha256(raw).digest()

    def _derive_fernet_key(self, raw_bytes: bytes) -> bytes:
        """Derive a url-safe base64 32-byte Fernet key."""
        salt = b"ALFRED_MK_V_SECRETS_SALT_2026"
        if _CRYPTO_AVAILABLE:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100_000,
            )
            key = kdf.derive(raw_bytes)
            return base64.urlsafe_b64encode(key)
        else:
            # Fallback when cryptography is not available
            h = hashlib.sha256(raw_bytes + salt).digest()
            return base64.urlsafe_b64encode(h)

    def _init_encryption(self) -> None:
        """Initialize or load master encryption key from keyring or machine seed."""
        key_str = None
        if _KEYRING_AVAILABLE:
            try:
                key_str = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            except Exception:
                key_str = None

        if not key_str:
            # Generate new or derive from machine fingerprint
            if _CRYPTO_AVAILABLE and _KEYRING_AVAILABLE:
                try:
                    generated = Fernet.generate_key().decode("utf-8")
                    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, generated)
                    key_str = generated
                except Exception:
                    key_str = None

            if not key_str:
                seed = self._get_machine_fingerprint()
                key_str = self._derive_fernet_key(seed).decode("utf-8")

        key_bytes = key_str.encode("utf-8")
        if _CRYPTO_AVAILABLE:
            self._fernet = Fernet(key_bytes)
        else:
            self._fernet = None

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string."""
        if not plaintext:
            return ""
        if self._fernet is not None:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        # Fallback simple XOR/b64 if cryptography is completely missing
        seed = self._get_machine_fingerprint()
        raw = plaintext.encode("utf-8")
        xored = bytes([b ^ seed[i % len(seed)] for i, b in enumerate(raw)])
        return "RAW:" + base64.b64encode(xored).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string."""
        if not ciphertext:
            return ""
        if ciphertext.startswith("RAW:"):
            seed = self._get_machine_fingerprint()
            xored = base64.b64decode(ciphertext[4:])
            return bytes([b ^ seed[i % len(seed)] for i, b in enumerate(xored)]).decode("utf-8")
        if self._fernet is not None:
            try:
                return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
            except Exception:
                return ""
        return ""

    def _load(self) -> None:
        """Load and decrypt all secrets from secrets.env into memory cache."""
        with self._rw_lock:
            self._cache.clear()
            if not self._path.exists():
                return
            try:
                lines = self._path.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    decrypted = self._decrypt(v)
                    if decrypted:
                        self._cache[k] = decrypted
            except Exception as e:
                print(f"[SecretStore] Warning loading secrets: {e}")

    def _save(self) -> None:
        """Atomically persist memory cache to encrypted secrets.env."""
        with self._rw_lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# ALFRED-MK-VIII Encrypted Secrets Store",
                "# Do not edit manually. Machine-local encryption active.",
            ]
            for k, v in sorted(self._cache.items()):
                enc = self._encrypt(v)
                lines.append(f"{k}={enc}")
            content = "\n".join(lines) + "\n"

            # Atomic write to temporary file then replace
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile("w", dir=str(self._path.parent), delete=False, encoding="utf-8") as tf:
                    temp_file = Path(tf.name)
                    tf.write(content)
                shutil.move(str(temp_file), str(self._path))
            except Exception as e:
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise IOError(f"Failed to write encrypted secrets: {e}")

    def set(self, key: str, value: str) -> None:
        """Store a secret under the given key."""
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("Secret key cannot be empty")
        with self._rw_lock:
            self._cache[clean_key] = str(value or "")
            self._save()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a decrypted secret by key."""
        clean_key = str(key or "").strip()
        with self._rw_lock:
            return self._cache.get(clean_key, default)

    def delete(self, key: str) -> bool:
        """Delete a secret by key. Returns True if removed."""
        clean_key = str(key or "").strip()
        with self._rw_lock:
            if clean_key in self._cache:
                del self._cache[clean_key]
                self._save()
                return True
            return False

    def list_keys(self) -> list[str]:
        """Return list of all configured secret keys (never values)."""
        with self._rw_lock:
            return sorted(list(self._cache.keys()))

    def has(self, key: str) -> bool:
        """Check if a secret key exists and has non-empty content."""
        val = self.get(key)
        return bool(val and len(val.strip()) > 0)

    @staticmethod
    def validate_format(value: str, pattern: str) -> bool:
        """Check if a secret value matches a given regex pattern."""
        if not value:
            return False
        return bool(re.match(pattern, value.strip()))


def get_secret_store() -> SecretStore:
    """Convenience getter for singleton SecretStore."""
    return SecretStore.get_instance()
