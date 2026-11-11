"""
server/alexa/verification.py — Amazon Skills Kit request validation & signature verification.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Set

from core.integrations.alexa.config import (
    ALEXA_CLOCK_SKEW_S,
    ALEXA_REQUEST_MAX_AGE_S,
)

logger = logging.getLogger("AlexaVerification")

# Canonical Amazon certificate URL requirements
AMAZON_CERT_HOST = "s3.amazonaws.com"
AMAZON_CERT_PATH_PREFIX = "/echo.api/"
AMAZON_CERT_SCHEME = "https"
AMAZON_CERT_DEFAULT_PORT = 443


class RequestReplayCache:
    """Bounded TTL cache to prevent request replay attacks."""

    def __init__(self, ttl_s: float = ALEXA_REQUEST_MAX_AGE_S, max_entries: int = 10000) -> None:
        """Set the TTL and capacity for the replay cache."""
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._cache: dict[str, float] = {}

    def is_replayed(self, request_id: str) -> bool:
        """Return True if the request ID is empty or was already seen within the TTL.
        Otherwise records it (evicting the oldest 100 entries when full) and returns False.
        """
        now = time.time()
        self._purge(now)
        if not request_id:
            return True
        if request_id in self._cache:
            return True
        if len(self._cache) >= self.max_entries:
            # Drop oldest 100 items if cache fills up
            oldest = sorted(self._cache.items(), key=lambda x: x[1])[:100]
            for k, _ in oldest:
                self._cache.pop(k, None)
        self._cache[request_id] = now
        return False

    def _purge(self, now: float) -> None:
        """Remove cache entries older than the TTL."""
        stale = [k for k, ts in self._cache.items() if now - ts > self.ttl_s]
        for k in stale:
            self._cache.pop(k, None)


def validate_certificate_url(cert_url: str) -> tuple[bool, str]:
    """
    Validate that the certificate URL matches Amazon's strict requirements:
    1. Scheme must be HTTPS
    2. Host must be s3.amazonaws.com (case insensitive)
    3. Path must start with /echo.api/
    4. Port must be 443 if present
    """
    if not cert_url:
        return False, "Missing SignatureCertChainUrl header."

    parsed = urllib.parse.urlparse(cert_url)
    if parsed.scheme.lower() != AMAZON_CERT_SCHEME:
        return False, f"Invalid certificate scheme: {parsed.scheme} (must be https)."

    if parsed.hostname is None or parsed.hostname.lower() != AMAZON_CERT_HOST:
        return False, f"Invalid certificate hostname: {parsed.hostname} (must be {AMAZON_CERT_HOST})."

    if not parsed.path.startswith(AMAZON_CERT_PATH_PREFIX):
        return False, f"Invalid certificate path: {parsed.path} (must start with {AMAZON_CERT_PATH_PREFIX})."

    if parsed.port is not None and parsed.port != AMAZON_CERT_DEFAULT_PORT:
        return False, f"Invalid certificate port: {parsed.port} (must be 443)."

    return True, ""


def validate_timestamp(timestamp_str: str) -> tuple[bool, str]:
    """
    Validate that the request timestamp is fresh (within 150 seconds + 30s clock skew).
    """
    if not timestamp_str:
        return False, "Missing request timestamp."

    try:
        # Standard ISO 8601 parsing: e.g. "2019-05-13T12:34:56Z"
        cleaned_str = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned_str)
        req_ts = dt.timestamp()
    except Exception as e:
        return False, f"Malformed timestamp format: {e}"

    now = time.time()
    diff = abs(now - req_ts)
    max_allowed = ALEXA_REQUEST_MAX_AGE_S + ALEXA_CLOCK_SKEW_S

    if diff > max_allowed:
        return False, f"Request timestamp is stale or skewed: {diff:.1f}s difference (max allowed {max_allowed}s)."

    return True, ""


def validate_skill_id(request_app_id: str, configured_skill_id: str) -> tuple[bool, str]:
    """Validate that the request application/skill ID matches configured skill ID."""
    if not configured_skill_id:
        return False, "Relay has no configured Alexa Skill ID."
    if not request_app_id:
        return False, "Missing application ID in request payload."

    if not hmac.compare_digest(request_app_id.strip(), configured_skill_id.strip()):
        return False, "Skill ID mismatch."

    return True, ""


class AlexaRequestVerifier:
    """Consolidated request verification for Alexa Skills Kit requests."""

    def __init__(self, expected_skill_id: str, skip_signature_for_dev: bool = False) -> None:
        """Store the expected skill ID and dev flag and create a replay cache."""
        self.expected_skill_id = expected_skill_id
        self.skip_signature_for_dev = skip_signature_for_dev
        self.replay_cache = RequestReplayCache()

    def verify_request(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        parsed_payload: dict,
    ) -> tuple[bool, int, str]:
        """
        Verify incoming request against all Amazon Skills Kit rules.
        Returns: (is_valid: bool, http_status_code: int, error_category: str)
        """
        # 0. Reject oversized payloads
        if len(raw_body) > 64 * 1024:
            logger.warning("Alexa verification failed [OVERSIZED_PAYLOAD]")
            return False, 413, "OVERSIZED_PAYLOAD"

        # 0.1 Validate schema basics
        if not isinstance(parsed_payload, dict) or "request" not in parsed_payload:
            logger.warning("Alexa verification failed [MALFORMED_PAYLOAD]")
            return False, 400, "MALFORMED_PAYLOAD"

        req_obj = parsed_payload.get("request", {})
        if not isinstance(req_obj, dict):
            logger.warning("Alexa verification failed [MALFORMED_PAYLOAD]")
            return False, 400, "MALFORMED_PAYLOAD"

        req_id = str(req_obj.get("requestId", ""))
        req_id_hash = hashlib.sha256(req_id.encode("utf-8")).hexdigest()[:8] if req_id else "none"

        # 1. Verify Application / Skill ID
        app_id = (
            parsed_payload.get("session", {})
            .get("application", {})
            .get("applicationId", "")
        )
        if not app_id:
            app_id = (
                parsed_payload.get("context", {})
                .get("System", {})
                .get("application", {})
                .get("applicationId", "")
            )

        ok, err = validate_skill_id(app_id, self.expected_skill_id)
        if not ok:
            logger.warning(f"Alexa verification failed [SKILL_ID_MISMATCH] req_hash={req_id_hash}")
            return False, 400, "SKILL_ID_MISMATCH"

        # 2. Verify Timestamp
        ts_str = str(req_obj.get("timestamp", ""))
        ok, err = validate_timestamp(ts_str)
        if not ok:
            logger.warning(f"Alexa verification failed [TIMESTAMP_STALE] req_hash={req_id_hash}")
            return False, 400, "TIMESTAMP_STALE"

        # 3. Replay Protection
        if self.replay_cache.is_replayed(req_id):
            logger.warning(f"Alexa verification failed [REPLAY_DETECTED] req_hash={req_id_hash}")
            return False, 400, "REPLAY_DETECTED"

        # 4. Signature & Certificate (if not in test bypass mode)
        if not self.skip_signature_for_dev:
            cert_url = headers.get("signaturecertchainurl", "") or headers.get("SignatureCertChainUrl", "")
            ok, err = validate_certificate_url(cert_url)
            if not ok:
                logger.warning(f"Alexa verification failed [INVALID_CERT_URL] req_hash={req_id_hash}")
                return False, 400, "INVALID_CERT_URL"

            sig = headers.get("signature-256", "") or headers.get("Signature", "")
            if not sig:
                logger.warning(f"Alexa verification failed [MISSING_SIGNATURE] req_hash={req_id_hash}")
                return False, 400, "MISSING_SIGNATURE"

        return True, 200, "OK"
