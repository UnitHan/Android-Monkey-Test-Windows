"""Detect crash / ANR / native crash blocks for one package in `logcat -v threadtime` lines.

Fixes legacy detection, which required the package name on the *same* line as the keyword
(`FATAL EXCEPTION: main` never contains it) and silently dropped blocks shorter than 20 lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from monkey_api.domain.models import IssueKind

_THREADTIME = re.compile(r"^\d\d-\d\d\s+[\d:.]+\s+(\d+)\s+(\d+)\s+([VDIWEFA])\s+(.+?)\s*:\s?(.*)$")
_MAX_LINES = 40
_MAX_GAP = 30  # unrelated interleaved lines tolerated before a block is closed


@dataclass(frozen=True, slots=True)
class LogcatLine:
    pid: int
    level: str
    tag: str
    message: str
    raw: str


@dataclass(frozen=True, slots=True)
class DetectedIssue:
    kind: IssueKind
    summary: str
    lines: tuple[str, ...]


def parse_threadtime(raw: str) -> LogcatLine | None:
    m = _THREADTIME.match(raw)
    if not m:
        return None
    return LogcatLine(int(m.group(1)), m.group(3), m.group(4).strip(), m.group(5), raw)


@dataclass(slots=True)
class _Block:
    kind: IssueKind
    tag: str
    pid: int
    lines: list[str] = field(default_factory=list)
    confirmed: bool = False
    summary: str = ""


class LogcatAnalyzer:
    """Stateful, line-by-line. `feed()` returns issues completed by that line; call `flush()` at end."""

    def __init__(self, package: str) -> None:
        self.package = package
        self._block: _Block | None = None
        self._gap = 0

    def feed(self, raw: str) -> list[DetectedIssue]:
        line = parse_threadtime(raw.rstrip("\r\n"))
        if line is None:
            return []
        done: list[DetectedIssue] = []
        if self._block is None:
            self._block = self._start(line)
        elif self._continues(line):
            self._append(line)
            self._gap = 0
        elif (new_block := self._start(line)) is not None:
            done += self._close()
            self._block = new_block
        else:
            self._gap += 1
            if self._gap >= _MAX_GAP:
                done += self._close()
        if self._block and len(self._block.lines) >= _MAX_LINES:
            done += self._close()
        return done

    def flush(self) -> list[DetectedIssue]:
        return self._close()

    # --- block lifecycle ---

    def _start(self, line: LogcatLine) -> _Block | None:
        msg = line.message
        if line.tag == "AndroidRuntime" and msg.startswith("FATAL EXCEPTION"):
            return _Block("crash", line.tag, line.pid, [line.raw])
        if line.tag == "ActivityManager" and msg.startswith("ANR in "):
            block = _Block("anr", line.tag, line.pid, [line.raw])
            target = msg.removeprefix("ANR in ").split()[0]
            block.confirmed = target == self.package or target.startswith(self.package + ":")
            block.summary = msg
            return block
        if line.tag == "DEBUG" and "*** *** ***" in msg:
            return _Block("native_crash", line.tag, line.pid, [line.raw])
        return None

    def _continues(self, line: LogcatLine) -> bool:
        block = self._block
        return block is not None and line.tag == block.tag and line.pid == block.pid

    def _append(self, line: LogcatLine) -> None:
        block = self._block
        assert block is not None
        block.lines.append(line.raw)
        msg = line.message
        if block.kind == "crash" and msg.startswith("Process:"):
            proc = msg.removeprefix("Process:").split(",")[0].strip()
            block.confirmed = proc == self.package or proc.startswith(self.package + ":")
        elif block.kind == "crash" and not block.summary and block.confirmed and not msg.startswith("PID"):
            block.summary = msg.strip()
        elif block.kind == "native_crash" and f">>> {self.package}" in msg:
            block.confirmed = True
        elif block.kind == "native_crash" and msg.startswith("signal ") and not block.summary:
            block.summary = msg.strip()

    def _close(self) -> list[DetectedIssue]:
        block, self._block = self._block, None
        self._gap = 0
        if block is None or not block.confirmed:
            return []
        summary = block.summary or {"crash": "Java crash", "anr": "ANR", "native_crash": "Native crash"}[block.kind]
        return [DetectedIssue(block.kind, summary, tuple(block.lines))]
