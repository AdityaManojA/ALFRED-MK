# /deep-work Workflow

Run this workflow when the user is ready to start an uninterrupted focus session or Pomodoro block.

## Objective
Configure the environment for maximum cognitive throughput, eliminate distractions, set time boundaries, and track progress.

## Steps

1. **Define Objective & Time Block**
   - Confirm target task (e.g., *"Refactoring authentication module"*) and duration (standard: 25, 45, or 60 minutes).

2. **Engage Focus Protocol**
   - Execute `focus_protocol(action='start', duration_minutes=<duration>, task='<objective>')`.

3. **Workspace Preparation**
   - If requested, launch designated development IDE, terminal, or workspace using `open_app`.
   - Minimize non-essential browser windows using `computer_control`.

4. **Notification Shielding**
   - Route non-urgent notifications to silent logging.
   - Hold incoming Tier 2-4 emails until the focus block concludes. Only Tier 1 critical alerts may interrupt.

5. **Session Wrap-Up & Check-In**
   - When the timer fires, gently alert the user that the focus interval has finished.
   - Prompt for a 5-minute break and summarize what was accomplished.
