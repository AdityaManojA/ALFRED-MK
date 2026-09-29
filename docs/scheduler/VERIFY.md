# Scheduler Verification

## Completed implementation

- `core/scheduler/ledger.py` writes `data/schedule.json` atomically and keeps malformed local data from crashing the scheduler.
- `core/scheduler/parser.py` handles relative times, 24-hour times, AM/PM, and daily recurrence.
- `core/scheduler/engine.py` uses a 1-second polling interval within one minute of pending work and a 10-second idle interval otherwise. It supports pause, delete, trigger-now, acknowledge, and macro abort/cancel controls.
- `core/scheduler/automation.py` focuses a user-selected window/tab keyword before clipboard paste, waits 200 ms, then optionally presses Enter. It reports failure without injecting input if focus cannot be confirmed.
- `core/ui/task_board.py`, `ui.py`, and `main.py` connect the same engine to a HUD task board and application lifetime. The board provides pause/resume, delete, immediate trigger, acknowledgment, and abort during the 10-second macro warning.
- `actions/schedule_task.py` schedules both voice reminders and explicit local macros against the process-wide engine.

## Validation

Run `python -m unittest tests.scheduler.test_scheduler_engine` for deterministic parser, ledger, reminder, acknowledgment, and cancelled-macro checks. Pytest is not installed in the active interpreter, so the repository's pytest suite could not be executed here.
