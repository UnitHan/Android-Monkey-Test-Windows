"""Event-driven foreground recovery with one bounded queue and one recovery worker."""

import asyncio
import time
from collections.abc import Callable

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.foreground_events import resumed_package
from monkey_api.adapters.adb.runner import AdbStream
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import log

EventSink = Callable[[str, dict[str, object]], None]
COOLDOWN_S = 0.5
RECONNECT_S = 2.0


async def _read(stream: AdbStream, queue: asyncio.Queue[str]) -> None:
    async for line in stream.lines():
        if package := resumed_package(line):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(package)
        await asyncio.sleep(0)  # buffered log bursts must not starve the recovery worker
    raise AdbError("foreground event stream ended")


async def _recover(ops: DeviceOps, serial: str, package: str, sink: EventSink) -> bool:
    # Check only on a resume event (or stream startup), not on a polling timer.
    # Old events and transient overlays must not cause unwanted launcher navigation.
    foreground = await ops.foreground_package(serial)
    if foreground is None or foreground == package:
        return False
    started = time.monotonic()
    await ops.launch(serial, package)
    confirmed = await ops.foreground_package(serial) == package
    data = {
        "action": "relaunch",
        "foreground": foreground,
        "trigger": "activity_event",
        "confirmed": confirmed,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
    sink("guard", data)
    log("session", "foreground recovery requested", "INFO" if confirmed else "WARNING", **data)
    return True


async def _work(ops: DeviceOps, serial: str, package: str, queue: asyncio.Queue[str], sink: EventSink) -> None:
    next_allowed = 0.0
    while True:
        foreground = await queue.get()
        if foreground == package:
            continue
        await asyncio.sleep(max(0, next_allowed - time.monotonic()))
        if not queue.empty():
            foreground = queue.get_nowait()
        if foreground == package:
            continue
        try:
            if await _recover(ops, serial, package, sink):
                next_allowed = time.monotonic() + COOLDOWN_S
        except AdbError as exc:
            next_allowed = time.monotonic() + RECONNECT_S
            sink("guard", {"action": "relaunch_failed", "code": exc.code})
            log("session", "foreground recovery failed", "WARNING", code=exc.code)


async def _watch(ops: DeviceOps, serial: str, package: str, sink: EventSink) -> None:
    stream = await ops.foreground_events(serial)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    queue.put_nowait("")  # one initial snapshot also covers an already-backgrounded app
    tasks = [asyncio.create_task(_work(ops, serial, package, queue, sink)), asyncio.create_task(_read(stream, queue))]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await stream.terminate(grace_s=2)


async def guard_foreground(ops: DeviceOps, serial: str, package: str, sink: EventSink) -> None:
    while True:
        try:
            await _watch(ops, serial, package, sink)
        except AdbError as exc:
            sink("guard", {"action": "foreground_stream_unavailable", "code": exc.code})
            log("session", "foreground event stream unavailable; reconnecting", "WARNING", code=exc.code)
            await asyncio.sleep(RECONNECT_S)
