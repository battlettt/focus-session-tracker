from datetime import date, timedelta

from focus_session_tracker import reports, store, timer
from tests.helpers import at


def add_session(state, start, minutes, task=None, pause_minutes=0, notes=()):
    timer.start_session(state, start, task)
    if pause_minutes:
        timer.pause_session(state, start + timedelta(minutes=1))
        timer.resume_session(state, start + timedelta(minutes=1 + pause_minutes))
    for i, note in enumerate(notes):
        timer.log_distraction(state, start + timedelta(minutes=2 + i), note)
    timer.stop_session(state, start + timedelta(minutes=minutes + pause_minutes))
    return state["sessions"][-1]


def sample_state():
    """Week of Mon 26 Oct 2026, plus one session the week before and after."""
    state = store.empty_state()
    add_session(state, at(2026, 10, 20, 9), 30, "Old")                       # previous week
    add_session(state, at(2026, 10, 26, 9), 50, "Write report", 10, ["email", "Email "])
    add_session(state, at(2026, 10, 26, 14), 25, "Code review", notes=["phone"])
    add_session(state, at(2026, 10, 28, 8, 30), 60, "Write report")
    add_session(state, at(2026, 10, 30, 19), 40, "Reading", notes=["phone", "email"])
    timer.log_distraction(state, at(2026, 10, 31, 11), "news")               # standalone
    add_session(state, at(2026, 11, 2, 9), 45, "Next week")                   # next week
    return state


def test_format_duration():
    assert reports.format_duration(0) == "0s"
    assert reports.format_duration(59) == "59s"
    assert reports.format_duration(60) == "1m"
    assert reports.format_duration(59 * 60 + 59) == "59m"
    assert reports.format_duration(3600) == "1h 00m"
    assert reports.format_duration(2 * 3600 + 5 * 60) == "2h 05m"


def test_time_blocks_cover_every_hour():
    names = [reports.time_block(h) for h in range(24)]
    assert names[4] == "Night" and names[5] == "Morning"
    assert names[12] == "Afternoon" and names[17] == "Evening" and names[22] == "Night"


def test_history_lists_oldest_first_with_focus_and_distractions():
    rows, total = reports.history_rows(sample_state())
    assert total == 6
    assert [r["id"] for r in rows] == [1, 2, 3, 4, 5, 6]
    second = rows[1]
    assert second["task"] == "Write report"
    assert second["focused"] == 50 * 60 and second["paused"] == 10 * 60
    assert [d["note"] for d in second["distractions"]] == ["email", "Email"]


def test_history_filters_and_limit():
    state = sample_state()
    rows, _ = reports.history_rows(state, task="write")
    assert [r["id"] for r in rows] == [2, 4]
    rows, total = reports.history_rows(state, since=date(2026, 10, 26), until=date(2026, 10, 28))
    assert [r["id"] for r in rows] == [2, 3, 4] and total == 3
    rows, total = reports.history_rows(state, limit=2)
    assert [r["id"] for r in rows] == [5, 6] and total == 6


def test_history_formatting():
    rows, total = reports.history_rows(sample_state(), limit=2)
    text = reports.format_history(rows, total, 6, details=True)
    assert "Reading" in text and "Fri 30 Oct" in text
    assert "19:02  phone" in text
    assert "Showing the 2 most recent of 6 sessions" in text
    assert "Total focused: 1h 25m across 2 sessions." in text
    assert reports.format_history([], 0, 0) == "No sessions recorded yet."
    assert reports.format_history([], 0, 3) == "No sessions match."


def test_week_bounds():
    assert reports.week_bounds(date(2026, 10, 26)) == (date(2026, 10, 26), date(2026, 11, 1))
    assert reports.week_bounds(date(2026, 11, 1)) == (date(2026, 10, 26), date(2026, 11, 1))


def test_weekly_totals_and_per_day():
    s = reports.weekly_summary(sample_state(), date(2026, 10, 29))
    assert s["sessions"] == 4
    assert s["focused"] == (50 + 25 + 60 + 40) * 60
    assert s["average"] == s["focused"] // 4
    assert s["distractions"] == 6  # five in sessions plus one standalone
    by_day = {d["date"]: d for d in s["days"]}
    assert len(by_day) == 7
    assert by_day[date(2026, 10, 26)]["focused"] == 75 * 60
    assert by_day[date(2026, 10, 26)]["sessions"] == 2
    assert by_day[date(2026, 10, 26)]["distractions"] == 3
    assert by_day[date(2026, 10, 27)] == {"date": date(2026, 10, 27), "focused": 0,
                                          "sessions": 0, "distractions": 0}
    assert by_day[date(2026, 10, 31)]["distractions"] == 1


def test_weekly_common_distractions_are_normalized_and_ranked():
    s = reports.weekly_summary(sample_state(), date(2026, 10, 26))
    assert s["common"] == [("email", 3), ("phone", 2), ("news", 1)]


def test_weekly_time_blocks_and_patterns():
    s = reports.weekly_summary(sample_state(), date(2026, 10, 26))
    blocks = {b["name"]: b for b in s["blocks"]}
    assert set(blocks) == {"Morning", "Afternoon", "Evening"}
    assert blocks["Morning"]["focused"] == 110 * 60 and blocks["Morning"]["sessions"] == 2
    assert blocks["Morning"]["distractions"] == 2
    assert blocks["Afternoon"]["per_hour"] == 1 * 3600 / (25 * 60)
    patterns = reports.focus_patterns(s)
    assert patterns[0] == "Most focused time this week was in the morning."
    assert "Longest sessions on average: morning (55m)." in patterns
    assert "Fewest distractions per focused hour: morning." in patterns
    assert "Most focused day: Mon 26 Oct (1h 15m)." in patterns


def test_empty_week():
    s = reports.weekly_summary(store.empty_state(), date(2026, 11, 2))
    assert s["sessions"] == 0 and s["focused"] == 0 and s["distractions"] == 0
    assert s["common"] == [] and s["blocks"] == []
    text = reports.format_week(s)
    assert "No sessions recorded this week." in text
    assert "Week of Mon 2 Nov - Sun 8 Nov 2026" in text


def test_week_report_is_neutral():
    state = sample_state()
    text = reports.format_week(reports.weekly_summary(state, date(2026, 10, 26))).lower()
    for word in ("streak", "fail", "missed", "goal", "target", "score", "grade", "should"):
        assert word not in text, word
    assert "  tue 27 oct        -\n" in text
