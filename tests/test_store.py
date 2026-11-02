import os
from pathlib import Path

from focus_session_tracker import store, timer
from tests.helpers import at, temp_data_path


def test_missing_file_gives_empty_state():
    assert store.load(temp_data_path()) == store.empty_state()


def test_empty_or_blank_file_gives_empty_state():
    path = Path(temp_data_path())
    path.parent.mkdir(parents=True)
    for content in ("", "  \n"):
        path.write_text(content)
        assert store.load(path) == store.empty_state()


def test_round_trip_creates_parent_folders():
    path = temp_data_path()
    state = store.empty_state()
    timer.start_session(state, at(2026, 11, 2), "Read")
    timer.log_distraction(state, at(2026, 11, 2, 9, 5), "door")
    store.save(path, state)
    assert store.load(path) == state
    assert not os.path.exists(path + ".tmp")


def test_corrupt_file_raises_and_is_left_untouched():
    path = Path(temp_data_path())
    path.parent.mkdir(parents=True)
    for content in ("{not json", "[1, 2]", '{"sessions": 5}'):
        path.write_text(content)
        try:
            store.load(path)
        except store.StoreError as exc:
            assert "untouched" in str(exc)
        else:
            raise AssertionError(f"expected StoreError for {content!r}")
        assert path.read_text() == content


def test_next_id_is_repaired_from_existing_sessions():
    path = Path(temp_data_path())
    path.parent.mkdir(parents=True)
    path.write_text('{"sessions": [{"id": 7, "task": null, "start": "2026-11-02T09:00:00+01:00",'
                    ' "end": "2026-11-02T09:30:00+01:00", "pauses": []}]}')
    assert store.load(path)["next_id"] == 8


def test_default_path_precedence():
    assert store.default_path({"FOCUS_DATA_FILE": "/tmp/x.json", "XDG_DATA_HOME": "/xdg"}) == Path("/tmp/x.json")
    assert store.default_path({"XDG_DATA_HOME": "/xdg"}) == Path("/xdg/focus-session-tracker/sessions.json")
    home_default = store.default_path({})
    assert home_default == Path.home() / ".local/share/focus-session-tracker/sessions.json"
