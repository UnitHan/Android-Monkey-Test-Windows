"""FakeAdb: scripted AdbPort for tests. No device, deterministic, records every call."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from monkey_api.adapters.adb.runner import AdbResult

FIXTURES = Path(__file__).parent / "fixtures" / "adb"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


Reply = AdbResult | str | Callable[[tuple[str, ...], str | None], AdbResult | str]


def ok(stdout: str = "") -> AdbResult:
    return AdbResult(args=(), exit_code=0, stdout=stdout, stderr="", duration_ms=1)


def fail(stderr: str, code: int = 1) -> AdbResult:
    return AdbResult(args=(), exit_code=code, stdout="", stderr=stderr, duration_ms=1)


@dataclass
class FakeStream:
    lines_: list[str]
    delay_s: float = 0.0
    hold: bool = False  # keep stream open after lines until terminated (logcat-like)
    exit_code: int = 0
    stderr: str = ""
    pid: int | None = 4242
    _terminated: asyncio.Event = field(default_factory=asyncio.Event)

    async def lines(self) -> AsyncIterator[str]:
        for line in self.lines_:
            if self._terminated.is_set():
                return
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            yield line
        if self.hold:
            await self._terminated.wait()

    async def stderr_text(self) -> str:
        return self.stderr

    async def wait(self) -> int:
        return self.exit_code

    async def terminate(self, grace_s: float = 5.0) -> int | None:
        self._terminated.set()
        return self.exit_code


@dataclass
class FakeAdb:
    """Rules match on an argument prefix; the most recently registered match wins."""

    rules: dict[tuple[str, ...], Reply] = field(default_factory=dict)
    streams: dict[tuple[str, ...], Callable[[], FakeStream]] = field(default_factory=dict)
    calls: list[tuple[tuple[str, ...], str | None]] = field(default_factory=list)
    default: Reply = field(default_factory=lambda: ok(""))

    def on(self, *prefix: str, reply: Reply) -> FakeAdb:
        self.rules.pop(tuple(prefix), None)  # re-registering moves the rule to the end
        self.rules[tuple(prefix)] = reply
        return self

    def on_stream(self, *prefix: str, factory: Callable[[], FakeStream]) -> FakeAdb:
        self.streams.pop(tuple(prefix), None)
        self.streams[tuple(prefix)] = factory
        return self

    @staticmethod
    def _match(table: dict, args: tuple[str, ...]):  # type: ignore[type-arg]
        """The most recently registered matching prefix wins (tests override healthy defaults)."""
        for prefix in reversed(table):
            if args[: len(prefix)] == prefix:
                return table[prefix]
        return None

    async def run(
        self, args: Sequence[str], serial: str | None = None, timeout: float | None = None, quiet: bool = False
    ) -> AdbResult:
        key = tuple(args)
        self.calls.append((key, serial))
        reply = self._match(self.rules, key)
        reply = self.default if reply is None else reply
        if callable(reply):
            reply = reply(key, serial)
        if isinstance(reply, str):
            reply = ok(reply)
        return AdbResult(key, reply.exit_code, reply.stdout, reply.stderr, reply.duration_ms)

    async def stream(self, args: Sequence[str], serial: str | None = None) -> FakeStream:
        key = tuple(args)
        self.calls.append((key, serial))
        factory = self._match(self.streams, key)
        return factory() if factory else FakeStream([], hold=False)

    def called(self, *prefix: str) -> int:
        return sum(1 for args, _ in self.calls if args[: len(prefix)] == prefix)


SERIAL = "R3CN30ABCDE"
PACKAGE = "com.example.app"


def healthy_device() -> FakeAdb:
    """A connected Galaxy S21 with com.example.app installed and running."""
    adb = FakeAdb()
    adb.on("version", reply="Android Debug Bridge version 1.0.41\nVersion 36.0.0")
    adb.on("devices", "-l", reply=fixture("devices_l.txt"))
    adb.on("shell", "getprop", "ro.product.model", reply="SM-G991N\n")
    adb.on("shell", "getprop", "ro.build.version.release", reply="14\n")
    adb.on("shell", "getprop", "ro.build.version.sdk", reply="34\n")
    adb.on("shell", "echo", "ok", reply="ok\n")
    adb.on(
        "shell", "pm", "list", "packages",
        reply="package:com.example.app\npackage:com.android.settings\npackage:com.sec.imslogger\n",
    )  # fmt: skip
    adb.on("shell", "dumpsys", "package", reply=fixture("dumpsys_package.txt"))
    adb.on("shell", "dumpsys", "meminfo", reply=fixture("meminfo_android14.txt"))
    adb.on("shell", "dumpsys", "activity", "activities", reply=fixture("activity_activities.txt"))
    adb.on("shell", "pidof", reply="11509\n")
    adb.on("shell", "top", reply=fixture("top.txt").replace("11509", "11509"))
    adb.on("shell", "settings", "get", "global", "airplane_mode_on", reply="0\n")
    adb.on("shell", "settings", "get", "global", "mobile_data", reply="1\n")
    adb.on_stream("logcat", factory=lambda: FakeStream(fixture("logcat_crash.txt").splitlines(), hold=True))
    adb.on_stream(
        "shell", "monkey",
        factory=lambda: FakeStream(fixture("monkey_output.txt").splitlines(), delay_s=0.01),
    )  # fmt: skip
    return adb
