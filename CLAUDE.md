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
- Run: `python3 -m focus_session_tracker` (see README for commands)
- Tests: plain asserts, runnable with or without pytest:
  `python3 run_tests.py` (no pytest needed) or `python3 -m pytest`
- Keep the CLI, the session store, and the reporting code separate so each
  can be tested alone: `cli.py`, `store.py`, `timer.py`, `reports.py`.
- Timer code takes `now` as an argument; tests use a fake clock
  (`tests/helpers.py`), never real waiting.
- After changing any output, rebuild the demo:
  `python3 scripts/build_demo.py` (`tests/test_demo.py` checks it).

## Conventions
- Small functions, clear names, minimal abstraction.
- Every feature ships with tests and a README section.
- A browser demo is optional; if built, it must run offline and match the
  CLI's numbers exactly.
