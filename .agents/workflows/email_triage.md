# /email-triage Workflow

Run this workflow whenever the user wants to process their inbox, review recent messages, or draft replies.

## Objective
Filter the noise, surface urgent communications, summarize email threads, and draft professional replies with zero user friction.

## Steps

1. **Inbox Scan & Extraction**
   - Execute `gmail_manager(mode='unread', max_results=10)`.
   - Retrieve sender, subject, timestamp, and body preview.

2. **Intelligent Categorization**
   - Classify each message into one of four tiers:
     1. **Tier 1 (Urgent / Action Required)**: Direct inquiries from boss, clients, team leads, or security alerts.
     2. **Tier 2 (Informational)**: Project updates, shipping notifications, calendar invites.
     3. **Tier 3 (Newsletters / Digests)**: Read-later content, industry news, newsletters.
     4. **Tier 4 (Spam / Promotional)**: Marketing blasts, cold outreach.

3. **Present Executive Digest**
   - Report Tier 1 items first with sender, core request, and suggested next step.
   - Summarize Tier 2 items briefly.
   - Mention total count of Tier 3/4 items without reading them aloud.

4. **Reply Composition (When Requested)**
   - When the user asks to reply to an email:
     1. Formulate a concise, professional reply matching the user's executive voice.
     2. Read back the recipient, subject, and draft body to the user.
     3. **MANDATORY SAFETY CHECK**: Require explicit user confirmation (*"Ready to send, shall I transmit?"*) before executing `gmail_manager(mode='send')`.
