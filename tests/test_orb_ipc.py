"""
tests/test_orb_ipc.py — Unit tests for the Orb IPC server and Swift companion integration.
"""

import json
import os
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from core.orb_ipc import OrbIPCServer, build_native_orb_binary


class TestOrbIPC(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sock_path = os.path.join(self.temp_dir.name, "test_orb.sock")
        self.server = OrbIPCServer(socket_path=self.sock_path)

    def tearDown(self):
        self.server.stop()
        self.temp_dir.cleanup()

    @unittest.skipIf(sys.platform != "darwin" and not hasattr(socket, "AF_UNIX"), "Unix sockets required")
    def test_server_starts_and_accepts_client(self):
        self.assertTrue(self.server.start())
        self.assertTrue(os.path.exists(self.sock_path))

        # Connect client
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(self.sock_path)
        time.sleep(0.1)

        with self.server._clients_lock:
            self.assertEqual(len(self.server._clients), 1)

        # Broadcast state
        self.server.broadcast({"state": "LISTENING", "rms": 0.5})
        client.settimeout(2.0)
        data = client.recv(1024).decode("utf-8")
        self.assertIn("LISTENING", data)
        msg = json.loads(data.strip().split("\n")[0])
        self.assertEqual(msg["state"], "LISTENING")
        self.assertEqual(msg["rms"], 0.5)

        client.close()

    @unittest.skipIf(sys.platform != "darwin" and not hasattr(socket, "AF_UNIX"), "Unix sockets required")
    def test_client_sends_action_dispatches_callback(self):
        received = []

        def callback(action, payload):
            received.append((action, payload))

        self.server.set_action_callback(callback)
        self.assertTrue(self.server.start())

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(self.sock_path)
        time.sleep(0.1)

        msg = json.dumps({"action": "tap", "timestamp": 12345}) + "\n"
        client.sendall(msg.encode("utf-8"))
        time.sleep(0.2)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "tap")
        self.assertEqual(received[0][1]["action"], "tap")

        client.close()

    @unittest.skipIf(sys.platform != "darwin", "macOS required for Swift compilation")
    def test_build_native_orb_binary_exists(self):
        ok = build_native_orb_binary()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
