# Focus Session Tracker

A small command line tool for timed focus sessions, a distraction log,
session history, and a weekly review.

- **Local-only.** Your data is a JSON file on your machine. There's no
  network, no accounts, no sync.
- **No streaks, scores or targets.** A day without sessions shows up as `-`
  and nothing else. The weekly review says what happened and when focus
  went well. It doesn't judge.
- **Python 3 standard library only.** Nothing to install.

## Running it

From the repo root:

```sh
python3 -m focus_session_tracker <command> [options]
```

To get a `focus` command, install the package (it has no dependencies) or
add a shell alias:

```sh
pip install .                                    # provides `focus`
alias focus='python3 -m focus_session_tracker'   # or this, from the repo root
```

The examples below use `focus`. Run `focus --help` or
`focus <command> --help` for every option.

| Command | What it does |
| --- | --- |
| `focus start [task]` | Start a session, with an optional task label |
| `focus pause` / `focus resume` | Pause and resume. Paused time is not counted as focus |
| `focus stop` | Stop the session and record it |
| `focus cancel` | Throw away the active session without recording it |
| `focus distract "note"` | Log a distraction with the current time |
| `focus status` | Show the active session |
| `focus history` | List past sessions |
| `focus week` | Weekly review |

## Commands

### start

```
$ focus start Write project report
Started session #1: Write project report at 09:00
```

The task label is optional (`focus start` alone works). Only one session
can run at a time. Starting a second one prints a message and leaves the
first one running:

```
$ focus start Something else
Session #1 (Write project report) is already running. Stop it first with: focus stop
```

### pause and resume

```
$ focus pause
Paused session #1 at 09:25 (focused 25m so far)
$ focus resume
Resumed session #1 after a 10m pause
```

Paused time never counts as focused time. Running `focus stop` while paused
ends the pause at the moment you stop.

### stop

```
$ focus stop
Stopped session #1: Write project report
  Focused 1h 00m, paused 10m, 1 distraction
```

Focused time is the time from start to stop, minus any pauses.

### cancel

```
$ focus cancel
Discarded session #2: (no task) (not recorded)
```

This also removes any distractions logged against that session.

### distract

```
$ focus distract email notification
Logged distraction at 09:18 (session #1): email notification
```

Each entry stores the time and your note. Quotes around the note are
optional. Where the entry goes:

- If a session is running, it's attached to that session.
- `--last` attaches it to the most recent finished session, for things you
  remember afterwards:
  `focus distract --last "remembered a call to make"`
- `--session ID` attaches it to a particular session (the IDs are listed in
  `focus history`).
- Otherwise it's stored on its own. It still counts in the weekly review.

### status

```
$ focus status
Focusing: Write project report (session #1)
  Started 09:00, focused 40m
  Paused 10m in total
  1 distraction logged
```

With no session running: `No active session. Start one with: focus start [task]`.

### history

```
$ focus history
   #  Date        Start  Task                          Focused  Distractions
   1  Mon 26 Oct  09:00  Write project report           1h 00m  2
   2  Mon 26 Oct  14:00  Code review                       25m  1
   3  Tue 27 Oct  09:30  Write project report              55m  1
Total focused: 2h 20m across 3 sessions.
```

Filters can be combined:

| Option | Meaning |
| --- | --- |
| `--days N` | Only the last N days, including today |
| `--since YYYY-MM-DD` / `--until YYYY-MM-DD` | Date range (inclusive, by start date) |
| `--task TEXT` | Only tasks containing TEXT (case-insensitive) |
| `--limit N` | Show the N most recent (default 20) |
| `--all` | Show every matching session |
| `--details` | Also show paused time and each distraction note |

```
$ focus history --task report --details
   #  Date        Start  Task                          Focused  Distractions
   1  Mon 26 Oct  09:00  Write project report           1h 00m  2
      paused 10m
      09:18  email notification
      10:13  remembered a call to make
   3  Tue 27 Oct  09:30  Write project report              55m  1
      09:57  email notification
Total focused: 1h 55m across 2 sessions.
```

### week

```
$ focus week
Week of Mon 26 Oct - Sun 1 Nov 2026

Focused time    5h 15m across 7 sessions
Average session 45m
Distractions    8

By day
  Mon 26 Oct   1h 25m  2 sessions   3 distractions
  Tue 27 Oct      55m  1 session    1 distraction
  Wed 28 Oct   1h 10m  2 sessions   2 distractions
  Thu 29 Oct        -
  Fri 30 Oct   1h 45m  2 sessions   2 distractions
  Sat 31 Oct        -
  Sun 1 Nov         -

Most common distractions
    3  email notification
    3  phone
    1  chat message
    1  remembered a call to make

Time of day (by session start)
  Morning   05-12   3h 35m  4 sessions   avg     53m  1.1 distractions/hr
  Afternoon 12-17   1h 05m  2 sessions   avg     32m  2.8 distractions/hr
  Evening   17-22      35m  1 session    avg     35m  1.7 distractions/hr

Patterns
  Most focused time this week was in the morning.
  Longest sessions on average: morning (53m).
  Fewest distractions per focused hour: morning.
  Most focused day: Fri 30 Oct (1h 45m).
```

- Weeks run Monday to Sunday. `focus week 2026-10-28` reviews the week
  containing that date, and `focus week --previous 1` reviews last week.
- A session belongs to the day it started. Distractions are counted on the
  day they happened, including ones not attached to a session.
- When counting common distractions, notes are compared without regard to
  case or extra spaces, so `Email` and `email ` count as the same thing.
- A session that is still running is left out of the review, and the
  review says so.

## Where data is stored

The tool picks the first of these that applies:

1. `--data PATH` (a global option, given before the command):
   `focus --data /tmp/test.json status`
2. The `FOCUS_DATA_FILE` environment variable
3. `$XDG_DATA_HOME/focus-session-tracker/sessions.json`
4. `~/.local/share/focus-session-tracker/sessions.json`

On first use the file and its folder don't need to exist; they're created
the first time you record something. A missing or empty file is treated as
"no data yet". If the file isn't valid JSON, the tool prints an error and
leaves the file alone. It never overwrites data it can't read. Writes go
to a temporary file that is then renamed into place, so an interrupted
write can't leave a half-written file.

When a command can't run (for example `stop`, `pause`, `resume` or `cancel`
with no session active, or a second `start`), it prints a plain message and
exits with status 1. Nothing is changed.

## Tests

```sh
python3 run_tests.py       # plain runner, no pytest needed
python3 -m pytest          # also works if pytest is installed
```

The tests use a fake clock, so timer math (including pause exclusion) runs
instantly. They cover the timer, the distraction log, storage edge cases,
history filters, the weekly totals and patterns, the CLI end to end, and
the demo page.

## Browser demo

`demo/index.html` is a static page that walks through a sample week. It
works offline: no scripts, no external assets. Every output on the page
comes from running the real CLI on sample data with a simulated clock. To
regenerate it after changing any output:

```sh
python3 scripts/build_demo.py
```

`tests/test_demo.py` fails if the page doesn't match what the CLI prints
now.

## Layout

```
focus_session_tracker/
  timer.py     session timer and distraction logic (clock passed in as `now`)
  store.py     JSON file loading and saving
  reports.py   history and weekly review, computing and formatting
  cli.py       argument parsing and commands
tests/         plain-assert tests and a fake clock (helpers.py)
run_tests.py   test runner that needs no pytest
scripts/build_demo.py   builds demo/index.html from CLI output
```
