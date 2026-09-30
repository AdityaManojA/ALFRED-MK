"""iMessage / SMS through Messages.app, and FaceTime / iPhone calls."""
from core.mac import require_mac

require_mac()

from core.mac import apps                                   # noqa: E402
from core.mac.tooling import B, S, needs_confirm, tool      # noqa: E402


@tool
def mac_messages(p, **_):
    a = str(p.get("action", "")).lower().strip()
    to = str(p.get("to") or "").strip()
    if not to:
        return "Who to?"
    if a == "send":
        text = str(p.get("text") or "").strip()
        if not text:
            return "What should the message say?"
        handle, who = apps.resolve_handle(to)
        if not p.get("confirm"):
            return needs_confirm(f"Send to {who} ({handle}) via {p.get('service') or 'iMessage'}: “{text}”?")
        return apps.send_message(handle, text, str(p.get("service") or "iMessage"))
    if a == "call":
        return apps.call(to, str(p.get("kind") or "audio"))
    return "Unknown action. Use send or call."


TOOL = {
    "name": "mac_messages",
    "description": ("Send an iMessage/SMS from Messages.app to a contact name, number or email (preview + confirm first), "
                    "or start a FaceTime audio/video call or an iPhone call."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["send", "call"]),
        "to": S("Contact name as in Contacts, or a phone number / email."),
        "text": S("send: the message."),
        "service": S("send: iMessage (default) or SMS."),
        "kind": S("call: audio (FaceTime audio, default), video, or phone (via iPhone)."),
        "confirm": B("send: only true after the user approved the exact message."),
    }, "required": ["action", "to"]},
    "handler": mac_messages,
}
