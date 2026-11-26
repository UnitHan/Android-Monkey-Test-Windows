"""Own the remote Monkey PID: closing the PC adb pipe does not stop Android Monkey."""

import asyncio
import shlex
import uuid
from collections.abc import AsyncIterator

from monkey_api.adapters.adb.runner import AdbPort, AdbStream, run_checked
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import log


class MonkeyProcess:
    def __init__(self, adb: AdbPort, serial: str, stream: AdbStream, pid_file: str) -> None:
        self.adb, self.serial, self.stream, self.pid_file = adb, serial, stream, pid_file
        self.pid = stream.pid  # local adb PID, not the Android PID
        self.finished = False
        self.cleaned = False

    async def lines(self) -> AsyncIterator[str]:
        async for line in self.stream.lines():
            yield line

    async def stderr_text(self) -> str:
        return await self.stream.stderr_text()

    async def write_stdin(self, data: bytes) -> None:
        await self.stream.write_stdin(data)

    async def wait(self) -> int:
        code = await self.stream.wait()
        self.finished = True
        return code

    async def _remote_pid(self) -> int | None:
        for _ in range(10):
            result = await self.adb.run(["shell", "cat", self.pid_file], serial=self.serial, timeout=2, quiet=True)
            if result.exit_code == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip())
            if self.finished:
                return None
            await asyncio.sleep(0.1)  # only startup/cleanup race; not foreground polling
        raise AdbError("could not identify this run's remote Monkey; refusing to start another run")

    async def _stop_remote(self) -> None:
        pid = await self._remote_pid()
        if pid is None:
            return
        path = f"/proc/{pid}/cmdline"
        result = await self.adb.run(["shell", "cat", path], serial=self.serial, timeout=2, quiet=True)
        if result.exit_code != 0:
            return  # already exited
        name = result.stdout.replace("\x00", " ").strip()
        if name != "com.android.commands.monkey":
            if self.finished:
                return  # PID has already been reused by another process
            raise AdbError("remote PID identity changed; refusing to kill an unrelated process", pid=pid)
        await run_checked(self.adb, ["shell", "kill", "-9", str(pid)], serial=self.serial, timeout=2)
        for _ in range(10):
            result = await self.adb.run(["shell", "cat", path], serial=self.serial, timeout=2, quiet=True)
            if result.exit_code != 0 or result.stdout.replace("\x00", " ").strip() != name:
                log("session", "remote Monkey stopped", remote_pid=pid)
                return
            await asyncio.sleep(0.05)
        raise AdbError("remote Monkey did not stop; refusing to start another run", pid=pid)

    async def terminate(self, grace_s: float = 5.0) -> int | None:
        try:
            if not self.cleaned:
                await self._stop_remote()
                await self.adb.run(["shell", "rm", "-f", self.pid_file], serial=self.serial, timeout=2, quiet=True)
                self.cleaned = True
        finally:
            code = await self.stream.terminate(grace_s)
        return code


async def start_monkey(adb: AdbPort, serial: str, args: list[str]) -> AdbStream:
    if args[:2] != ["shell", "monkey"]:
        raise AdbError("invalid Monkey invocation")
    pid_file = f"/data/local/tmp/monkey-test-{uuid.uuid4().hex}.pid"
    # exec keeps the shell PID, so cleanup owns exactly this invocation. All arguments
    # are shell-quoted here because adb itself joins remote shell arguments with spaces.
    script = f"echo $$ > {shlex.quote(pid_file)}; exec {shlex.join(args[1:])}"
    command = shlex.join(["sh", "-c", script])
    stream = await adb.stream(["shell", command], serial=serial)
    return MonkeyProcess(adb, serial, stream, pid_file)
