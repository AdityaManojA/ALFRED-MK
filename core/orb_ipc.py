"""
core/orb_ipc.py — Ultra-low-latency IPC bridge between ALFRED Python core
and native frontends (e.g., Swift/Metal Bat Globe Orb on macOS).

Architecture:
- Unix domain socket (/tmp/alfred_orb.sock) for zero-network-overhead local IPC.
- Thread-safe broadcast of agent state, audio RMS energy, and viseme data.
- Bi-directional: receives native user events (clicks, double-clicks, gestures)
  and dispatches them into ALFRED actions.
- Fail-open: if no native client is connected, broadcast is a fast no-op.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("core.orb_ipc")

SOCKET_PATH = "/tmp/alfred_orb.sock"
BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
SWIFT_SOURCE = Path(__file__).resolve().parent.parent / "native" / "macos" / "BatGlobeOrb.swift"
SWIFT_BINARY = BIN_DIR / "BatGlobeOrb"


class OrbIPCServer:
    """Unix Domain Socket server broadcasting ALFRED state to native frontends."""

    def __init__(self, socket_path: str = SOCKET_PATH):
        self.socket_path = socket_path
        self._server_sock: Optional[socket.socket] = None
        self._clients: set[socket.socket] = set()
        self._clients_lock = threading.Lock()
        self._running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._on_action_callback: Optional[Callable[[str, dict], None]] = None

    def set_action_callback(self, cb: Callable[[str, dict], None]) -> None:
        """Register callback for handling events sent from the native Orb."""
        self._on_action_callback = cb

    def start(self) -> bool:
        """Start the IPC socket server in a background daemon thread."""
        if self._running:
            return True

        if sys.platform != "darwin" and not hasattr(socket, "AF_UNIX"):
            logger.info("OrbIPC: Unix domain sockets not supported on this platform.")
            return False

        try:
            if os.path.exists(self.socket_path):
                try:
                    os.unlink(self.socket_path)
                except OSError:
                    pass

            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(self.socket_path)
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
            self._running = True

            self._listen_thread = threading.Thread(
                target=self._accept_loop, daemon=True, name="alfred-orb-ipc-accept"
            )
            self._listen_thread.start()
            logger.info(f"OrbIPC: Server listening on {self.socket_path}")
            return True
        except Exception as e:
            logger.warning(f"OrbIPC: Failed to start socket server: {e}")
            self._running = False
            return False

    def _accept_loop(self) -> None:
        """Accept incoming client connections."""
        while self._running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
                with self._clients_lock:
                    self._clients.add(conn)
                logger.info("OrbIPC: Native Orb frontend connected.")
                client_thread = threading.Thread(
                    target=self._client_read_loop, args=(conn,), daemon=True, name="alfred-orb-client-reader"
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.debug(f"OrbIPC accept error: {e}")
                break

    def _client_read_loop(self, conn: socket.socket) -> None:
        """Read incoming JSON commands from a connected native client."""
        buf = ""
        while self._running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_client_message(line)
            except Exception:
                break

        with self._clients_lock:
            self._clients.discard(conn)
        try:
            conn.close()
        except Exception:
            pass
        logger.info("OrbIPC: Native Orb frontend disconnected.")

    def _handle_client_message(self, raw: str) -> None:
        """Dispatch JSON event from native client."""
        try:
            msg = json.loads(raw)
            action = msg.get("action", "")
            if self._on_action_callback and action:
                self._on_action_callback(action, msg)
        except Exception as e:
            logger.debug(f"OrbIPC: Failed to parse client message '{raw}': {e}")

    def broadcast(self, payload: dict) -> None:
        """Send JSON state update to all connected native frontends."""
        if not self._clients:
            return

        try:
            data = (json.dumps(payload) + "\n").encode("utf-8")
        except Exception:
            return

        with self._clients_lock:
            stale = []
            for client in self._clients:
                try:
                    client.sendall(data)
                except Exception:
                    stale.append(client)
            for dead in stale:
                self._clients.discard(dead)
                try:
                    dead.close()
                except Exception:
                    pass

    def stop(self) -> None:
        """Stop server and disconnect clients."""
        self._running = False
        with self._clients_lock:
            for client in self._clients:
                try:
                    client.close()
                except Exception:
                    pass
            self._clients.clear()

        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
        logger.info("OrbIPC: Server stopped.")


def build_native_orb_binary() -> bool:
    """Compile BatGlobeOrb.swift into bin/BatGlobeOrb if needed."""
    if sys.platform != "darwin":
        return False

    if SWIFT_BINARY.exists() and SWIFT_BINARY.stat().st_mtime >= SWIFT_SOURCE.stat().st_mtime:
        return True

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("OrbIPC: Compiling native macOS Swift Bat Globe Orb…")
    try:
        cmd = [
            "swiftc",
            "-O",
            "-o", str(SWIFT_BINARY),
            str(SWIFT_SOURCE),
            "-framework", "Cocoa",
            "-framework", "SwiftUI",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and SWIFT_BINARY.exists():
            SWIFT_BINARY.chmod(0o755)
            logger.info("OrbIPC: Native Swift Orb compiled successfully.")
            return True
        else:
            logger.warning(f"OrbIPC: Swift compilation failed: {r.stderr}")
            return False
    except Exception as e:
        logger.warning(f"OrbIPC: Swift compilation error: {e}")
        return False


def launch_native_orb() -> Optional[subprocess.Popen]:
    """Compile (if needed) and launch the native macOS Bat Globe Orb companion process."""
    if sys.platform != "darwin":
        return None

    if not build_native_orb_binary():
        return None

    try:
        proc = subprocess.Popen(
            [str(SWIFT_BINARY)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception as e:
        logger.warning(f"OrbIPC: Failed to launch native Swift Orb: {e}")
        return None


_GLOBAL_SERVER: Optional[OrbIPCServer] = None
_GLOBAL_LOCK = threading.Lock()


def get_orb_ipc_server() -> OrbIPCServer:
    """Retrieve or create the process singleton OrbIPCServer."""
    global _GLOBAL_SERVER
    with _GLOBAL_LOCK:
        if _GLOBAL_SERVER is None:
            _GLOBAL_SERVER = OrbIPCServer()
            _GLOBAL_SERVER.start()
        return _GLOBAL_SERVER
