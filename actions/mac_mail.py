"""Mail.app: unread summary, drafts, sending (with confirmation)."""
from core.mac import require_mac

require_mac()

from core.mac import apps                                   # noqa: E402
from core.mac.tooling import B, N, S, needs_confirm, tool   # noqa: E402


@tool
def mac_mail(p, **_):
    a = str(p.get("action", "")).lower().strip()
    if a == "unread":
        return apps.mail_unread(int(p.get("limit") or 8))
    if a in ("compose", "send"):
        to = str(p.get("to") or "").strip()
        subject = str(p.get("subject") or "").strip()
        body = str(p.get("body") or "").strip()
        if a == "send":
            if not to:
                return "Who should it go to?"
            if not p.get("confirm"):
                return needs_confirm(f"Email {to}, subject “{subject}”: “{body[:300]}”?")
            return apps.mail_compose(to, subject, body, send=True)
        return apps.mail_compose(to, subject, body, send=False)
    return "Unknown action. Use unread, compose or send."


TOOL = {
    "name": "mac_mail",
    "description": ("Apple Mail: how many unread and who they're from, open a pre-filled draft, "
                    "or send an email (preview + confirm first)."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["unread", "compose", "send"]),
        "to": S("Contact name or email address."),
        "subject": S("Subject line."),
        "body": S("Message body."),
        "limit": N("unread: how many to list (default 8)."),
        "confirm": B("send: only true after the user approved it."),
    }, "required": ["action"]},
    "handler": mac_mail,
}
