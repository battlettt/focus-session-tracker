"""Shared test helpers: a fake clock and a temporary data file."""

import io
import os
import tempfile
from datetime import datetime, timedelta, timezone

from focus_session_tracker import cli

TZ = timezone(timedelta(hours=1))


def at(year, month, day, hour=9, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=TZ)


class FakeClock:
    """A clock that only moves when told to."""

    def __init__(self, start):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, minutes=0, seconds=0):
        self.now += timedelta(minutes=minutes, seconds=seconds)

    def set(self, moment):
        self.now = moment


def temp_data_path():
    folder = tempfile.mkdtemp(prefix="focus-test-")
    return os.path.join(folder, "nested", "sessions.json")


class Cli:
    """Runs CLI commands against one temp data file with a fake clock."""

    def __init__(self, clock, path=None):
        self.clock = clock
        self.path = path or temp_data_path()

    def run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(["--data", self.path, *argv], clock=self.clock, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        code, out, err = self.run(*argv)
        assert code == 0, (argv, code, err)
        return out
