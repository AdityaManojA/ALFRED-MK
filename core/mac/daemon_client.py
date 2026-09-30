"""Client for alfredd, the native wake-word listener (mac/alfredd).

Newline-delimited JSON over ~/Library/Application Support/ALFRED/alfredd.sock.
Reconnects on its own if the listener restarts.
"""
from __future__ import annotations

import itertools
import json
import os
import socket
import threading
import time
from pathlib import Path

SOCKET_PATH = str(Path.home() / "Library/Application Support/ALFRED/alfredd.sock")
# Written by mac/build.sh: the listener is installed even if it is restarting right now.
INSTALLED_MARKER = str(Path.home() / "Library/Application Support/ALFRED/daemon.json")


class DaemonClient:
    def __init__(self, path: str = SOCKET_PATH):
        self.path = path
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._handlers: dict[str, list] = {}
        self._pending: dict[int, tuple[threading.Event, dict]] = {}
        self._ids = itertools.count(1)
        self.connected = threading.Event()
        self._stop = False
        self._started = False

    def on(self, msg_type: str, fn) -> None:
        self._handlers.setdefault(msg_type, []).append(fn)

    def start(self) -> None:
        """Connect in the background. Register handlers first: alfredd flushes
        queued messages (the wake + command that launched us) on hello."""
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._run, name="alfredd-client", daemon=True).start()

    def _run(self) -> None:
        while not self._stop:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self.path)
            except OSError:
                time.sleep(3)
                continue
            self._sock = s
            self.send({"type": "hello", "role": "agent", "pid": os.getpid()})
            self.connected.set()
            buf = b""
            try:
                while True:
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            self._dispatch(json.loads(line))
                        except ValueError:
                            pass
            except OSError:
                pass
            self.connected.clear()
            self._sock = None
            try:
                s.close()
            except OSError:
                pass
            time.sleep(1)

    def _dispatch(self, msg: dict) -> None:
        if msg.get("type") == "reply" and "req" in msg:
            waiter = self._pending.pop(msg["req"], None)
            if waiter:
                waiter[1].update(msg)
                waiter[0].set()
            return
        for fn in self._handlers.get(msg.get("type", ""), []):
            try:
                fn(msg)
            except Exception as e:
                print(f"[alfredd] handler error for {msg.get('type')}: {e}")

    def send(self, obj: dict) -> bool:
        s = self._sock
        if s is None:
            return False
        data = (json.dumps(obj) + "\n").encode()
        with self._send_lock:
            try:
                s.sendall(data)
                return True
            except OSError:
                return False

    def request(self, obj: dict, timeout: float = 5.0) -> dict | None:
        if not self.connected.wait(timeout):
            return None
        rid = next(self._ids)
        ev, box = threading.Event(), {}
        self._pending[rid] = (ev, box)
        if not self.send({**obj, "req": rid}):
            self._pending.pop(rid, None)
            return None
        if not ev.wait(timeout):
            self._pending.pop(rid, None)
            return None
        return box


_client: DaemonClient | None = None


def get_client(start: bool = True) -> DaemonClient | None:
    """Shared client, or None when the listener isn't installed."""
    global _client
    installed = os.path.exists(SOCKET_PATH) or os.path.exists(INSTALLED_MARKER)
    if _client is None and installed and not os.environ.get("ALFRED_NO_DAEMON"):
        _client = DaemonClient()
    if _client is not None and start:
        _client.start()
    return _client
