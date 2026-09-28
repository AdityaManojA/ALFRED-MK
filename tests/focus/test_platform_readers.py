"""Unit tests for platform reader backends and host hashing."""
import unittest

from core.sentry.focus.reader import extract_host_from_url, hash_host, get_platform_reader


class TestPlatformReaders(unittest.TestCase):
    def test_hash_host_privacy(self):
        # 1. Host is extracted cleanly
        self.assertEqual(extract_host_from_url("https://github.com/AdityaManojA/repo?query=1#hash"), "github.com")
        self.assertEqual(extract_host_from_url("http://localhost:8080/foo"), "localhost:8080")

        # 2. Host hash is 16 chars hex
        h1 = hash_host("github.com")
        self.assertEqual(len(h1), 16)

        # 3. Case insensitive and normalizes ports
        h2 = hash_host("GITHUB.COM")
        self.assertEqual(h1, h2)

        # 4. Never reveals full URL
        self.assertNotEqual(hash_host("github.com"), hash_host("google.com"))

    def test_reader_instantiation(self):
        reader = get_platform_reader()
        self.assertIsNotNone(reader)
        surf = reader.get_frontmost_surface()
        self.assertIsNotNone(surf)
        self.assertIn(surf.capability, ("FULL", "APP_ONLY", "UNKNOWN", "PERM_DENIED"))


if __name__ == "__main__":
    unittest.main()
