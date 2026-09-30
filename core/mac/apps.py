"""Apple apps: Contacts, Messages, FaceTime, Mail, Notes, Music/Spotify, Maps, Shortcuts."""
from __future__ import annotations

import html
import os
import re
import subprocess
import tempfile
import threading
from urllib.parse import quote

from core.mac.osa import OSAError, applescript, is_running, q, run

# ── Contacts (Contacts.framework) ────────────────────────────────────────────

def _contacts_store():
    import Contacts
    s = Contacts.CNContactStore.alloc().init()
    status = Contacts.CNContactStore.authorizationStatusForEntityType_(0)
    if status in (1, 2):
        raise OSAError("ALFRED isn't allowed to read Contacts. Turn it on in System Settings → "
                       "Privacy & Security → Contacts → ALFRED.")
    if status == 0:
        done, box = threading.Event(), {}

        def handler(granted, error):
            box["ok"] = bool(granted)
            done.set()

        s.requestAccessForEntityType_completionHandler_(0, handler)
        done.wait(120)
        if not box.get("ok"):
            raise OSAError("Access to Contacts was not granted.")
    return s


def find_contacts(name: str, limit: int = 5) -> list[dict]:
    import Contacts
    s = _contacts_store()
    keys = [Contacts.CNContactGivenNameKey, Contacts.CNContactFamilyNameKey, Contacts.CNContactNicknameKey,
            Contacts.CNContactOrganizationNameKey, Contacts.CNContactPhoneNumbersKey,
            Contacts.CNContactEmailAddressesKey]
    pred = Contacts.CNContact.predicateForContactsMatchingName_(name)
    found, _err = s.unifiedContactsMatchingPredicate_keysToFetch_error_(pred, keys, None)
    out = []
    for c in (found or [])[:limit]:
        label = Contacts.CNLabeledValue.localizedStringForLabel_
        out.append({
            "name": " ".join(x for x in [c.givenName(), c.familyName()] if x) or c.organizationName(),
            "phones": [{"label": label(p.label()) if p.label() else "", "number": p.value().stringValue()}
                       for p in c.phoneNumbers()],
            "emails": [{"label": label(e.label()) if e.label() else "", "address": str(e.value())}
                       for e in c.emailAddresses()],
        })
    return out


def _looks_like_handle(s: str) -> bool:
    return "@" in s or bool(re.fullmatch(r"[+\d][\d\s\-().]{5,}", s.strip()))


def resolve_handle(recipient: str, want: str = "phone") -> tuple[str, str]:
    """Name / number / email → (handle, display name)."""
    r = recipient.strip()
    if _looks_like_handle(r):
        return re.sub(r"[\s\-().]", "", r) if "@" not in r else r, r
    matches = find_contacts(r)
    if not matches:
        raise OSAError(f"I couldn't find {recipient} in Contacts.")
    c = matches[0]
    phones = sorted(c["phones"], key=lambda p: ("mobile" not in p["label"].lower() and "iphone" not in p["label"].lower()))
    if want == "email" and c["emails"]:
        return c["emails"][0]["address"], c["name"]
    if phones:
        return re.sub(r"[\s\-().]", "", phones[0]["number"]), c["name"]
    if c["emails"]:
        return c["emails"][0]["address"], c["name"]
    raise OSAError(f"{c['name']} has no phone number or email in Contacts.")


# ── Messages / FaceTime ──────────────────────────────────────────────────────

def send_message(recipient: str, text: str, service: str = "iMessage") -> str:
    handle, who = resolve_handle(recipient)
    svc = "SMS" if service.lower() in ("sms", "text") else "iMessage"
    applescript(f'tell application "Messages"\n'
                f'  set acct to 1st account whose service type = {svc}\n'
                f'  send {q(text)} to participant {q(handle)} of acct\n'
                f'end tell', app="Messages", timeout=20)
    return f"Sent to {who} via {svc}."


def call(recipient: str, kind: str = "audio") -> str:
    handle, who = resolve_handle(recipient)
    scheme = {"video": "facetime", "audio": "facetime-audio", "phone": "tel"}.get(kind, "facetime-audio")
    subprocess.run(["open", f"{scheme}://{quote(handle)}"])
    return f"Calling {who} ({'FaceTime video' if kind == 'video' else 'FaceTime audio' if kind == 'audio' else 'phone via iPhone'}). Confirm on screen if macOS asks."


# ── Mail ─────────────────────────────────────────────────────────────────────

def mail_unread(limit: int = 8) -> dict:
    script = f'''tell application "Mail"
  set n to unread count of inbox
  set out to ""
  set msgs to (messages of inbox whose read status is false)
  set k to 0
  repeat with m in msgs
    set k to k + 1
    if k > {int(limit)} then exit repeat
    set out to out & (sender of m) & " ||| " & (subject of m) & " ||| " & ((date received of m) as string) & linefeed
  end repeat
  return (n as string) & linefeed & out
end tell'''
    out = applescript(script, app="Mail", timeout=30).splitlines()
    items = []
    for line in out[1:]:
        parts = line.split(" ||| ")
        if len(parts) == 3:
            items.append({"from": parts[0], "subject": parts[1], "received": parts[2]})
    return {"unread": int(out[0]) if out and out[0].isdigit() else None, "latest": items}


def mail_compose(to: str, subject: str, body: str, send: bool = False) -> str:
    handle, who = resolve_handle(to, want="email") if to else ("", "")
    if to and "@" not in handle:
        raise OSAError(f"I don't have an email address for {to}.")
    script = f'''tell application "Mail"
  set m to make new outgoing message with properties {{subject:{q(subject)}, content:{q(body)}, visible:{"false" if send else "true"}}}
  {f"tell m to make new to recipient at end of to recipients with properties {{address:{q(handle)}}}" if handle else ""}
  {"send m" if send else "activate"}
end tell'''
    applescript(script, app="Mail", timeout=30)
    return f"Email to {who} sent." if send else f"Draft to {who or 'nobody yet'} is open in Mail."


# ── Notes ────────────────────────────────────────────────────────────────────

def _note_html(title: str, body: str) -> str:
    paras = "".join(f"<div>{html.escape(line) or '<br>'}</div>" for line in body.splitlines())
    return f"<h1>{html.escape(title)}</h1>{paras}"


def note_create(title: str, body: str = "", folder: str | None = None) -> str:
    where = f" at folder {q(folder)}" if folder else ""
    applescript(f'tell application "Notes" to make new note{where} with properties {{body:{q(_note_html(title, body))}}}',
                app="Notes", timeout=20)
    return f"Created note “{title}”."


def note_search(query: str, limit: int = 10) -> list[dict]:
    script = f'''tell application "Notes"
  set out to ""
  set k to 0
  repeat with n in (notes whose name contains {q(query)})
    set k to k + 1
    if k > {int(limit)} then exit repeat
    set out to out & (id of n) & " ||| " & (name of n) & " ||| " & ((modification date of n) as string) & linefeed
  end repeat
  return out
end tell'''
    rows = []
    for line in applescript(script, app="Notes", timeout=30).splitlines():
        parts = line.split(" ||| ")
        if len(parts) == 3:
            rows.append({"id": parts[0], "title": parts[1], "modified": parts[2]})
    return rows


def note_read(note_id: str, max_chars: int = 4000) -> str:
    return applescript(f'tell application "Notes" to get plaintext of note id {q(note_id)}',
                       app="Notes", timeout=20)[:max_chars]


def note_append(note_id: str, text: str) -> str:
    paras = "".join(f"<div>{html.escape(line) or '<br>'}</div>" for line in text.splitlines())
    applescript(f'tell application "Notes"\n  set n to note id {q(note_id)}\n'
                f'  set body of n to (body of n) & {q(paras)}\nend tell', app="Notes", timeout=20)
    return "Added to the note."


# ── Music / Spotify ──────────────────────────────────────────────────────────

def _player() -> str | None:
    """Whichever of Spotify / Music is running (Spotify preferred when both are playing)."""
    for app, bid in (("Spotify", "com.spotify.client"), ("Music", "com.apple.Music")):
        if is_running(bid):
            try:
                if applescript(f'tell application "{app}" to get player state as string', app=app, timeout=5) == "playing":
                    return app
            except OSAError:
                pass
    if is_running("com.spotify.client"):
        return "Spotify"
    if is_running("com.apple.Music"):
        return "Music"
    return None


def music_control(action: str, app: str | None = None) -> str:
    app = {"spotify": "Spotify", "music": "Music", "apple music": "Music"}.get((app or "").lower()) or _player()
    if app is None:
        from core.mac.system import media_key
        key = {"play": "play_pause", "pause": "play_pause", "toggle": "play_pause",
               "next": "next", "previous": "previous"}.get(action, "play_pause")
        return media_key(key)
    verb = {"play": "play", "pause": "pause", "toggle": "playpause", "next": "next track",
            "previous": "previous track"}[action]
    applescript(f'tell application "{app}" to {verb}', app=app)
    return f"{app}: {action}."


def now_playing() -> dict:
    app = _player()
    if app is None:
        return {"playing": None}
    out = applescript(f'tell application "{app}"\n  if player state is stopped then return "stopped"\n'
                      f'  return (player state as string) & " ||| " & (name of current track) & " ||| " & '
                      f'(artist of current track) & " ||| " & (album of current track)\nend tell', app=app)
    if out == "stopped":
        return {"app": app, "state": "stopped"}
    state, name, artist, album = (out.split(" ||| ") + ["", "", "", ""])[:4]
    return {"app": app, "state": state, "track": name, "artist": artist, "album": album}


def music_play(query: str) -> str:
    """Play from the Apple Music library: playlist by name first, then track/artist/album search."""
    script = f'''tell application "Music"
  set q to {q(query)}
  try
    set p to first playlist whose name is q
    play p
    return "playlist: " & (name of p)
  end try
  set hits to (search library playlist 1 for q)
  if (count of hits) is 0 then return "none"
  play item 1 of hits
  return "track: " & (name of item 1 of hits) & " by " & (artist of item 1 of hits)
end tell'''
    out = applescript(script, app="Music", timeout=30)
    if out == "none":
        raise OSAError(f"Nothing called “{query}” is in the Music library.")
    return f"Playing {out}."


def spotify_play_uri(uri: str) -> str:
    applescript(f'tell application "Spotify" to play track {q(uri)}', app="Spotify")
    return "Playing on Spotify."


# ── Maps ─────────────────────────────────────────────────────────────────────

def maps(destination: str, origin: str = "", mode: str = "driving") -> str:
    flag = {"driving": "d", "walking": "w", "transit": "r", "cycling": "c"}.get(mode, "d")
    url = f"maps://?daddr={quote(destination)}&dirflg={flag}" + (f"&saddr={quote(origin)}" if origin else "")
    subprocess.run(["open", url])
    return f"Directions to {destination} are open in Maps."


def maps_search(query: str) -> str:
    subprocess.run(["open", f"maps://?q={quote(query)}"])
    return f"Showing {query} in Maps."


# ── Shortcuts ────────────────────────────────────────────────────────────────

def shortcuts_list() -> list[str]:
    return [s for s in run(["shortcuts", "list"]).splitlines() if s.strip()]


def shortcut_run(name: str, text_input: str = "") -> str:
    names = shortcuts_list()
    match = next((n for n in names if n.lower() == name.lower()), None) or \
        next((n for n in names if name.lower() in n.lower()), None)
    if match is None:
        raise OSAError(f"There's no shortcut called “{name}”. Available: {', '.join(names[:20]) or 'none'}.")
    args = ["shortcuts", "run", match]
    tmp_in = None
    if text_input:
        tmp_in = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        tmp_in.write(text_input)
        tmp_in.close()
        args += ["--input-path", tmp_in.name]
    out_path = tempfile.mktemp(suffix=".txt")
    args += ["--output-path", out_path, "--output-type", "public.plain-text"]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=120)
        result = ""
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8", errors="replace") as f:
                result = f.read().strip()
        if p.returncode != 0 and not result:
            raise OSAError(p.stderr.strip() or f"Shortcut “{match}” failed.")
        return f"Ran “{match}”." + (f" Output: {result[:1500]}" if result else "")
    finally:
        for f in (out_path, tmp_in.name if tmp_in else None):
            if f and os.path.exists(f):
                os.unlink(f)
