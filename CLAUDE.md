# CLAUDE.md - Focus Session Tracker

## What this is
A command line focus session tracker: timed focus sessions, a distraction
log, session history, and a weekly review. Built to protect focus and
reduce procrastination without streaks, guilt, or pressure.

## Principles
- Local-only. Session data stays on the user's machine. No network, no
  accounts, no sync.
- No streaks, no guilt styling. Missed sessions are neutral, not failures.
- Plain readable output. Every report must be understandable at a glance.
- Python standard library only for the core. No dependencies to install.

## Build, test, run
- Run: `python -m focus_session_tracker` (see README for commands)
- Tests: plain asserts, runnable with or without pytest:
  `python -m pytest`
- Keep the CLI, the session store, and the reporting code separate so each
  can be tested alone.

## Conventions
- Small functions, clear names, minimal abstraction.
- Every feature ships with tests and a README section.
- A browser demo is optional; if built, it must run offline and match the
  CLI's numbers exactly.
