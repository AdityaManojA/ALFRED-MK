"""
tests/test_alexa_verification.py — Unit tests for Amazon Skills Kit request validation and verification.
"""
import time
import unittest
from datetime import datetime, timezone

from server.alexa.verification import (
    AlexaRequestVerifier,
    RequestReplayCache,
    validate_certificate_url,
    validate_skill_id,
    validate_timestamp,
)


class TestAlexaVerification(unittest.TestCase):
    """Test suite validating Amazon Skills Kit request verification rules."""

    def test_certificate_url_validation(self):
        # Valid URLs
        valid_urls = [
            "https://s3.amazonaws.com/echo.api/echo.api.cert",
            "https://s3.amazonaws.com:443/echo.api/cert-chain.pem",
            "HTTPS://S3.AMAZONAWS.COM/echo.api/test.pem",
        ]
        for url in valid_urls:
            ok, err = validate_certificate_url(url)
            self.assertTrue(ok, f"Failed for valid URL {url}: {err}")

        # Invalid URLs
        invalid_urls = [
            ("http://s3.amazonaws.com/echo.api/cert", "scheme"),
            ("https://attacker.com/echo.api/cert", "hostname"),
            ("https://s3.amazonaws.com/malicious/cert", "path"),
            ("https://s3.amazonaws.com:8080/echo.api/cert", "port"),
            ("", "missing"),
        ]
        for url, reason in invalid_urls:
            ok, err = validate_certificate_url(url)
            self.assertFalse(ok, f"Should have failed for {reason}: {url}")

    def test_timestamp_freshness(self):
        now_dt = datetime.now(timezone.utc)
        valid_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, err = validate_timestamp(valid_iso)
        self.assertTrue(ok, f"Current timestamp failed: {err}")

        # Stale timestamp (1 hour ago)
        stale_iso = "2020-01-01T00:00:00Z"
        ok, err = validate_timestamp(stale_iso)
        self.assertFalse(ok)
        self.assertIn("stale", err.lower())

    def test_skill_id_validation(self):
        expected_id = "amzn1.ask.skill.12345678-abcd-1234-abcd-1234567890ab"

        # Match
        ok, err = validate_skill_id(expected_id, expected_id)
        self.assertTrue(ok)

        # Mismatch
        ok, err = validate_skill_id("amzn1.ask.skill.other", expected_id)
        self.assertFalse(ok)

    def test_replay_protection(self):
        cache = RequestReplayCache(ttl_s=10.0)
        req_id = "amzn1.echo-api.request.unique-id-1"

        # First time: not replayed
        self.assertFalse(cache.is_replayed(req_id))

        # Second time: replayed!
        self.assertTrue(cache.is_replayed(req_id))

    def test_consolidated_verifier(self):
        expected_id = "amzn1.ask.skill.valid-test-id"
        verifier = AlexaRequestVerifier(expected_skill_id=expected_id, skip_signature_for_dev=True)

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Valid request payload
        valid_payload = {
            "session": {
                "application": {"applicationId": expected_id},
            },
            "request": {
                "type": "IntentRequest",
                "requestId": "req-001",
                "timestamp": now_iso,
                "intent": {"name": "AlfredStatusIntent"},
            },
        }
        ok, code, cat = verifier.verify_request({}, b"{}", valid_payload)
        self.assertTrue(ok)
        self.assertEqual(code, 200)

        # 2. Wrong skill ID
        bad_skill_payload = {
            "session": {
                "application": {"applicationId": "wrong-id"},
            },
            "request": {
                "requestId": "req-002",
                "timestamp": now_iso,
            },
        }
        ok, code, cat = verifier.verify_request({}, b"{}", bad_skill_payload)
        self.assertFalse(ok)
        self.assertEqual(cat, "SKILL_ID_MISMATCH")

        # 3. Stale timestamp
        stale_payload = {
            "session": {
                "application": {"applicationId": expected_id},
            },
            "request": {
                "requestId": "req-003",
                "timestamp": "2020-01-01T00:00:00Z",
            },
        }
        ok, code, cat = verifier.verify_request({}, b"{}", stale_payload)
        self.assertFalse(ok)
        self.assertEqual(cat, "TIMESTAMP_STALE")

        # 5. Oversized payload
        oversized_bytes = b"x" * (65 * 1024)
        ok, code, cat = verifier.verify_request({}, oversized_bytes, valid_payload)
        self.assertFalse(ok)
        self.assertEqual(code, 413)
        self.assertEqual(cat, "OVERSIZED_PAYLOAD")

        # 6. Malformed payload
        ok, code, cat = verifier.verify_request({}, b"{}", {"invalid": True})
        self.assertFalse(ok)
        self.assertEqual(code, 400)
        self.assertEqual(cat, "MALFORMED_PAYLOAD")

    def test_signature_and_cert_verification(self):
        expected_id = "amzn1.ask.skill.strict-id"
        verifier = AlexaRequestVerifier(expected_skill_id=expected_id, skip_signature_for_dev=False)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "session": {"application": {"applicationId": expected_id}},
            "request": {
                "type": "IntentRequest",
                "requestId": "req-strict-1",
                "timestamp": now_iso,
            },
        }

        # Invalid cert URL
        headers_bad_cert = {
            "SignatureCertChainUrl": "http://evil.com/cert",
            "Signature-256": "dummy-sig",
        }
        ok, code, cat = verifier.verify_request(headers_bad_cert, b"{}", payload)
        self.assertFalse(ok)
        self.assertEqual(cat, "INVALID_CERT_URL")

        # Missing signature
        payload_2 = {
            "session": {"application": {"applicationId": expected_id}},
            "request": {
                "type": "IntentRequest",
                "requestId": "req-strict-2",
                "timestamp": now_iso,
            },
        }
        headers_no_sig = {
            "SignatureCertChainUrl": "https://s3.amazonaws.com/echo.api/cert.pem",
        }
        ok, code, cat = verifier.verify_request(headers_no_sig, b"{}", payload_2)
        self.assertFalse(ok)
        self.assertEqual(cat, "MISSING_SIGNATURE")


if __name__ == "__main__":
    unittest.main()
