"""Session timer logic: start, pause, resume, stop, and distraction logging.

All functions take the current time as an argument (`now`), so the timer can
be tested with a fake clock instead of waiting real minutes. State is a plain
dict (see store.empty_state) and timestamps are stored as ISO 8601 strings.
"""

from datetime import datetime


class TimerError(Exception):
    """An action that does not fit the current state (e.g. stop while idle)."""


def system_clock():
    """Current local time, timezone-aware."""
    return datetime.now().astimezone()


def to_iso(moment):
    return moment.isoformat(timespec="seconds")


def from_iso(text):
    return datetime.fromisoformat(text)


def seconds_between(start, end):
    """Whole seconds from start to end, never negative (guards clock skew)."""
    return max(0, int((end - start).total_seconds()))


def is_paused(session):
    pauses = session["pauses"]
    return bool(pauses) and pauses[-1]["end"] is None


def paused_seconds(session, now=None):
    """Total paused time. An open pause counts up to `now` (or the end)."""
    total = 0
    for pause in session["pauses"]:
        start = from_iso(pause["start"])
        if pause["end"] is not None:
            end = from_iso(pause["end"])
        elif session["end"] is not None:
            end = from_iso(session["end"])
        else:
            end = now
        if end is not None:
            total += seconds_between(start, end)
    return total


def elapsed_seconds(session, now=None):
    """Wall-clock time from start to end (or to `now` if still running)."""
    end = from_iso(session["end"]) if session["end"] else now
    return seconds_between(from_iso(session["start"]), end)


def focused_seconds(session, now=None):
    """Elapsed time minus paused time. Paused time never counts as focus."""
    return max(0, elapsed_seconds(session, now) - paused_seconds(session, now))


def active_session(state):
    return state["active"]


def start_session(state, now, task=None):
    if state["active"] is not None:
        current = state["active"]
        label = current["task"] or "untitled"
        raise TimerError(
            f"Session #{current['id']} ({label}) is already running. "
            "Stop it first with: focus stop"
        )
    task = (task or "").strip() or None
    session = {
        "id": state["next_id"],
        "task": task,
        "start": to_iso(now),
        "end": None,
        "pauses": [],
    }
    state["next_id"] += 1
    state["active"] = session
    return session


def _require_active(state, action):
    if state["active"] is None:
        raise TimerError(f"No active session to {action}. Start one with: focus start [task]")
    return state["active"]


def pause_session(state, now):
    session = _require_active(state, "pause")
    if is_paused(session):
        raise TimerError(f"Session #{session['id']} is already paused. Resume with: focus resume")
    session["pauses"].append({"start": to_iso(now), "end": None})
    return session


def resume_session(state, now):
    session = _require_active(state, "resume")
    if not is_paused(session):
        raise TimerError(f"Session #{session['id']} is not paused.")
    session["pauses"][-1]["end"] = to_iso(now)
    return session


def stop_session(state, now):
    """End the active session. An open pause is closed at the stop time."""
    session = _require_active(state, "stop")
    if is_paused(session):
        session["pauses"][-1]["end"] = to_iso(now)
    session["end"] = to_iso(now)
    state["sessions"].append(session)
    state["active"] = None
    return session


def cancel_session(state):
    """Discard the active session without recording it."""
    session = _require_active(state, "cancel")
    state["active"] = None
    state["distractions"] = [
        d for d in state["distractions"] if d["session_id"] != session["id"]
    ]
    return session


def find_session(state, session_id):
    for session in state["sessions"]:
        if session["id"] == session_id:
            return session
    active = state["active"]
    if active is not None and active["id"] == session_id:
        return active
    return None


def log_distraction(state, now, note, session_id=None, attach_last=False):
    """Record a distraction with a timestamp and short note.

    Association rules:
    - an explicit session_id attaches to that session;
    - otherwise attach_last attaches to the most recent finished session;
    - otherwise the active session, if there is one;
    - otherwise the distraction is stored on its own (session_id None).
    """
    note = (note or "").strip()
    if not note:
        raise TimerError("A distraction needs a short note, e.g. focus distract \"email\"")
    if session_id is not None:
        if find_session(state, session_id) is None:
            raise TimerError(f"No session #{session_id}. See ids with: focus history")
    elif attach_last:
        if not state["sessions"]:
            raise TimerError("No finished sessions yet to attach this to.")
        session_id = state["sessions"][-1]["id"]
    elif state["active"] is not None:
        session_id = state["active"]["id"]
    distraction = {"at": to_iso(now), "note": note, "session_id": session_id}
    state["distractions"].append(distraction)
    return distraction


def distractions_for(state, session_id):
    return [d for d in state["distractions"] if d["session_id"] == session_id]
