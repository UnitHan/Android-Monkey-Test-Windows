"""Incremental parser for `monkey -v -v` stdout."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENDING_EVENT = re.compile(r"//\s*Sending event #(\d+)")
_INJECTED = re.compile(r"Events injected:\s*(\d+)")
_ABORTED = re.compile(r"\*\* Monkey aborted|monkey aborted", re.IGNORECASE)
_FINISHED = re.compile(r"//\s*Monkey finished", re.IGNORECASE)
_CRASH = re.compile(r"//\s*CRASH:\s*(\S+)")
_ANR = re.compile(r"//\s*NOT RESPONDING:\s*(\S+)")


@dataclass(slots=True)
class MonkeyOutputTracker:
    """Feed lines; read `events_sent`, `finished`, `aborted`, monkey-reported crash/anr counts."""

    events_sent: int = 0
    injected: int | None = None
    finished: bool = False
    aborted: bool = False
    reported_crashes: int = 0
    reported_anrs: int = 0
    lines_seen: int = 0

    def feed(self, line: str) -> None:
        self.lines_seen += 1
        if m := _SENDING_EVENT.search(line):
            self.events_sent = max(self.events_sent, int(m.group(1)))
        elif m := _INJECTED.search(line):
            self.injected = int(m.group(1))
            self.events_sent = max(self.events_sent, self.injected)
        elif _FINISHED.search(line):
            self.finished = True
        elif _ABORTED.search(line):
            self.aborted = True
        elif _CRASH.search(line):
            self.reported_crashes += 1
        elif _ANR.search(line):
            self.reported_anrs += 1
