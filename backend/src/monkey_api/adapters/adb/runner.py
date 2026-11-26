"""Async ADB process runner. Argument lists only (no shell), typed errors, every call logged."""

from __future__ import annotations

import asyncio
import contextlib
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from monkey_api.core.errors import AdbError, AdbTimeout, AdbUnavailable, DeviceNotFound, DeviceOffline
from monkey_api.core.logging import log

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_STDERR_HEAD = 500


@dataclass(frozen=True, slots=True)
class AdbResult:
    args: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class AdbStream(Protocol):
    """A long-running adb process (monkey, logcat)."""

    pid: int | None

    def lines(self) -> AsyncIterator[str]: ...
    async def stderr_text(self) -> str: ...
    async def wait(self) -> int: ...
    async def write_stdin(self, data: bytes) -> None: ...
    async def terminate(self, grace_s: float = 5.0) -> int | None: ...


class AdbPort(Protocol):
    """What services need from ADB. Implemented by AdbRunner and tests' FakeAdb."""

    async def run(
        self, args: Sequence[str], serial: str | None = None, timeout: float | None = None, quiet: bool = False
    ) -> AdbResult: ...

    async def stream(self, args: Sequence[str], serial: str | None = None) -> AdbStream: ...


def classify_failure(result: AdbResult, serial: str | None) -> AdbError:
    text = (result.stderr or result.stdout).strip()
    lowered = text.lower()
    if "not found" in lowered and serial and serial in text:
        return DeviceNotFound(f"device '{serial}' not found", serial=serial)
    if "offline" in lowered or "no devices/emulators found" in lowered:
        return DeviceOffline(text or "device offline", serial=serial)
    return AdbError(text or f"adb exited with {result.exit_code}", exit_code=result.exit_code)


def _full_args(adb_path: str, args: Sequence[str], serial: str | None) -> list[str]:
    return [adb_path, *(["-s", serial] if serial else []), *args]


class _ProcessStream:
    def __init__(self, proc: asyncio.subprocess.Process, args: tuple[str, ...]) -> None:
        self._proc = proc
        self._args = args
        self.pid = proc.pid
        self._stderr = asyncio.create_task(self._read_stderr())

    async def lines(self) -> AsyncIterator[str]:
        assert self._proc.stdout is not None
        async for raw in self._proc.stdout:
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")

    async def _read_stderr(self) -> str:
        assert self._proc.stderr is not None
        head = bytearray()
        while chunk := await self._proc.stderr.read(8192):
            head.extend(chunk[: max(0, 4096 - len(head))])
        return head.decode("utf-8", errors="replace")

    async def stderr_text(self) -> str:
        return await self._stderr

    async def wait(self) -> int:
        return await self._proc.wait()

    async def write_stdin(self, data: bytes) -> None:
        if self._proc.stdin is None:
            raise AdbError("stream stdin is unavailable")
        try:
            self._proc.stdin.write(data)
            await self._proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise AdbError("stream stdin closed") from exc

    async def terminate(self, grace_s: float = 5.0) -> int | None:
        if self._proc.stdin is not None:
            self._proc.stdin.close()
        if self._proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._proc.terminate()
        try:
            return await asyncio.wait_for(self._proc.wait(), grace_s)
        except TimeoutError:
            self._proc.kill()
            log("adb", "stream killed after grace period", "WARNING", args=list(self._args))
            return await self._proc.wait()
        finally:
            await self._stderr


class AdbRunner:
    def __init__(self, adb_path: str, default_timeout: float = 30.0) -> None:
        self.adb_path = adb_path
        self.default_timeout = default_timeout

    async def run(
        self, args: Sequence[str], serial: str | None = None, timeout: float | None = None, quiet: bool = False
    ) -> AdbResult:
        full = _full_args(self.adb_path, args, serial)
        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *full, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=_NO_WINDOW
            )
        except FileNotFoundError as exc:
            raise AdbUnavailable(f"adb not found at '{self.adb_path}'") from exc
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout or self.default_timeout)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise AdbTimeout(f"adb {' '.join(args)} timed out", args=list(args)) from exc
        result = AdbResult(
            args=tuple(args),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return result

    async def stream(self, args: Sequence[str], serial: str | None = None) -> AdbStream:
        full = _full_args(self.adb_path, args, serial)
        try:
            proc = await asyncio.create_subprocess_exec(
                *full,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=_NO_WINDOW,
            )
        except FileNotFoundError as exc:
            raise AdbUnavailable(f"adb not found at '{self.adb_path}'") from exc
        return _ProcessStream(proc, tuple(args))


class LoggingAdb:
    """Decorator around any AdbPort: one `adb` API-log record per call (ok / failed / raised).

    Kept separate from AdbRunner so fakes and real runners are logged by the same code.
    """

    def __init__(self, inner: AdbPort) -> None:
        self.inner = inner

    async def run(
        self, args: Sequence[str], serial: str | None = None, timeout: float | None = None, quiet: bool = False
    ) -> AdbResult:
        base = {"args": list(args), "serial": serial}
        started = time.perf_counter()
        try:
            result = await self.inner.run(args, serial=serial, timeout=timeout, quiet=quiet)
        except AdbError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            log("adb", f"adb command error: {exc.code}", "ERROR", **base, duration_ms=elapsed, detail=exc.detail)
            raise
        data = {**base, "exit_code": result.exit_code, "duration_ms": result.duration_ms}
        if result.exit_code != 0:
            log("adb", "adb command failed", "WARNING", **data, stderr=(result.stderr or result.stdout)[:_STDERR_HEAD])
        else:
            log("adb", "adb command ok", "DEBUG" if quiet else "INFO", **data)
        return result

    async def stream(self, args: Sequence[str], serial: str | None = None) -> AdbStream:
        try:
            stream = await self.inner.stream(args, serial=serial)
        except AdbError as exc:
            log("adb", f"adb stream error: {exc.code}", "ERROR", args=list(args), serial=serial, detail=exc.detail)
            raise
        log("adb", "adb stream started", args=list(args), serial=serial, pid=stream.pid)
        return stream


async def run_checked(
    adb: AdbPort, args: Sequence[str], serial: str | None = None, timeout: float | None = None, quiet: bool = False
) -> str:
    """Run and raise a typed error on non-zero exit. Returns stdout."""
    result = await adb.run(args, serial=serial, timeout=timeout, quiet=quiet)
    if result.exit_code != 0:
        raise classify_failure(result, serial)
    return result.stdout
