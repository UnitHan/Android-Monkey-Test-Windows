"""Retry the device agent twice, then preserve measurement with an explicit fallback."""

import asyncio
from collections.abc import Callable

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.perf_agent import PerfAgent
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import log
from monkey_api.domain.models import PerfSample
from monkey_api.services.collectors import sample_performance


async def collect_performance(
    ops: DeviceOps,
    serial: str,
    package: str,
    run: int,
    interval_s: float,
    on_sample: Callable[[PerfSample], None],
    on_event: Callable[[str, dict[str, object]], None],
) -> None:
    connected = False

    def receive(sample: PerfSample) -> None:
        nonlocal connected
        if not connected:
            on_event("collector", {"source": "appkium", "state": "connected"})
            connected = True
        on_sample(sample)

    for attempt in range(3):
        try:
            connected = False
            on_event("collector", {"source": "appkium", "state": "connecting", "attempt": attempt + 1})
            await PerfAgent(ops.adb, serial, package, interval_s).collect(run, receive)
        except (AdbError, OSError, ValueError) as exc:
            log("session", "performance agent disconnected", "WARNING", attempt=attempt + 1, error=str(exc))
            on_event("collector", {"source": "appkium", "state": "disconnected", "attempt": attempt + 1})
            if attempt < 2:
                await asyncio.sleep(1 + attempt)
    on_event("collector", {"source": "adb", "state": "fallback"})
    log("session", "performance collection using adb fallback", "WARNING")
    await sample_performance(ops, serial, package, run, interval_s, on_sample)
