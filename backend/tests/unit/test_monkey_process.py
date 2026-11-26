import shlex
from unittest.mock import AsyncMock

import pytest
from fakes import FakeAdb, FakeStream, fail, ok

from monkey_api.adapters.adb.monkey_process import MonkeyProcess, start_monkey
from monkey_api.core.errors import AdbError


async def test_start_tracks_exact_exec_pid_and_quotes_arguments():
    stream = FakeStream([], hold=True)
    adb = AsyncMock()
    adb.stream.return_value = stream
    process = await start_monkey(adb, "S", ["shell", "monkey", "-p", "com.example.app", "-s", "7", "100"])
    args = adb.stream.call_args.args[0]
    assert args[0] == "shell"
    remote = shlex.split(args[1])
    assert remote[:2] == ["sh", "-c"]
    assert remote[2].startswith(f"echo $$ > {process.pid_file}; exec monkey ")
    assert process.pid_file.startswith("/data/local/tmp/monkey-test-")


async def test_terminate_kills_only_owned_remote_pid_before_local_pipe():
    adb, stream = FakeAdb(), FakeStream([], hold=True)
    pid_file = "/data/local/tmp/monkey-test-test.pid"
    adb.on("shell", "cat", pid_file, reply="123\n")
    alive = [True]
    adb.on(
        "shell",
        "cat",
        "/proc/123/cmdline",
        reply=lambda *_: ok("com.android.commands.monkey\0") if alive[0] else fail("gone"),
    )

    def kill(*_):
        assert not stream._terminated.is_set()
        alive[0] = False
        return ok()

    adb.on("shell", "kill", "-9", "123", reply=kill)
    process = MonkeyProcess(adb, "S", stream, pid_file)
    await process.terminate()
    await process.terminate()
    assert adb.called("shell", "kill", "-9", "123") == 1
    assert adb.called("shell", "rm", "-f", pid_file) == 1
    assert stream._terminated.is_set()


async def test_remote_stop_failure_propagates_and_local_stream_still_closes():
    adb, stream = FakeAdb(), FakeStream([], hold=True)
    adb.on("shell", "cat", "/test.pid", reply="123")
    adb.on("shell", "cat", "/proc/123/cmdline", reply="com.android.commands.monkey\0")
    adb.on("shell", "kill", reply=fail("permission denied"))
    with pytest.raises(AdbError, match="permission denied"):
        await MonkeyProcess(adb, "S", stream, "/test.pid").terminate()
    assert stream._terminated.is_set()
    assert adb.called("shell", "rm") == 0  # keep ownership evidence when cleanup fails


async def test_reused_pid_is_not_killed():
    adb, stream = FakeAdb(), FakeStream([])
    adb.on("shell", "cat", "/test.pid", reply="123")
    adb.on("shell", "cat", "/proc/123/cmdline", reply="unrelated.process\0")
    process = MonkeyProcess(adb, "S", stream, "/test.pid")
    with pytest.raises(AdbError, match="identity changed"):
        await process.terminate()
    assert adb.called("shell", "kill") == 0
    assert stream._terminated.is_set()


async def test_naturally_finished_remote_process_needs_no_kill():
    adb, stream = FakeAdb(), FakeStream([])
    adb.on("shell", "cat", "/test.pid", reply="123")
    adb.on("shell", "cat", "/proc/123/cmdline", reply=fail("No such file"))
    process = MonkeyProcess(adb, "S", stream, "/test.pid")
    await process.wait()
    await process.terminate()
    assert adb.called("shell", "kill") == 0
    assert process.cleaned
