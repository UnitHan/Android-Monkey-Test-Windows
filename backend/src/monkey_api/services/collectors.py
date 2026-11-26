"""Background loops that run alongside one monkey run: logcat, performance, guards.

Each loop is an async function cancelled by the run executor when the run ends.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.core.errors import AdbError
from monkey_api.core.ids import new_id, utc_now
from monkey_api.core.logging import log
from monkey_api.domain.logcat_analyzer import DetectedIssue, LogcatAnalyzer
from monkey_api.domain.models import Issue, PerfSample
from monkey_api.services.foreground_guard import guard_foreground

IssueSink = Callable[[Issue], None]
PerfSink = Callable[[PerfSample], None]


def _to_issue(found: DetectedIssue, run: int) -> Issue:
    return Issue(
        id=new_id("iss"), kind=found.kind, run=run, at=utc_now(), summary=found.summary, lines=list(found.lines)
    )


async def collect_logcat(ops: DeviceOps, serial: str, package: str, run: int, path: Path, on_issue: IssueSink) -> None:
    analyzer = LogcatAnalyzer(package)
    stream = await ops.logcat(serial)
    lines = 0
    try:
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            async for line in stream.lines():
                lines += 1
                fh.write(line + "\n")
                for found in analyzer.feed(line):
                    on_issue(_to_issue(found, run))
    finally:
        for found in analyzer.flush():
            on_issue(_to_issue(found, run))
        await stream.terminate(grace_s=2)
        log("session", "logcat collector stopped", "DEBUG", run=run, lines=lines, file=path.name)


async def sample_performance(
    ops: DeviceOps, serial: str, package: str, run: int, interval_s: float, on_sample: PerfSink
) -> None:
    samples = 0
    while True:
        try:
            pid = await ops.pid_of(serial, package)
            memory = await ops.memory_mb(serial, package)
            cpu = await ops.cpu_percent(serial, pid) if pid else None
            on_sample(PerfSample(at=utc_now(), run=run, memory_mb=memory, cpu_percent=cpu))
            samples += 1
        except AdbError as exc:
            log("session", "perf sample failed", "WARNING", run=run, error=exc.detail, code=exc.code)
        await asyncio.sleep(interval_s)


async def guard_app_state(
    ops: DeviceOps,
    serial: str,
    package: str,
    interval_s: float,
    keep_foreground: bool,
    network_guard: bool,
    on_event: Callable[[str, dict[str, object]], None],
) -> None:
    """Foreground uses resume events; network checks retain their separate interval."""
    tasks = []
    if keep_foreground:
        tasks.append(asyncio.create_task(guard_foreground(ops, serial, package, on_event)))
    if network_guard:
        tasks.append(asyncio.create_task(_guard_network(ops, serial, interval_s, on_event)))
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _guard_network(
    ops: DeviceOps, serial: str, interval_s: float, on_event: Callable[[str, dict[str, object]], None]
) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            if await ops.global_setting(serial, "airplane_mode_on"):
                await ops.disable_airplane_mode(serial)
                on_event("guard", {"action": "airplane_mode_disabled"})
            if await ops.global_setting(serial, "mobile_data") is False:
                await ops.enable_mobile_data(serial)
                on_event("guard", {"action": "mobile_data_enabled"})
        except AdbError as exc:
            log("session", "guard check failed", "WARNING", error=exc.detail, code=exc.code)
