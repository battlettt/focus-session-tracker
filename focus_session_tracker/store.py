"""Local JSON storage. Data never leaves the user's machine.

Location, in order of precedence:
1. an explicit path (the CLI's --data flag)
2. the FOCUS_DATA_FILE environment variable
3. $XDG_DATA_HOME/focus-session-tracker/sessions.json
4. ~/.local/share/focus-session-tracker/sessions.json
"""

import json
import os
from pathlib import Path

FORMAT_VERSION = 1
ENV_VAR = "FOCUS_DATA_FILE"


class StoreError(Exception):
    """The data file exists but cannot be read as tracker data."""


def empty_state():
    return {
        "version": FORMAT_VERSION,
        "next_id": 1,
        "active": None,
        "sessions": [],
        "distractions": [],
    }


def default_path(env=None):
    env = os.environ if env is None else env
    if env.get(ENV_VAR):
        return Path(env[ENV_VAR]).expanduser()
    base = env.get("XDG_DATA_HOME") or os.path.join(Path.home(), ".local", "share")
    return Path(base) / "focus-session-tracker" / "sessions.json"


def load(path):
    """Read state from path. A missing or empty file gives an empty state."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return empty_state()
    except OSError as exc:
        raise StoreError(f"Could not read {path}: {exc}") from exc
    if not text.strip():
        return empty_state()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoreError(
            f"{path} is not valid JSON ({exc}). It was left untouched; "
            "fix or move it to start fresh."
        ) from exc
    if not isinstance(data, dict):
        raise StoreError(f"{path} does not contain tracker data. It was left untouched.")
    state = empty_state()
    state.update(data)
    if not isinstance(state["sessions"], list) or not isinstance(state["distractions"], list):
        raise StoreError(f"{path} has an unexpected layout. It was left untouched.")
    known_ids = [s["id"] for s in state["sessions"]]
    if state["active"]:
        known_ids.append(state["active"]["id"])
    state["next_id"] = max([state["next_id"], *[i + 1 for i in known_ids]])
    return state


def save(path, state):
    """Write state atomically (temp file + rename) so a crash cannot truncate it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
