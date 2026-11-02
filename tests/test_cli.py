import io
import json
from pathlib import Path

from focus_session_tracker import cli
from tests.helpers import Cli, FakeClock, at


def test_first_run_with_no_data_file():
    app = Cli(FakeClock(at(2026, 11, 2, 9)))
    assert app.ok("status") == "No active session. Start one with: focus start [task]\n"
    assert app.ok("history") == "No sessions recorded yet.\n"
    assert "No sessions recorded this week." in app.ok("week")
    # Read-only commands do not create the file.
    assert not Path(app.path).exists()


def test_full_session_walkthrough():
    clock = FakeClock(at(2026, 11, 2, 9, 0))
    app = Cli(clock)
    assert app.ok("start", "Write", "report") == "Started session #1: Write report at 09:00\n"
    clock.advance(minutes=20)
    assert "focused 20m so far" in app.ok("pause")
    clock.advance(minutes=5)
    assert app.ok("resume") == "Resumed session #1 after a 5m pause\n"
    clock.advance(minutes=3)
    assert "(session #1): Slack" in app.ok("distract", "Slack")
    status = app.ok("status")
    assert "Focusing: Write report (session #1)" in status
    assert "focused 23m" in status and "1 distraction logged" in status
    clock.advance(minutes=12)
    out = app.ok("stop")
    assert out == "Stopped session #1: Write report\n  Focused 35m, paused 5m, 1 distraction\n"

    data = json.loads(Path(app.path).read_text())
    assert data["active"] is None and len(data["sessions"]) == 1
    assert data["distractions"][0]["at"] == "2026-11-02T09:28:00+01:00"

    history = app.ok("history")
    assert "Write report" in history and "35m" in history
    week = app.ok("week")
    assert "35m across 1 session" in week and "1  slack" in week


def test_error_cases_exit_nonzero_with_message():
    app = Cli(FakeClock(at(2026, 11, 2, 9)))
    for command in ("stop", "pause", "resume", "cancel"):
        code, out, err = app.run(command)
        assert code == 1 and out == "" and "No active session" in err
    app.ok("start")
    code, _, err = app.run("start", "again")
    assert code == 1 and "already running" in err
    code, _, err = app.run("distract", "--session", "42", "x")
    assert code == 1 and "No session #42" in err


def test_status_while_paused_and_cancel():
    clock = FakeClock(at(2026, 11, 2, 9))
    app = Cli(clock)
    app.ok("start", "Plan")
    clock.advance(minutes=10)
    app.ok("pause")
    clock.advance(minutes=30)
    status = app.ok("status")
    assert status.startswith("Paused: Plan") and "focused 10m" in status
    assert "Paused 30m in total" in status
    assert "not recorded" in app.ok("cancel")
    assert app.ok("history") == "No sessions recorded yet.\n"


def test_distract_after_session_with_last():
    clock = FakeClock(at(2026, 11, 2, 9))
    app = Cli(clock)
    app.ok("start")
    clock.advance(minutes=25)
    app.ok("stop")
    assert "(session #1)" in app.ok("distract", "--last", "kept", "thinking", "about", "lunch")
    assert "(no session)" in app.ok("distract", "doorbell")
    details = app.ok("history", "--details")
    assert "09:25  kept thinking about lunch" in details
    assert "doorbell" not in details


def test_history_filters_from_cli():
    clock = FakeClock(at(2026, 10, 20, 9))
    app = Cli(clock)
    for day, task in ((20, "Alpha"), (28, "Beta"), (31, "Alpha two")):
        clock.set(at(2026, 10, day, 9))
        app.ok("start", task)
        clock.advance(minutes=30)
        app.ok("stop")
    clock.set(at(2026, 11, 2, 10))
    assert "Beta" not in app.ok("history", "--task", "alpha")
    recent = app.ok("history", "--days", "7")
    assert "Alpha two" in recent and "Beta" in recent and "Tue 20 Oct" not in recent
    assert "Beta" not in app.ok("history", "--since", "2026-10-29")
    assert "Alpha two" not in app.ok("history", "--until", "2026-10-30")
    limited = app.ok("history", "--limit", "1")
    assert "Alpha two" in limited and "Showing the 1 most recent of 3" in limited
    assert "Showing" not in app.ok("history", "--limit", "1", "--all")
    assert "No sessions match." in app.ok("history", "--task", "zzz")


def test_week_selection():
    clock = FakeClock(at(2026, 10, 27, 9))
    app = Cli(clock)
    app.ok("start")
    clock.advance(minutes=40)
    app.ok("stop")
    clock.set(at(2026, 11, 2, 9))
    assert "No sessions recorded this week." in app.ok("week")
    assert "40m across 1 session" in app.ok("week", "--previous", "1")
    assert "40m across 1 session" in app.ok("week", "2026-11-01")


def test_week_mentions_active_session():
    clock = FakeClock(at(2026, 11, 2, 9))
    app = Cli(clock)
    app.ok("start")
    assert "Session #1 is in progress and not included yet." in app.ok("week")


def test_corrupt_data_file_is_reported_not_overwritten():
    app = Cli(FakeClock(at(2026, 11, 2, 9)))
    path = Path(app.path)
    path.parent.mkdir(parents=True)
    path.write_text("{oops")
    code, _, err = app.run("start")
    assert code == 1 and "not valid JSON" in err
    assert path.read_text() == "{oops"


def test_empty_data_file_works():
    app = Cli(FakeClock(at(2026, 11, 2, 9)))
    path = Path(app.path)
    path.parent.mkdir(parents=True)
    path.write_text("")
    assert "Started session #1" in app.ok("start")


def test_data_path_from_environment():
    app = Cli(FakeClock(at(2026, 11, 2, 9)))
    out = io.StringIO()
    code = cli.main(["start", "Env"], clock=app.clock, out=out, err=io.StringIO(),
                    env={"FOCUS_DATA_FILE": app.path})
    assert code == 0 and Path(app.path).exists()


def test_no_command_prints_help():
    out = io.StringIO()
    assert cli.main([], out=out) == 0
    assert "start" in out.getvalue() and "week" in out.getvalue()
