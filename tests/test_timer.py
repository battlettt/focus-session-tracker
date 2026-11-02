from datetime import timedelta

from focus_session_tracker import store, timer
from tests.helpers import at


def expect_error(fn, *args, contains="", **kwargs):
    try:
        fn(*args, **kwargs)
    except timer.TimerError as exc:
        assert contains in str(exc), str(exc)
        return
    raise AssertionError("expected TimerError")


def test_start_stop_counts_elapsed_time():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9, 0)
    session = timer.start_session(state, t0, "Write report")
    assert session["id"] == 1 and session["task"] == "Write report"
    assert timer.focused_seconds(session, t0 + timedelta(minutes=10)) == 600
    timer.stop_session(state, t0 + timedelta(minutes=25))
    assert state["active"] is None
    assert timer.focused_seconds(state["sessions"][0]) == 25 * 60


def test_pause_time_is_excluded():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9, 0)
    timer.start_session(state, t0)
    timer.pause_session(state, t0 + timedelta(minutes=10))
    # While paused, focused time stands still.
    session = state["active"]
    assert timer.focused_seconds(session, t0 + timedelta(minutes=10)) == 600
    assert timer.focused_seconds(session, t0 + timedelta(minutes=40)) == 600
    timer.resume_session(state, t0 + timedelta(minutes=15))
    timer.pause_session(state, t0 + timedelta(minutes=20))
    timer.resume_session(state, t0 + timedelta(minutes=22))
    timer.stop_session(state, t0 + timedelta(minutes=30))
    done = state["sessions"][0]
    assert timer.elapsed_seconds(done) == 30 * 60
    assert timer.paused_seconds(done) == 7 * 60
    assert timer.focused_seconds(done) == 23 * 60


def test_stop_while_paused_closes_the_pause():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9, 0)
    timer.start_session(state, t0)
    timer.pause_session(state, t0 + timedelta(minutes=20))
    timer.stop_session(state, t0 + timedelta(minutes=50))
    done = state["sessions"][0]
    assert done["pauses"][-1]["end"] == done["end"]
    assert timer.focused_seconds(done) == 20 * 60
    assert timer.paused_seconds(done) == 30 * 60


def test_untitled_task_and_whitespace_label():
    state = store.empty_state()
    assert timer.start_session(state, at(2026, 11, 2), "   ")["task"] is None


def test_ids_increase():
    state = store.empty_state()
    t0 = at(2026, 11, 2)
    for expected in (1, 2, 3):
        assert timer.start_session(state, t0)["id"] == expected
        timer.stop_session(state, t0)


def test_double_start_is_refused():
    state = store.empty_state()
    timer.start_session(state, at(2026, 11, 2), "A")
    expect_error(timer.start_session, state, at(2026, 11, 2, 10), "B", contains="already running")
    assert state["active"]["task"] == "A"


def test_actions_without_active_session():
    state = store.empty_state()
    now = at(2026, 11, 2)
    expect_error(timer.stop_session, state, now, contains="No active session to stop")
    expect_error(timer.pause_session, state, now, contains="No active session to pause")
    expect_error(timer.resume_session, state, now, contains="No active session to resume")
    expect_error(timer.cancel_session, state, contains="No active session to cancel")


def test_double_pause_and_resume_without_pause():
    state = store.empty_state()
    now = at(2026, 11, 2)
    timer.start_session(state, now)
    expect_error(timer.resume_session, state, now, contains="not paused")
    timer.pause_session(state, now)
    expect_error(timer.pause_session, state, now, contains="already paused")


def test_clock_going_backwards_never_gives_negative_time():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9)
    timer.start_session(state, t0)
    timer.stop_session(state, t0 - timedelta(minutes=5))
    assert timer.focused_seconds(state["sessions"][0]) == 0


def test_distraction_attaches_to_active_session_with_timestamp():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9)
    timer.start_session(state, t0)
    d = timer.log_distraction(state, t0 + timedelta(minutes=7), "  Slack ping ")
    assert d == {"at": "2026-11-02T09:07:00+01:00", "note": "Slack ping", "session_id": 1}
    assert timer.distractions_for(state, 1) == [d]


def test_distraction_without_session_is_standalone():
    state = store.empty_state()
    d = timer.log_distraction(state, at(2026, 11, 2), "phone")
    assert d["session_id"] is None


def test_distraction_after_session_with_last_or_id():
    state = store.empty_state()
    t0 = at(2026, 11, 2, 9)
    for _ in range(2):
        timer.start_session(state, t0)
        timer.stop_session(state, t0 + timedelta(minutes=30))
    assert timer.log_distraction(state, t0, "email", attach_last=True)["session_id"] == 2
    assert timer.log_distraction(state, t0, "news", session_id=1)["session_id"] == 1
    expect_error(timer.log_distraction, state, t0, "x", session_id=99, contains="No session #99")


def test_distraction_requires_note_and_last_requires_a_session():
    state = store.empty_state()
    expect_error(timer.log_distraction, state, at(2026, 11, 2), "  ", contains="short note")
    expect_error(timer.log_distraction, state, at(2026, 11, 2), "x", attach_last=True,
                 contains="No finished sessions")


def test_cancel_discards_session_and_its_distractions():
    state = store.empty_state()
    t0 = at(2026, 11, 2)
    timer.log_distraction(state, t0, "loose")
    timer.start_session(state, t0)
    timer.log_distraction(state, t0, "noise")
    timer.cancel_session(state)
    assert state["active"] is None and state["sessions"] == []
    assert [d["note"] for d in state["distractions"]] == ["loose"]
