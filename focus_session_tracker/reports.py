"""History and weekly review: pure functions over state, plus plain-text formatting.

Reports describe what happened. They do not grade, compare against targets,
or count streaks. A day with no sessions is shown as "-" and nothing more.
"""

from collections import Counter
from datetime import timedelta

from .timer import distractions_for, focused_seconds, from_iso, paused_seconds

# Time-of-day blocks by session start hour: (name, first hour, end hour).
TIME_BLOCKS = [
    ("Morning", 5, 12),
    ("Afternoon", 12, 17),
    ("Evening", 17, 22),
    ("Night", 22, 5),
]


def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60:02d}m"


def format_day(day):
    return f"{day:%a} {day.day} {day:%b}"


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def session_date(session):
    return from_iso(session["start"]).date()


def time_block(hour):
    for name, first, end in TIME_BLOCKS:
        if first < end and first <= hour < end:
            return name
        if first > end and (hour >= first or hour < end):
            return name
    raise ValueError(hour)


# ---------------------------------------------------------------- history


def filter_sessions(sessions, since=None, until=None, task=None):
    """Sessions whose start date is within [since, until], optionally by task text."""
    needle = task.lower() if task else None
    result = []
    for session in sessions:
        day = session_date(session)
        if since is not None and day < since:
            continue
        if until is not None and day > until:
            continue
        if needle is not None and needle not in (session["task"] or "").lower():
            continue
        result.append(session)
    return result


def history_rows(state, since=None, until=None, task=None, limit=None):
    """Finished sessions, oldest first. `limit` keeps the most recent N."""
    sessions = sorted(filter_sessions(state["sessions"], since, until, task),
                      key=lambda s: s["start"])
    total = len(sessions)
    if limit is not None and limit < total:
        sessions = sessions[total - limit:]
    rows = []
    for session in sessions:
        notes = distractions_for(state, session["id"])
        rows.append({
            "id": session["id"],
            "date": session_date(session),
            "start": from_iso(session["start"]),
            "task": session["task"],
            "focused": focused_seconds(session),
            "paused": paused_seconds(session),
            "distractions": notes,
        })
    return rows, total


def _shorten(text, width):
    return text if len(text) <= width else text[: width - 3] + "..."


def format_history(rows, total, recorded, details=False, active=None):
    """`total` is the number of matching sessions, `recorded` the number stored."""
    lines = []
    if not rows:
        lines.append("No sessions match." if recorded else "No sessions recorded yet.")
    else:
        lines.append(f"{'#':>4}  {'Date':<10}  {'Start':<5}  {'Task':<28}  {'Focused':>7}  Distractions")
        for row in rows:
            task = _shorten(row["task"] or "(no task)", 28)
            lines.append(
                f"{row['id']:>4}  {format_day(row['date']):<10}  {row['start']:%H:%M}  "
                f"{task:<28}  {format_duration(row['focused']):>7}  {len(row['distractions'])}"
            )
            if details:
                if row["paused"]:
                    lines.append(f"{'':>6}paused {format_duration(row['paused'])}")
                for d in row["distractions"]:
                    lines.append(f"{'':>6}{from_iso(d['at']):%H:%M}  {d['note']}")
        if len(rows) < total:
            lines.append(f"Showing the {len(rows)} most recent of {total} sessions (use --all for every one).")
        focus = sum(r["focused"] for r in rows)
        lines.append(f"Total focused: {format_duration(focus)} across {plural(len(rows), 'session')}.")
    if active is not None:
        lines.append(f"Session #{active['id']} is in progress (see: focus status).")
    return "\n".join(lines)


# ---------------------------------------------------------------- weekly review


def week_bounds(day):
    """Monday and Sunday of the ISO week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def normalize_note(note):
    return " ".join(note.lower().split())


def weekly_summary(state, any_day, top=5):
    """Totals, per-day breakdown, common distractions and time-of-day patterns.

    Sessions belong to the day they started. Distractions are counted by their
    own timestamp, including ones not attached to any session.
    """
    monday, sunday = week_bounds(any_day)
    sessions = filter_sessions(state["sessions"], since=monday, until=sunday)
    distractions = [
        d for d in state["distractions"] if monday <= from_iso(d["at"]).date() <= sunday
    ]

    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        day_sessions = [s for s in sessions if session_date(s) == day]
        days.append({
            "date": day,
            "focused": sum(focused_seconds(s) for s in day_sessions),
            "sessions": len(day_sessions),
            "distractions": sum(1 for d in distractions if from_iso(d["at"]).date() == day),
        })

    blocks = []
    for name, first, end in TIME_BLOCKS:
        block_sessions = [s for s in sessions if time_block(from_iso(s["start"]).hour) == name]
        if not block_sessions:
            continue
        focus = sum(focused_seconds(s) for s in block_sessions)
        count = sum(len(distractions_for(state, s["id"])) for s in block_sessions)
        blocks.append({
            "name": name,
            "hours": f"{first:02d}-{end:02d}",
            "focused": focus,
            "sessions": len(block_sessions),
            "average": focus // len(block_sessions),
            "distractions": count,
            "per_hour": (count * 3600 / focus) if focus else None,
        })

    counts = Counter(normalize_note(d["note"]) for d in distractions)
    # Most common first; ties in alphabetical order so output is stable.
    common = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top]

    total_focus = sum(focused_seconds(s) for s in sessions)
    return {
        "monday": monday,
        "sunday": sunday,
        "focused": total_focus,
        "sessions": len(sessions),
        "average": total_focus // len(sessions) if sessions else 0,
        "distractions": len(distractions),
        "days": days,
        "common": common,
        "blocks": blocks,
    }


def focus_patterns(summary):
    """Neutral one-line observations about when focus happened."""
    blocks = [b for b in summary["blocks"] if b["focused"] > 0]
    if not blocks:
        return []
    notes = []
    most = max(blocks, key=lambda b: b["focused"])
    notes.append(f"Most focused time this week was in the {most['name'].lower()}.")
    longest = max(blocks, key=lambda b: b["average"])
    if len(blocks) > 1:
        notes.append(f"Longest sessions on average: {longest['name'].lower()} "
                     f"({format_duration(longest['average'])}).")
        calmest = min(blocks, key=lambda b: (b["per_hour"], -b["focused"]))
        notes.append(f"Fewest distractions per focused hour: {calmest['name'].lower()}.")
    busiest = max(summary["days"], key=lambda d: d["focused"])
    notes.append(f"Most focused day: {format_day(busiest['date'])} "
                 f"({format_duration(busiest['focused'])}).")
    return notes


def format_week(summary, active=None):
    s = summary
    lines = [f"Week of {format_day(s['monday'])} - {format_day(s['sunday'])} {s['sunday']:%Y}", ""]
    if s["sessions"] == 0:
        lines.append("No sessions recorded this week.")
    else:
        lines.append(f"Focused time    {format_duration(s['focused'])} across {plural(s['sessions'], 'session')}")
        lines.append(f"Average session {format_duration(s['average'])}")
    lines.append(f"Distractions    {s['distractions']}")

    if s["sessions"]:
        lines += ["", "By day"]
        for day in s["days"]:
            if day["sessions"] == 0 and day["distractions"] == 0:
                lines.append(f"  {format_day(day['date']):<10}  {'-':>7}")
                continue
            focus = format_duration(day["focused"]) if day["sessions"] else "-"
            lines.append(
                f"  {format_day(day['date']):<10}  {focus:>7}  "
                f"{plural(day['sessions'], 'session'):<11}  {plural(day['distractions'], 'distraction')}"
            )

    if s["common"]:
        lines += ["", "Most common distractions"]
        for note, count in s["common"]:
            lines.append(f"  {count:>3}  {note}")

    if s["blocks"]:
        lines += ["", "Time of day (by session start)"]
        for b in s["blocks"]:
            rate = "-" if b["per_hour"] is None else f"{b['per_hour']:.1f}"
            lines.append(
                f"  {b['name']:<9} {b['hours']}  {format_duration(b['focused']):>7}  "
                f"{plural(b['sessions'], 'session'):<11}  avg {format_duration(b['average']):>7}  "
                f"{rate} distractions/hr"
            )
        patterns = focus_patterns(s)
        if patterns:
            lines += ["", "Patterns"]
            lines += [f"  {p}" for p in patterns]

    if active is not None:
        lines += ["", f"Session #{active['id']} is in progress and not included yet."]
    return "\n".join(lines)
