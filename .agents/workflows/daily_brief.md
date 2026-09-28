# /daily-brief Workflow

Run this workflow whenever the user asks for a morning briefing, daily status report, or starts their day.

## Objective
Deliver a crisp, executive situational summary covering live conditions, priority communications, scheduled agenda, and device readiness.

## Steps

1. **Acknowledge and Contextualize Time of Day**
   - Check local time and address the user with their configured name and respectful executive tone (*"Good morning, Commander"* or *"Good morning, Sir"*).

2. **Retrieve Live Environmental Telemetry**
   - Query live weather conditions (temperature, sky condition, precipitation chance) using `daily_brief` or `weather_report`.

3. **Triage Priority Communications (Gmail)**
   - Query `gmail_manager` for unread emails (`mode='summarize'`).
   - Highlight:
     - High-priority / VIP senders.
     - Urgent action items requiring immediate attention.
     - Total unread message count.

4. **Review Calendar Agenda & Reminders**
   - Query `calendar_sync` (`action='list'`) for meetings and deadlines scheduled for today.
   - Query `reminder` queue for timed reminders.

5. **Assess Device & System Health**
   - Check CPU load, RAM usage, and battery power level via `system_monitor`.
   - Alert the user if memory exceeds 85% or laptop is unplugged below 25%.

6. **Deliver Executive Actionable Synthesis**
   - Synthesize the findings into a clear, spoken summary:
     - 1 sentence on weather & clothing/umbrella recommendation if rainy.
     - 1-2 sentences on critical emails & action items.
     - 1 sentence on the first upcoming meeting/event.
     - 1 sentence confirming system readiness.
   - Close with readiness statement: *"Systems are running at peak capacity. What is our first objective?"*
