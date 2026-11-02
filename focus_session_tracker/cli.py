"""Command line interface: parses arguments, loads/saves the store, prints reports."""

import argparse
import sys
from datetime import date, timedelta

from . import __version__, reports, store, timer
from .reports import format_duration, plural


def build_parser():
    parser = argparse.ArgumentParser(
        prog="focus",
        description="Local-only focus session tracker. Data stays on this machine.",
    )
    parser.add_argument("--data", metavar="PATH",
                        help=f"data file to use (default: ${store.ENV_VAR} or "
                             "~/.local/share/focus-session-tracker/sessions.json)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("start", help="start a focus session")
    p.add_argument("task", nargs="*", help="optional task label")
    sub.add_parser("stop", help="stop the active session and record it")
    sub.add_parser("pause", help="pause the active session (paused time is not counted)")
    sub.add_parser("resume", help="resume a paused session")
    sub.add_parser("cancel", help="discard the active session without recording it")

    p = sub.add_parser("distract", help="log a distraction with a short note")
    p.add_argument("note", nargs="+", help="what pulled your attention away")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--session", type=int, metavar="ID", help="attach to session ID")
    group.add_argument("--last", action="store_true", help="attach to the most recent finished session")

    sub.add_parser("status", help="show the active session")

    p = sub.add_parser("history", help="list past sessions")
    p.add_argument("--days", type=int, metavar="N", help="only the last N days (including today)")
    p.add_argument("--since", type=parse_date, metavar="YYYY-MM-DD", help="only sessions on or after this date")
    p.add_argument("--until", type=parse_date, metavar="YYYY-MM-DD", help="only sessions on or before this date")
    p.add_argument("--task", metavar="TEXT", help="only sessions whose task contains TEXT")
    p.add_argument("--limit", type=int, default=20, metavar="N", help="show the N most recent (default 20)")
    p.add_argument("--all", action="store_true", help="show every matching session")
    p.add_argument("--details", action="store_true", help="also show distraction notes and paused time")

    p = sub.add_parser("week", help="weekly review")
    p.add_argument("date", nargs="?", type=parse_date, metavar="YYYY-MM-DD",
                   help="any day in the week to review (default: this week)")
    p.add_argument("--previous", type=int, default=0, metavar="N",
                   help="go back N weeks (e.g. --previous 1 for last week)")
    return parser


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a date like 2026-11-02, got {text!r}")


def _label(session):
    return session["task"] or "(no task)"


def cmd_start(state, args, now):
    session = timer.start_session(state, now, " ".join(args.task))
    return f"Started session #{session['id']}: {_label(session)} at {now:%H:%M}"


def cmd_stop(state, args, now):
    session = timer.stop_session(state, now)
    count = len(timer.distractions_for(state, session["id"]))
    line = (f"Stopped session #{session['id']}: {_label(session)}\n"
            f"  Focused {format_duration(timer.focused_seconds(session))}")
    paused = timer.paused_seconds(session)
    if paused:
        line += f", paused {format_duration(paused)}"
    return line + f", {plural(count, 'distraction')}"


def cmd_pause(state, args, now):
    session = timer.pause_session(state, now)
    return (f"Paused session #{session['id']} at {now:%H:%M} "
            f"(focused {format_duration(timer.focused_seconds(session, now))} so far)")


def cmd_resume(state, args, now):
    session = timer.resume_session(state, now)
    pause = session["pauses"][-1]
    length = timer.seconds_between(timer.from_iso(pause["start"]), now)
    return f"Resumed session #{session['id']} after a {format_duration(length)} pause"


def cmd_cancel(state, args, now):
    session = timer.cancel_session(state)
    return f"Discarded session #{session['id']}: {_label(session)} (not recorded)"


def cmd_distract(state, args, now):
    d = timer.log_distraction(state, now, " ".join(args.note),
                              session_id=args.session, attach_last=args.last)
    where = f"session #{d['session_id']}" if d["session_id"] else "no session"
    return f"Logged distraction at {now:%H:%M} ({where}): {d['note']}"


def cmd_status(state, args, now):
    session = timer.active_session(state)
    if session is None:
        return "No active session. Start one with: focus start [task]"
    start = timer.from_iso(session["start"])
    mode = "Paused" if timer.is_paused(session) else "Focusing"
    lines = [
        f"{mode}: {_label(session)} (session #{session['id']})",
        f"  Started {start:%H:%M}, focused {format_duration(timer.focused_seconds(session, now))}",
    ]
    paused = timer.paused_seconds(session, now)
    if paused:
        lines.append(f"  Paused {format_duration(paused)} in total")
    notes = timer.distractions_for(state, session["id"])
    lines.append(f"  {plural(len(notes), 'distraction')} logged")
    return "\n".join(lines)


def cmd_history(state, args, now):
    since = args.since
    if args.days is not None:
        if args.days < 1:
            raise timer.TimerError("--days needs a number of 1 or more.")
        days_since = now.date() - timedelta(days=args.days - 1)
        since = max(since, days_since) if since else days_since
    if args.limit < 1 and not args.all:
        raise timer.TimerError("--limit needs a number of 1 or more.")
    limit = None if args.all else args.limit
    rows, total = reports.history_rows(state, since=since, until=args.until,
                                       task=args.task, limit=limit)
    return reports.format_history(rows, total, len(state["sessions"]), details=args.details,
                                  active=timer.active_session(state))


def cmd_week(state, args, now):
    day = args.date or now.date()
    day -= timedelta(weeks=args.previous)
    summary = reports.weekly_summary(state, day)
    return reports.format_week(summary, active=timer.active_session(state))


COMMANDS = {
    "start": (cmd_start, True),
    "stop": (cmd_stop, True),
    "pause": (cmd_pause, True),
    "resume": (cmd_resume, True),
    "cancel": (cmd_cancel, True),
    "distract": (cmd_distract, True),
    "status": (cmd_status, False),
    "history": (cmd_history, False),
    "week": (cmd_week, False),
}


def main(argv=None, clock=timer.system_clock, out=None, err=None, env=None):
    """Run one command. Returns the exit code. `clock` is injectable for tests."""
    out = out or sys.stdout
    err = err or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(out)
        return 0
    path = args.data or store.default_path(env)
    handler, writes = COMMANDS[args.command]
    try:
        state = store.load(path)
        message = handler(state, args, clock())
        if writes:
            store.save(path, state)
    except (timer.TimerError, store.StoreError) as exc:
        print(exc, file=err)
        return 1
    print(message, file=out)
    return 0
