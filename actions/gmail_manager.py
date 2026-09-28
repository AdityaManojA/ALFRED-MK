"""
Gmail Manager Action for ALFRED Mark-LIV.
Provides full Gmail connectivity:
  - Reading unread / recent emails with intelligent body extraction
  - Executive summarization of inboxes and threads
  - Searching emails by sender, subject, or query
  - Sending emails with recipient & content validation
  - Auto-discovered by core/action_loader.py as 'gmail_manager'
"""
from __future__ import annotations

import email
import imaplib
import json
import os
import smtplib
from datetime import datetime
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def _load_gmail_creds() -> tuple[str, str]:
    """Retrieve user email and app password from config or environment."""
    email_addr = os.environ.get("GMAIL_USER", "").strip()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not email_addr or not app_pw:
        if _CONFIG_PATH.exists():
            try:
                data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                email_addr = email_addr or data.get("gmail_user", "").strip()
                app_pw = app_pw or data.get("gmail_app_password", "").strip()
            except Exception:
                pass
    # Google App Passwords often have 4-character grouping spaces ('abcd efgh ijkl mnop')
    clean_pw = app_pw.replace(" ", "").strip()
    return email_addr, clean_pw


def _clean_header_str(val: Any) -> str:
    """Safely decode RFC 2047 email headers."""
    if not val:
        return ""
    try:
        decoded_parts = decode_header(val)
        out = []
        for text, encoding in decoded_parts:
            if isinstance(text, bytes):
                encoding = encoding or "utf-8"
                try:
                    out.append(text.decode(encoding, errors="replace"))
                except Exception:
                    out.append(text.decode("latin1", errors="replace"))
            else:
                out.append(str(text))
        return "".join(out).strip()
    except Exception:
        return str(val).strip()


def _extract_body_snippet(msg: email.message.Message, max_chars: int = 240) -> str:
    """Extract plain text body snippet from an email message."""
    body_text = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in cdispo:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")
    except Exception:
        body_text = ""

    # Collapse whitespace and return snippet
    cleaned = " ".join(body_text.split()).strip()
    return (cleaned[:max_chars] + "…") if len(cleaned) > max_chars else cleaned


def fetch_unread_emails(max_count: int = 5, query: Optional[str] = None) -> List[Dict[str, str]]:
    """Connect to Gmail IMAP and fetch unread email summaries."""
    user, pw = _load_gmail_creds()
    if not user or not pw:
        return []

    results = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(user, pw)
        mail.select("INBOX", readonly=True)

        search_criteria = "UNSEEN"
        if query:
            search_criteria = f'(UNSEEN {query})'

        status, response = mail.search(None, search_criteria)
        if status != "OK" or not response[0]:
            return []

        msg_ids = response[0].split()
        # Take the most recent unread emails
        selected_ids = msg_ids[-max_count:]
        selected_ids.reverse()

        for mid in selected_ids:
            status, data = mail.fetch(mid, "(RFC822)")
            if status != "OK" or not data:
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = _clean_header_str(msg.get("From", "Unknown"))
            subject = _clean_header_str(msg.get("Subject", "(No Subject)"))
            date_str = _clean_header_str(msg.get("Date", ""))
            snippet = _extract_body_snippet(msg)

            # Extract clean sender display name if available
            sender_name = sender.split("<")[0].strip().strip('"') if "<" in sender else sender

            results.append({
                "sender": sender_name or sender,
                "from_full": sender,
                "subject": subject,
                "date": date_str,
                "snippet": snippet or "No text preview available."
            })
    except Exception as e:
        print(f"[GmailManager] IMAP error: {e}")
        return []
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    return results


def send_gmail_message(to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    """Send an email using Gmail SMTP SSL."""
    user, pw = _load_gmail_creds()
    if not user or not pw:
        return False, "Gmail credentials are not configured. Please set gmail_user and gmail_app_password in settings."

    if not to_addr or "@" not in to_addr:
        return False, f"Invalid recipient email address: '{to_addr}'."

    try:
        msg = MIMEMultipart()
        msg["From"] = f"ALFRED Assistant <{user}>"
        msg["To"] = to_addr.strip()
        msg["Subject"] = subject.strip()
        msg.attach(MIMEText(body.strip(), "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(user, pw)
            server.send_message(msg)
        return True, f"Email successfully dispatched to {to_addr}."
    except Exception as e:
        return False, f"Failed to send email: {e}"


def gmail_manager(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    """Action entry point for Gmail interaction."""
    mode = str(parameters.get("mode", "summarize")).strip().lower()
    query = parameters.get("query")
    max_results = int(parameters.get("max_results", 5))
    to_addr = parameters.get("to")
    subject = parameters.get("subject", "")
    body = parameters.get("body", "")

    user, pw = _load_gmail_creds()
    has_creds = bool(user and pw)

    if not has_creds:
        setup_notice = (
            "Sir, Gmail integration is ready but requires your Google App Password. "
            "Please add 'gmail_user' and 'gmail_app_password' to your config or settings. "
            "In the meantime, your email channel is standing by."
        )
        if player:
            try:
                player.write_log(f"ALFRED: [Gmail] Setup needed: specify gmail_user & gmail_app_password in config/api_keys.json")
            except Exception:
                pass
        return setup_notice

    # 1. SEND MODE
    if mode == "send":
        if not to_addr or not body:
            return "Sir, I require both a recipient address and message body to send an email."
        ok, res = send_gmail_message(to_addr, subject or "Message from ALFRED", body)
        if player:
            try:
                player.write_log(f"ALFRED: [Gmail] {res}")
            except Exception:
                pass
        return res

    # 2. UNREAD / SUMMARIZE / SEARCH MODE
    emails = fetch_unread_emails(max_count=max_results, query=query if mode == "search" else None)

    if not emails:
        if mode == "search":
            return f"Sir, no emails matched your query: '{query}'."
        return "Sir, your inbox is pristine. You have no unread messages at this time."

    # Build executive spoken summary
    count = len(emails)
    summary_lines = [f"Sir, you have {count} unread email{'s' if count != 1 else ''}:"]

    for i, em in enumerate(emails, 1):
        summary_lines.append(f"{i}. From {em['sender']}: '{em['subject']}'. Preview: {em['snippet']}")

    result_text = " ".join(summary_lines)

    if player:
        try:
            player.write_log(f"ALFRED: [Gmail] Reviewed {count} unread emails.")
            for em in emails:
                player.write_log(f"   • {em['sender']} — {em['subject']}")
        except Exception:
            pass

    return result_text


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "gmail_manager",
    "description": (
        "Manages Gmail: checks unread emails, summarizes inbox status, searches messages, "
        "and sends emails. Trigger when user asks about emails, messages in inbox, unread mail, "
        "or to compose/send an email."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "Operation mode: 'summarize' (briefing), 'unread' (list recent), 'search' (find query), or 'send' (send email)."
            },
            "query": {
                "type": "STRING",
                "description": "Optional search term or filter for emails (e.g. sender name, subject keyword, or 'from:someone')."
            },
            "max_results": {
                "type": "INTEGER",
                "description": "Maximum number of emails to fetch (default: 5)."
            },
            "to": {
                "type": "STRING",
                "description": "Recipient email address for 'send' mode."
            },
            "subject": {
                "type": "STRING",
                "description": "Subject line for 'send' mode."
            },
            "body": {
                "type": "STRING",
                "description": "Message body content for 'send' mode."
            }
        },
        "required": ["mode"]
    },
    "handler": gmail_manager,
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}
