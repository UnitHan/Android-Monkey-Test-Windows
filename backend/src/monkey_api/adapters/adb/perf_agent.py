"""AppkiumPerf protocol 1 adapter. One dex agent + heartbeat stream per run."""

import asyncio
import json
import math
import shlex
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from monkey_api.adapters.adb.runner import AdbPort, AdbStream, run_checked
from monkey_api.core.errors import AdbError
from monkey_api.core.ids import utc_now
from monkey_api.domain.models import PerfSample

MAIN_CLASS = "com.qabulls.appkium.agent.Main"
JAR_PATH = Path(__file__).resolve().parents[2] / "data" / "appkium-android.jar"


def number(data: dict, key: str) -> float | None:
    value = data.get(key)
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        else None
    )


def parse_sample(data: dict, run: int) -> PerfSample:
    running = data.get("running") is True
    cores = number(data, "cores")
    cpu = number(data, "appCpu") if running else None
    pss = number(data, "pssKb") if running else None
    rss = number(data, "rssKb") if running else None
    battery = data.get("battery") if isinstance(data.get("battery"), dict) else {}
    return PerfSample(
        at=utc_now(),
        run=run,
        source="appkium",
        running=running,
        foreground=data.get("foreground") is True,
        memory_mb=pss / 1024 if pss is not None else None,
        rss_mb=rss / 1024 if rss is not None else None,
        cpu_percent=cpu * cores if cpu is not None and cores and cores > 0 else None,
        cpu_total_percent=cpu,
        cpu_cores=int(cores) if cores and cores > 0 else None,
        fps=number(data, "fps") if running else None,
        jank_count=data.get("jank") if running else None,
        frame_time_max_ms=number(data, "frameMaxMs") if running else None,
        threads=data.get("threads") if running else None,
        battery_temp_c=number(battery, "tempC"),
        device_cpu_percent=number(data, "sysCpu"),
        sample_cost_ms=number(data, "costMs"),
    )


class PerfAgent:
    def __init__(self, adb: AdbPort, serial: str, package: str, interval_s: float) -> None:
        self.adb, self.serial, self.package = adb, serial, package
        self.interval_ms = max(500, round(interval_s * 1000))
        self.remote = f"/data/local/tmp/monkey-perf-{uuid.uuid4().hex}.jar"
        self.pid: int | None = None

    async def _start(self) -> AdbStream:
        if not JAR_PATH.is_file():
            raise AdbError("Appkium performance collector jar is missing")
        await run_checked(self.adb, ["push", str(JAR_PATH), self.remote], serial=self.serial, timeout=20)
        await run_checked(self.adb, ["shell", "chmod", "444", self.remote], serial=self.serial)
        command = shlex.join(
            [
                "env",
                f"CLASSPATH={self.remote}",
                "app_process",
                "/",
                MAIN_CLASS,
                "monitor",
                "--package",
                self.package,
                "--interval",
                str(self.interval_ms),
            ]
        )
        return await self.adb.stream(["shell", command], serial=self.serial)

    async def _heartbeat(self, stream: AdbStream) -> None:
        while True:
            await stream.write_stdin(b"\n")
            await asyncio.sleep(1)

    async def _read(self, stream: AdbStream, run: int, sink: Callable[[PerfSample], None]) -> None:
        lines = aiter(stream.lines())
        hello = False
        deadline = time.monotonic() + 10
        while True:
            try:
                line = await asyncio.wait_for(anext(lines), max(0, deadline - time.monotonic()))
            except (StopAsyncIteration, TimeoutError) as exc:
                raise AdbError("performance collector stream stopped responding") from exc
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("type") == "hello":
                if data.get("protocol") != 1 or data.get("package") != self.package:
                    raise AdbError("unsupported performance collector protocol/package")
                pid = data.get("pid")
                if not isinstance(pid, int) or pid <= 0:
                    raise AdbError("performance collector returned invalid PID")
                self.pid, hello = pid, True
                deadline = time.monotonic() + 30
            elif data.get("type") == "sample" and hello:
                sink(parse_sample(data, run))
                deadline = time.monotonic() + 30
            elif data.get("type") == "error":
                raise AdbError("performance collector reported an error", agent_code=data.get("code"))

    async def _cleanup(self, stream: AdbStream | None) -> None:
        if stream is not None:
            await stream.terminate(grace_s=2)  # EOF + heartbeat watchdog also stop the device agent
        if self.pid:
            result = await self.adb.run(
                ["shell", "cat", f"/proc/{self.pid}/cmdline"], serial=self.serial, timeout=3, quiet=True
            )
            if result.exit_code == 0 and MAIN_CLASS in result.stdout:
                await self.adb.run(["shell", "kill", str(self.pid)], serial=self.serial, timeout=3, quiet=True)
        await self.adb.run(["shell", "rm", "-f", self.remote], serial=self.serial, timeout=3, quiet=True)

    async def collect(self, run: int, sink: Callable[[PerfSample], None]) -> None:
        stream = None
        tasks = []
        try:
            stream = await self._start()
            tasks = [asyncio.create_task(self._heartbeat(stream)), asyncio.create_task(self._read(stream, run, sink))]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._cleanup(stream)
