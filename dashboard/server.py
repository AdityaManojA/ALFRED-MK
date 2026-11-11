"""
dashboard/server.py — ALFRED Local HTTP Dashboard

Plain HTTP on port 8000 (no SSL warnings, no firewall issues).
Security at the application layer: AES-256-CBC with session-key-derived key.
CryptoJS is auto-downloaded once and served locally — no CDN needed after that.

Install deps:  pip install fastapi "uvicorn[standard]" cryptography
"""

import asyncio
import base64
import hashlib
import json
import re
import secrets
import socket
import string
import time
from pathlib import Path

_DEPS_OK = False
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    import uvicorn
    _DEPS_OK = True
except ImportError:
    pass

# python-multipart is required for file uploads — optional dependency
_UPLOAD_OK = False
try:
    from fastapi import UploadFile, File as FastAPIFile
    _UPLOAD_OK = True
except Exception:
    pass

BASE_DIR    = Path(__file__).resolve().parent.parent
STATIC_DIR  = Path(__file__).parent / "static"
PORT        = 8000
MAX_UPLOAD_MB = 500
UPLINK_TIMEOUT_S: float = 5.0
RECONNECT_BASE_S: float = 0.5
RECONNECT_MAX_S: float = 5.0
UPLINK_HISTORY_N: int = 100


def _make_uploads_dir() -> Path:
    """Return (and create) the cross-platform uploads folder."""
    for candidate in [
        Path.home() / "Downloads" / "ALFRED Uploads",
        Path.home() / "Documents" / "ALFRED Uploads",
        Path.home() / "Downloads" / "JARVIS Uploads",
        Path.home() / "Documents" / "JARVIS Uploads",
        BASE_DIR / "uploads",
    ]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            pass
    return BASE_DIR / "uploads"


UPLOADS_DIR = _make_uploads_dir()

def _get_gemini_key() -> str | None:
    """Return the Gemini API key from config/api_keys.json, or None if unavailable."""
    try:
        import json as _json
        with open(BASE_DIR / "config" / "api_keys.json", "r", encoding="utf-8") as f:
            return _json.load(f).get("gemini_api_key")
    except Exception:
        return None

_KEY_CHARS = [c for c in (string.ascii_uppercase + string.digits)
              if c not in ('O', 'I', 'L', '0', '1')]

# ── AES-256-CBC ───────────────────────────────────────────────────────────────
_AES_SALT = b'JARVIS-DASHBOARD-v1'


def _derive_key(session_key: str) -> bytes:
    """SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed)."""
    return hashlib.sha256(session_key.encode('utf-8') + _AES_SALT).digest()


def _decrypt_cbc(aes_key: bytes, enc_b64: str) -> str:
    """Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_pad
    raw      = base64.b64decode(enc_b64)
    iv, ct   = raw[:16], raw[16:]
    dec      = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
    padded   = dec.update(ct) + dec.finalize()
    unpadder = sym_pad.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')


# ── CryptoJS (auto-download once, served locally) ─────────────────────────────
_CRYPTOJS_CDN  = ("https://cdnjs.cloudflare.com/ajax/libs/"
                  "crypto-js/4.2.0/crypto-js.min.js")
_CRYPTOJS_FILE = STATIC_DIR / "crypto-js.min.js"


def _ensure_network_access(port: int) -> None:
    """Cross-platform, best-effort: open port in the OS firewall for LAN access.

    Runs in a background thread — never blocks uvicorn startup.

    Windows : writes a .bat file, runs it elevated via Windows ShellExecuteW
              (native UAC dialog, guaranteed to appear). One-time setup.
    macOS   : osascript admin dialog if the Application Firewall is on.
    Linux   : pkexec GUI → sudo -n → prints manual command as fallback.
    """
    import sys, subprocess, os, tempfile, threading

    # ── Windows ──────────────────────────────────────────────────────────────
    if sys.platform == "win32":
        import ctypes, time

        port_rule = f"ALFRED Dashboard Port {port}"
        prog_rule  = "ALFRED Dashboard Python"
        py_exe     = sys.executable

        def _netsh_rule_exists(name: str) -> bool:
            """Return True if a Windows firewall rule with this name exists."""
            try:
                r = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                    capture_output=True, text=True, timeout=5,
                )
                return r.returncode == 0 and "No rules match" not in r.stdout
            except Exception:
                return False

        def _network_is_public() -> bool:
            """Return True if any active network profile is categorised as Public."""
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "(Get-NetConnectionProfile | "
                     "Where-Object {$_.NetworkCategory -eq 'Public'} | "
                     "Measure-Object).Count"],
                    capture_output=True, text=True, timeout=6,
                )
                return r.stdout.strip() not in ("", "0")
            except Exception:
                return False

        need_port    = not _netsh_rule_exists(port_rule)
        need_prog    = not _netsh_rule_exists(prog_rule)
        need_private = _network_is_public()

        if not need_port and not need_prog and not need_private:
            return  # already fully configured

        # Build a .bat file — netsh + powershell, runs fast when elevated
        bat_lines = ["@echo off"]
        if need_private:
            bat_lines.append(
                'powershell -NoProfile -NonInteractive -Command "'
                'Get-NetConnectionProfile | '
                "Where-Object {$_.NetworkCategory -eq 'Public'} | "
                'Set-NetConnectionProfile -NetworkCategory Private"'
            )
        if need_port:
            bat_lines.append(
                f'netsh advfirewall firewall add rule '
                f'name="{port_rule}" protocol=TCP dir=in '
                f'localport={port} action=allow'
            )
        if need_prog:
            bat_lines.append(
                f'netsh advfirewall firewall add rule '
                f'name="{prog_rule}" dir=in action=allow '
                f'program="{py_exe}" enable=yes'
            )

        bat_body = "\r\n".join(bat_lines) + "\r\n"
        fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="jarvis_fw_")
        try:
            os.write(fd, bat_body.encode("mbcs"))   # Windows cmd.exe expects ANSI
            os.close(fd)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            return

        # ── Try running directly (succeeds when already admin) ────────────────
        try:
            r = subprocess.run(
                [bat_path], capture_output=True, timeout=8, shell=True
            )
            if r.returncode == 0:
                print(f"[Dashboard] Firewall configured for port {port}.")
                try:
                    os.unlink(bat_path)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # ── ShellExecuteW: native UAC elevation (most reliable on Windows) ────
        # ShellExecuteW with verb "runas" always shows the UAC dialog regardless
        # of UAC level settings. Non-blocking — uvicorn is already running.
        print("[Dashboard] One-time network setup required.")
        print("[Dashboard] >>> A Windows security dialog will appear — click 'Yes' <<<")
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,       # hwnd  (no parent window)
                "runas",    # verb  (request elevation)
                bat_path,   # file  (our .bat)
                None,       # params
                None,       # working dir
                0,          # SW_HIDE (run without a visible cmd window)
            )
            if int(ret) > 32:
                # ShellExecuteW returns immediately; bat finishes in ~1 second.
                # Sleep briefly so the rules are in place before the first retry.
                time.sleep(2)
                print(f"[Dashboard] Network setup complete — port {port} is open.")
                print("[Dashboard] Refresh your phone browser to connect.")
            else:
                print("[Dashboard] Setup was not allowed.")
                print("[Dashboard] Phone connections may fail until ALFRED is run as Administrator.")
        except Exception as e:
            print(f"[Dashboard] Firewall setup error: {e}")
        finally:
            # Cleanup after the bat has had time to run
            def _cleanup(path: str) -> None:
                """Delete the temporary setup batch file after a short delay."""
                time.sleep(5)
                try:
                    os.unlink(path)
                except Exception:
                    pass
            threading.Thread(target=_cleanup, args=(bat_path,), daemon=True).start()
        return

    # ── macOS ─────────────────────────────────────────────────────────────────
    if sys.platform == "darwin":
        fw_ctl = "/usr/libexec/ApplicationFirewall/socketfilterfw"
        try:
            r = subprocess.run(
                [fw_ctl, "--getglobalstate"], capture_output=True, text=True, timeout=5,
            )
            if "disabled" in r.stdout.lower():
                return  # firewall off — nothing to do

            py = sys.executable
            listed = subprocess.run(
                [fw_ctl, "--listapps"], capture_output=True, text=True, timeout=5,
            )
            if py in listed.stdout:
                return  # already allowed

            print("[Dashboard] One-time network setup — enter your password in the macOS dialog.")
            subprocess.run(
                ["osascript", "-e",
                 f'do shell script "{fw_ctl} --add {py} && {fw_ctl} --unblockapp {py}"'
                 f' with administrator privileges'],
                timeout=60,
            )
        except Exception:
            pass  # macOS firewall is off by default — silent failure is fine
        return

    # ── Linux ─────────────────────────────────────────────────────────────────
    def _privileged(cmd: list[str]) -> bool:
        """Run a command via pkexec or sudo -n and return True if either succeeds."""
        for prefix in (["pkexec"], ["sudo", "-n"]):
            try:
                r = subprocess.run(prefix + cmd, capture_output=True, timeout=30)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    try:  # ufw
        r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
        if "active" in r.stdout.lower():
            if _privileged(["ufw", "allow", f"{port}/tcp"]):
                print(f"[Dashboard] ufw: port {port} allowed.")
            else:
                print(f"[Dashboard] Run manually:  sudo ufw allow {port}/tcp")
            return
    except FileNotFoundError:
        pass

    try:  # firewalld
        r = subprocess.run(
            ["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5,
        )
        if "running" in r.stdout.lower():
            ok = (_privileged(["firewall-cmd", "--add-port", f"{port}/tcp", "--permanent"])
                  and _privileged(["firewall-cmd", "--reload"]))
            if ok:
                print(f"[Dashboard] firewalld: port {port} allowed.")
            else:
                print(f"[Dashboard] Run manually:  sudo firewall-cmd --add-port={port}/tcp --permanent && sudo firewall-cmd --reload")
            return
    except FileNotFoundError:
        pass

    try:  # iptables (not persistent but works until reboot)
        r = subprocess.run(["iptables", "-L", "INPUT", "-n"], capture_output=True, timeout=5)
        if r.returncode == 0:
            if _privileged(["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"]):
                print(f"[Dashboard] iptables: port {port} opened.")
            else:
                print(f"[Dashboard] Run manually:  sudo iptables -A INPUT -p tcp --dport {port} -j ACCEPT")
    except FileNotFoundError:
        pass  # no iptables means firewall is probably off — nothing to do


def _ensure_crypto_js() -> None:
    """Download and cache CryptoJS locally once; the client falls back to the CDN on failure."""
    if _CRYPTOJS_FILE.exists():
        return
    try:
        import urllib.request
        print("[Dashboard] Downloading CryptoJS (one-time setup)…")
        urllib.request.urlretrieve(_CRYPTOJS_CDN, str(_CRYPTOJS_FILE))
        print("[Dashboard] CryptoJS cached — will serve locally from now on.")
    except Exception as e:
        print(f"[Dashboard] CryptoJS download failed: {e}")
        print(f"[Dashboard] Encryption will fall back to CDN load on client.")


_ensure_crypto_js()


# ── helpers ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Return the best LAN-facing IPv4 address, no internet required."""
    # Method 1: route trick (fast, works when internet is available)
    for probe in ("8.8.8.8", "1.1.1.1", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # Method 2: hostname resolution (works offline on most systems)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # Method 3: enumerate all interfaces (fully offline, no external deps)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def _ensure_certs() -> bool:
    """
    Make sure config/certs holds a TLS key pair, generating a self-signed one the
    first time the dashboard runs.

    The pair is deliberately NOT shipped in the repository. A private key that
    every user downloads is the same as having no private key at all: anyone can
    present a certificate that matches it. Generating locally gives each install
    its own key, costs about a second, and happens exactly once.

    Returns True when a usable pair exists afterwards; False leaves the caller on
    plain HTTP, which still works — the QR code simply encodes http:// instead.
    """
    certs = BASE_DIR / "config" / "certs"
    key_p = certs / "jarvis.key"
    crt_p = certs / "jarvis.crt"
    if key_p.exists() and crt_p.exists():
        return True

    try:
        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        print("[Dashboard] cryptography not installed — serving over plain HTTP.")
        print("[Dashboard] For HTTPS run:  pip install cryptography")
        return False

    try:
        certs.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        who = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "ALFRED Dashboard"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ALFRED"),
        ])

        # The SAN has to cover every address the phone might use: the LAN IP the
        # QR code encodes, plus localhost when testing on the machine itself.
        alt = [x509.DNSName("localhost"),
               x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
        try:
            lan = _local_ip()
            if not lan.startswith("127."):
                alt.append(x509.IPAddress(ipaddress.IPv4Address(lan)))
        except Exception:
            pass          # no LAN address resolvable — localhost entries still work

        # Timezone-aware UTC: datetime.utcnow() is deprecated from Python 3.12 on,
        # and the builder normalises aware values to UTC itself.
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(who)
            .issuer_name(who)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )

        key_p.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        try:
            import os as _os
            _os.chmod(key_p, 0o600)   # best effort — largely a no-op on Windows
        except Exception:
            pass

        print(f"[Dashboard] Generated a self-signed certificate for this machine: {certs}")
        return True
    except Exception as e:
        print(f"[Dashboard] Certificate generation failed ({e}) — serving over plain HTTP.")
        return False


def _read(name: str) -> str:
    """Return the text of a file from the dashboard static directory."""
    return (STATIC_DIR / name).read_text(encoding="utf-8")


# ── DashboardServer ───────────────────────────────────────────────────────────

class DashboardServer:
    """FastAPI remote dashboard: phone pairing, encrypted commands, files, audio and broadcasts."""

    def __init__(self):
        """Initialise auth, client, queue and callback state, load device sessions and build the app."""
        self._ip                          = _local_ip()
        self._tokens: set[str]            = set()
        self._token_keys: dict[str, str]  = {}   # auth_token → session_key
        self._aes_cache:  dict[str, bytes]= {}   # session_key → AES bytes
        self._clients: set[WebSocket]     = set()
        self._history: list[dict]         = []
        self._command_queue               = asyncio.Queue()
        self._wake_callback               = None
        self._connect_callback            = None
        self._clear_chat_callback          = None
        self._action_callback              = None
        self._pending_keys: dict[str, float] = {}
        self._device_sessions_file        = BASE_DIR / "config" / "device_sessions.json"
        self._device_sessions: dict[str, dict] = self._load_device_sessions()
        self._phone_audio_queue: asyncio.Queue    = asyncio.Queue(maxsize=200)
        self._audio_queue: asyncio.Queue          = asyncio.Queue(maxsize=200)
        self._background_tasks: dict[str, dict]   = {}
        self._uploads_dir                 = UPLOADS_DIR
        self._login_html                  = _read("login.html")
        self._app_html                    = _read("app.html")
        self.app                          = self._build_app()

    def _load_device_sessions(self) -> dict[str, dict]:
        """Load persisted device sessions and pre-derive their AES keys; return {} on failure."""
        try:
            if self._device_sessions_file.exists():
                data = json.loads(self._device_sessions_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Pre-derive AES keys for persisted sessions
                    for dev_tok, s_info in data.items():
                        skey = s_info.get("session_key")
                        if skey:
                            self._aes_key(skey)
                    return data
        except Exception as e:
            print(f"[Dashboard] Error loading device sessions: {e}")
        return {}

    def _save_device_sessions(self) -> None:
        """Write the device sessions to config/device_sessions.json."""
        try:
            self._device_sessions_file.parent.mkdir(parents=True, exist_ok=True)
            self._device_sessions_file.write_text(json.dumps(self._device_sessions, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Dashboard] Error saving device sessions: {e}")

    # ── one-time key management ───────────────────────────────────────────

    def new_key(self, expiry_secs: int = 600) -> str:
        """Create a six-character one-time pairing key valid for expiry_secs and return it.
        Expired pending keys are pruned first.
        """
        now = time.time()
        self._pending_keys = {k: v for k, v in self._pending_keys.items() if v > now}
        key = ''.join(secrets.choice(_KEY_CHARS) for _ in range(6))
        self._pending_keys[key] = now + expiry_secs
        return key

    @staticmethod
    def _ssl_enabled() -> bool:
        """Return True if both the TLS key and certificate exist in config/certs."""
        certs = BASE_DIR / "config" / "certs"
        return (certs / "jarvis.key").exists() and (certs / "jarvis.crt").exists()

    def get_url(self) -> str:
        """Return the dashboard URL, using https when TLS certificates are present."""
        proto = "https" if self._ssl_enabled() else "http"
        return f"{proto}://{self._ip}:{PORT}"

    def get_manual_url(self) -> str:
        """URL for manual browser entry. When HTTPS active, points to alias port (also HTTPS)."""
        proto = "https" if self._ssl_enabled() else "http"
        if self._ssl_enabled():
            return f"{proto}://{self._ip}:{PORT + 1}"
        return f"{proto}://{self._ip}:{PORT}"

    def _aes_key(self, session_key: str) -> bytes:
        """Return the cached AES key for a session key, deriving it on first use."""
        if session_key not in self._aes_cache:
            self._aes_cache[session_key] = _derive_key(session_key)
        return self._aes_cache[session_key]

    def _decrypt(self, token: str, enc_b64: str) -> str | None:
        """Decrypt a payload with the session key bound to this token; return None on failure."""
        sk = self._token_keys.get(token)
        if not sk:
            return None
        try:
            return _decrypt_cbc(self._aes_key(sk), enc_b64)
        except Exception:
            return None

    # ── callbacks ────────────────────────────────────────────────────────

    def set_wake_callback(self, fn) -> None:
        """Register the callback invoked when a remote command or wake request arrives."""
        self._wake_callback = fn

    def set_connect_callback(self, fn) -> None:
        """Register the callback invoked when a phone completes pairing."""
        self._connect_callback = fn

    def set_clear_chat_callback(self, fn) -> None:
        """Register the callback invoked when the dashboard clears the chat."""
        self._clear_chat_callback = fn

    def set_action_callback(self, fn) -> None:
        """Register the async callback that executes dashboard action buttons."""
        self._action_callback = fn

    # ── background tasks & broadcast ────────────────────────────────────

    async def update_background_task(
        self,
        task_id: str,
        task_type: str,
        progress: int,
        status: str,
        detail: str = "",
    ) -> None:
        """Record a background task's progress and broadcast it to connected clients."""
        payload = {
            "type": "background_task",
            "task_id": task_id,
            "task_type": task_type,
            "progress": progress,
            "status": status,
            "detail": detail,
            "updated_at": time.time(),
        }
        self._background_tasks[task_id] = payload
        await self.broadcast(payload)

    def get_background_tasks(self) -> dict:
        """Return a copy of the tracked background tasks keyed by task id."""
        return dict(self._background_tasks)

    async def broadcast(self, msg: dict) -> None:
        """Send a message to all WebSocket clients and record it in the capped history.
        A clear_chat message empties the history; clients that fail are dropped.
        """
        if msg.get("type") == "clear_chat":
            self._history.clear()
        else:
            if msg.get("type") == "background_task":
                tid = msg.get("task_id")
                if tid:
                    self._background_tasks[tid] = msg
            self._history.append(msg)
            if len(self._history) > 300:
                self._history = self._history[-300:]
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── FastAPI app ───────────────────────────────────────────────────────

    def _build_app(self) -> "FastAPI":
        """Build the FastAPI app with all HTTP and WebSocket routes and return it."""
        app = FastAPI(docs_url=None, redoc_url=None)

        def _auth(req: Request) -> bool:
            """Return True if the request carries a known bearer token or device token.
            A valid device token also registers the supplied bearer token.
            """
            tok = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if tok and tok in self._tokens:
                return True
            dev_tok = req.headers.get("x-device-token", "").strip()
            if dev_tok and dev_tok in self._device_sessions:
                skey = self._device_sessions[dev_tok]["session_key"]
                if tok:
                    self._tokens.add(tok)
                    self._token_keys[tok] = skey
                    self._aes_key(skey)
                return True
            return False

        # serve CryptoJS from local cache, fallback to CDN redirect
        @app.get("/static/crypto.js")
        async def serve_crypto():
            """Serve the cached CryptoJS file, or redirect to the CDN copy."""
            if _CRYPTOJS_FILE.exists():
                return FileResponse(str(_CRYPTOJS_FILE),
                                    media_type="application/javascript")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(_CRYPTOJS_CDN)

        @app.get("/login", response_class=HTMLResponse)
        async def login_page():
            """Serve the login page HTML."""
            return HTMLResponse(self._login_html)

        @app.get("/", response_class=HTMLResponse)
        async def index():
            """Serve the dashboard app HTML with the IP, port and theme colour filled in."""
            # Auth is handled client-side via sessionStorage bearer token.
            # Server-side header auth can't work here because browser navigations
            # don't send custom headers (location.href doesn't carry Authorization).
            try:
                raw_html = _read("app.html")
            except Exception:
                raw_html = self._app_html

            theme_color = "#8e9bff"
            try:
                cfg_path = BASE_DIR / "config" / "api_keys.json"
                if cfg_path.exists():
                    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                    theme_color = cfg.get("ui_color", theme_color)
            except Exception:
                pass

            html = (raw_html
                    .replace("__IP__", self._ip)
                    .replace("__PORT__", str(PORT))
                    .replace("__THEME_COLOR__", theme_color))
            return HTMLResponse(html)

        @app.post("/login")
        async def login(req: Request):
            """Exchange a valid one-time PIN for a bearer token and a persistent device token.
            Returns 401 for an invalid or expired key.
            """
            body    = await req.json()
            entered = str(body.get("pin", "")).strip().upper()
            now     = time.time()
            if entered in self._pending_keys and self._pending_keys[entered] > now:
                del self._pending_keys[entered]          # one-time use
                tok = secrets.token_urlsafe(32)
                dev_tok = secrets.token_urlsafe(32)
                self._tokens.add(tok)
                self._token_keys[tok] = entered
                self._aes_key(entered)                   # pre-derive & cache
                self._device_sessions[dev_tok] = {"session_key": entered}
                self._save_device_sessions()
                if self._connect_callback:
                    self._connect_callback()
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Remote connection established."}
                ))
                # Bearer token and device token in response body for persistent pairing
                return JSONResponse({"ok": True, "token": tok, "device_token": dev_tok, "key": entered})
            return JSONResponse({"ok": False, "error": "Invalid or expired key"},
                                status_code=401)

        @app.get("/auto-login")
        async def auto_login(key: str = ""):
            """QR code target — validates one-time key, creates session, redirects phone."""
            now = time.time()
            if not key or key not in self._pending_keys or self._pending_keys[key] <= now:
                return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
  h2{color:#f87171;margin-bottom:12px}p{color:#5e6a7e;font-size:14px}
</style></head>
<body><div><h2>Link Expired</h2>
<p>Press <strong style="color:#dde3ed">Remote Control</strong> in ALFRED to get a new QR code.</p>
</div></body></html>""")

            del self._pending_keys[key]
            tok     = secrets.token_urlsafe(32)
            dev_tok = secrets.token_urlsafe(32)
            self._tokens.add(tok)
            self._token_keys[tok] = key
            self._aes_key(key)
            self._device_sessions[dev_tok] = {"session_key": key}
            self._save_device_sessions()

            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Remote connection established via QR code."}
            ))

            return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}}
  p{{color:#5e6a7e;font-size:14px}}
</style></head>
<body>
<script>
  sessionStorage.setItem('jarvis_token','{tok}');
  sessionStorage.setItem('jarvis_key','{key}');
  localStorage.setItem('jarvis_token','{tok}');
  localStorage.setItem('jarvis_key','{key}');
  localStorage.setItem('jarvis_device_token','{dev_tok}');
  setTimeout(function(){{location.replace('/')}},400);
</script>
<p>Connecting to ALFRED…</p>
</body></html>""")

        @app.post("/api/device-login")
        async def device_login_ep(req: Request):
            """Return a fresh auth token for a previously paired device token."""
            try:
                body = await req.json()
            except Exception:
                return JSONResponse({"ok": False}, status_code=400)
            dev_tok = (body.get("device_token") or "").strip()
            if not dev_tok or dev_tok not in self._device_sessions:
                return JSONResponse({"ok": False}, status_code=401)
            session_key = self._device_sessions[dev_tok]["session_key"]
            tok = secrets.token_urlsafe(32)
            self._tokens.add(tok)
            self._token_keys[tok] = session_key
            self._aes_key(session_key)
            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Known device reconnected automatically."}
            ))
            return JSONResponse({"ok": True, "token": tok, "key": session_key, "device_token": dev_tok})

        @app.post("/api/revoke-devices")
        async def revoke_devices(req: Request):
            """Invalidate all persistent device tokens (admin action)."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            count = len(self._device_sessions)
            self._device_sessions.clear()
            self._save_device_sessions()
            return JSONResponse({"ok": True, "revoked": count})

        @app.post("/api/action")
        async def action_ep(req: Request):
            """Execute tactical actions directly from mobile action buttons."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            try:
                body = await req.json()
            except Exception:
                return JSONResponse({"error": "Invalid JSON"}, status_code=400)

            action = (body.get("action") or "").strip()
            params = body.get("params") or {}
            if not action:
                return JSONResponse({"error": "Missing action"}, status_code=400)

            if self._action_callback:
                try:
                    res = await self._action_callback(action, params)
                    return JSONResponse(res if isinstance(res, dict) else {"ok": True, "result": res})
                except Exception as e:
                    return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
            return JSONResponse({"ok": False, "error": "No action handler configured"}, status_code=503)

        @app.get("/api/status")
        async def status_ep(req: Request):
            """Return current deck state (audio core state, mute status, etc.)."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            if self._action_callback:
                try:
                    res = await self._action_callback("get_deck_state", {})
                    return JSONResponse(res if isinstance(res, dict) else {"ok": True, "state": res})
                except Exception as e:
                    return JSONResponse({"ok": False, "error": str(e)})
            return JSONResponse({"ok": True, "audio_core": {}, "muted": False})

        @app.post("/api/command")
        async def command(req: Request):
            """Accept an authorised (optionally encrypted) text command and queue it.
            Invokes the wake callback when a command is queued.
            """
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            body  = await req.json()
            token = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            enc   = body.get("enc", "")
            if enc:
                text = self._decrypt(token, enc)
                if text is None:
                    return JSONResponse({"error": "Decryption failed"}, status_code=400)
            else:
                text = (body.get("text") or "").strip()
            if text:
                await self._command_queue.put(text)
                if self._wake_callback:
                    self._wake_callback()
            return JSONResponse({"ok": True})

        @app.post("/api/wake")
        async def wake_ep(req: Request):
            """Trigger the wake callback for an authorised request."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            if self._wake_callback:
                self._wake_callback()
            return JSONResponse({"ok": True})

        @app.post("/api/clear-chat")
        async def clear_chat_ep(req: Request):
            """Clear the chat history, broadcast the clear and invoke the clear-chat callback."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            self._history.clear()
            await self.broadcast({"type": "clear_chat"})
            if self._clear_chat_callback:
                try:
                    self._clear_chat_callback()
                except Exception as e:
                    print(f"[Dashboard] clear_chat_callback error: {e}")
            return JSONResponse({"ok": True})

        def _resolve_ws_auth(token: str = "", device_token: str = "") -> str | None:
            """Resolve a bearer or device token to a valid bearer token, or None if unauthorised.
            A known device token mints and registers a bearer token when none is given.
            """
            tok = (token or "").strip()
            if tok and tok in self._tokens:
                return tok
            dtok = (device_token or "").strip()
            if dtok and dtok in self._device_sessions:
                skey = self._device_sessions[dtok]["session_key"]
                new_tok = tok if tok else secrets.token_urlsafe(32)
                self._tokens.add(new_tok)
                self._token_keys[new_tok] = skey
                self._aes_key(skey)
                return new_tok
            return None

        # ── Phone mic real-time audio → Gemini Live ──────────────────────────

        @app.websocket("/ws/phone-audio")
        async def phone_audio_ws(websocket: WebSocket, token: str = "", device_token: str = ""):
            """Receive phone mic PCM over a WebSocket and queue it for the Live session."""
            tok = _resolve_ws_auth(token, device_token)
            if not tok:
                await websocket.close(code=4001)
                return
            await websocket.accept()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Phone microphone live."}
            ))
            try:
                while True:
                    data = await websocket.receive_bytes()
                    try:
                        self._phone_audio_queue.put_nowait(
                            {"data": data, "mime_type": "audio/pcm"}
                        )
                    except asyncio.QueueFull:
                        pass  # drop frame rather than block
            except WebSocketDisconnect:
                pass
            finally:
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Phone microphone stopped."}
                ))

        # ── File sharing ──────────────────────────────────────────────────────

        def _safe_filename(raw: str) -> str:
            """Return a filesystem-safe base name for an uploaded file, defaulting to upload."""
            name = Path(raw).name                          # strip path components
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(". ")
            return name or "upload"

        if _UPLOAD_OK:
            @app.post("/api/upload")
            async def upload_file(req: Request, file: UploadFile = FastAPIFile(...)):
                """Save an authorised upload to the uploads folder under a unique name.
                Rejects files over MAX_UPLOAD_MB and broadcasts a file_received event on success.
                """
                if not _auth(req):
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)

                safe = _safe_filename(file.filename or "upload")
                dest = self._uploads_dir / safe
                stem, suffix = Path(safe).stem, Path(safe).suffix
                counter = 1
                while dest.exists():
                    dest = self._uploads_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                size = 0
                max_bytes = MAX_UPLOAD_MB * 1024 * 1024
                try:
                    with open(dest, "wb") as fout:
                        while True:
                            chunk = await file.read(65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > max_bytes:
                                fout.close()
                                dest.unlink(missing_ok=True)
                                return JSONResponse(
                                    {"error": f"File too large (max {MAX_UPLOAD_MB} MB)"},
                                    status_code=413,
                                )
                            fout.write(chunk)
                except Exception as exc:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return JSONResponse({"error": str(exc)}, status_code=500)

                asyncio.create_task(self.broadcast({
                    "type": "file_received",
                    "name": dest.name,
                    "size": size,
                    "saved_to": str(self._uploads_dir),
                }))
                return JSONResponse({"ok": True, "name": dest.name, "size": size})
        else:
            @app.post("/api/upload")
            async def upload_unavailable(req: Request):
                """Report that uploads need python-multipart installed (HTTP 503)."""
                return JSONResponse(
                    {"error": "File uploads require: pip install python-multipart"},
                    status_code=503,
                )

        @app.get("/api/files")
        async def list_files(req: Request):
            """Return the uploaded files, newest first, with their sizes."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            files = []
            try:
                for f in sorted(
                    (p for p in self._uploads_dir.iterdir() if p.is_file()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                ):
                    files.append({"name": f.name, "size": f.stat().st_size})
            except Exception:
                pass
            return JSONResponse({"files": files})

        @app.get("/uploads/{filename}")
        async def download_file(filename: str, token: str = "", device_token: str = ""):
            """Serve an uploaded file to a client authorised by query-string token."""
            # Auth via query param — browser <a download> can't send custom headers
            tok = _resolve_ws_auth(token, device_token)
            if not tok:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            safe = re.sub(r'[/\\]', '', filename)
            path = self._uploads_dir / safe
            if not path.exists() or not path.is_file():
                return JSONResponse({"error": "Not found"}, status_code=404)
            return FileResponse(str(path), filename=safe)

        @app.get("/api/background_tasks")
        async def background_tasks_ep(req: Request):
            """Return the list of tracked background tasks."""
            return JSONResponse({"ok": True, "tasks": list(self._background_tasks.values())})

        @app.websocket("/ws")
        async def ws_ep(websocket: WebSocket, token: str = "", device_token: str = ""):
            """Main dashboard WebSocket: sends history, then handles ping, command and action messages."""
            tok = _resolve_ws_auth(token, device_token)
            if not tok:
                try:
                    await websocket.close(code=4001)
                except Exception:
                    pass
                return
            await websocket.accept()
            self._clients.add(websocket)

            # Send historical buffer immediately in batch
            history_slice = list(self._history[-UPLINK_HISTORY_N:])
            try:
                await websocket.send_json({"type": "history", "items": history_slice})
            except (WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError):
                self._clients.discard(websocket)
                return
            except Exception:
                pass

            try:
                while True:
                    data = await websocket.receive_json()
                    mtype = data.get("type")
                    if mtype == "ping":
                        await websocket.send_json({"type": "pong", "ts": time.time()})
                    elif mtype == "command":
                        enc = data.get("enc", "")
                        t   = self._decrypt(tok, enc) if enc else (data.get("text") or "").strip()
                        if t:
                            await self._command_queue.put(t)
                            if self._wake_callback:
                                self._wake_callback()
                    elif mtype == "action":
                        act = data.get("action")
                        prm = data.get("params") or {}
                        if act and self._action_callback:
                            try:
                                a_res = await self._action_callback(act, prm)
                                await websocket.send_json({"type": "action_result", "action": act, "data": a_res})
                            except Exception as ex:
                                await websocket.send_json({"type": "action_result", "action": act, "error": str(ex)})
            except (WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError):
                pass
            except Exception as e:
                pass
            finally:
                self._clients.discard(websocket)

        # ── Bidirectional audio WebSocket ─────────────────────────────────────
        @app.websocket("/ws/audio")
        async def audio_ws(websocket: WebSocket, token: str = "", device_token: str = ""):
            """WebSocket endpoint for bidirectional audio streaming.

            Receives: PCM 16kHz audio chunks from browser mic
            Sends:    PCM 16kHz audio chunks of ALFRED's synthesized audio
            """
            tok = _resolve_ws_auth(token, device_token)
            if not tok:
                try:
                    await websocket.close(code=4001)
                except Exception:
                    pass
                return
            await websocket.accept()

            # Task to handle incoming audio from browser to ALFRED mic
            async def handle_incoming_audio():
                """Read browser mic PCM from the WebSocket and queue it for the assistant."""
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        try:
                            self._phone_audio_queue.put_nowait(
                                {"data": data, "mime_type": "audio/pcm"}
                            )
                        except asyncio.QueueFull:
                            pass
                        except Exception:
                            pass
                except (WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError):
                    pass
                except Exception:
                    pass

            # Task to handle outgoing audio from ALFRED to browser speakers
            async def handle_outgoing_audio():
                """Send queued assistant audio chunks to the browser over the WebSocket."""
                try:
                    while True:
                        try:
                            audio_data = await asyncio.wait_for(
                                self._audio_queue.get(),
                                timeout=0.1
                            )
                            await websocket.send_bytes(audio_data["data"])
                        except asyncio.TimeoutError:
                            continue
                        except (WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError):
                            break
                        except Exception:
                            pass
                except (WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError):
                    pass
                except Exception:
                    pass

            try:
                await asyncio.gather(
                    handle_incoming_audio(),
                    handle_outgoing_audio()
                )
            except Exception:
                pass
            finally:
                # Clean up any remaining tasks
                pass

        return app

    # ── serve ─────────────────────────────────────────────────────────────

    async def _serve_alias(self) -> None:
        """Second HTTPS server on PORT+1 sharing the same app and in-memory state.
        Chrome HTTPS-upgrades any bare IP:PORT the user types, so this port also needs TLS.
        User types IP:8001 → Chrome tries https → self-signed cert warning → accept once → done."""
        ssl_key  = BASE_DIR / "config" / "certs" / "jarvis.key"
        ssl_cert = BASE_DIR / "config" / "certs" / "jarvis.crt"
        asyncio.get_event_loop().run_in_executor(None, _ensure_network_access, PORT + 1)
        cfg = uvicorn.Config(
            self.app, host="0.0.0.0", port=PORT + 1, log_level="warning",
            ssl_keyfile=str(ssl_key), ssl_certfile=str(ssl_cert),
        )
        print(f"[Dashboard] Manual entry:  {self._ip}:{PORT + 1}  (type in browser, accept cert once)")
        await uvicorn.Server(cfg).serve()

    async def serve(self) -> None:
        """Start the dashboard with uvicorn, over TLS when certificates are available.
        Opens firewall access in the background and starts the alias server on PORT+1 for TLS.
        """
        if not _DEPS_OK:
            print("[Dashboard] fastapi/uvicorn not installed — dashboard disabled.")
            print("[Dashboard] Run:  pip install fastapi 'uvicorn[standard]' cryptography")
            return

        # Firewall setup runs in a thread — uvicorn starts immediately,
        # no waiting for UAC dialogs or subprocess timeouts.
        asyncio.get_event_loop().run_in_executor(None, _ensure_network_access, PORT)

        # Generate the TLS pair on first run so no private key ships in the repo.
        _ensure_certs()

        use_ssl  = self._ssl_enabled()
        ssl_key  = BASE_DIR / "config" / "certs" / "jarvis.key"
        ssl_cert = BASE_DIR / "config" / "certs" / "jarvis.crt"

        if use_ssl:
            asyncio.create_task(self._serve_alias())

        cfg = uvicorn.Config(
            self.app, host="0.0.0.0", port=PORT, log_level="warning",
            **({"ssl_keyfile": str(ssl_key), "ssl_certfile": str(ssl_cert)} if use_ssl else {}),
        )

        proto = "https" if use_ssl else "http"
        print(f"[Dashboard] {proto}://{self._ip}:{PORT}")
        print("[Dashboard] Press 'Remote Control' in ALFRED UI to get the QR code.")
        await uvicorn.Server(cfg).serve()
