"""Real subprocess behaviour of AdbRunner, using the Python interpreter as a stand-in executable."""

import sys

import pytest

from monkey_api.adapters.adb.runner import AdbResult, AdbRunner, LoggingAdb, classify_failure, run_checked
from monkey_api.core.errors import AdbError, AdbTimeout, AdbUnavailable, DeviceNotFound, DeviceOffline
from monkey_api.core.logging import LogQuery, LogStore, configure_logging

PY = AdbRunner(sys.executable, default_timeout=10)


async def test_run_captures_stdout_stderr_and_exit_code() -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    result = await PY.run(["-c", code])
    assert (result.exit_code, result.stdout.strip(), result.stderr.strip()) == (3, "out", "err")
    assert result.args == ("-c", code)


async def test_arguments_are_not_interpreted_by_a_shell() -> None:
    result = await PY.run(["-c", "import sys; print(sys.argv[1])", "a; echo injected && dir"])
    assert result.stdout.strip() == "a; echo injected && dir"


async def test_timeout_kills_process() -> None:
    with pytest.raises(AdbTimeout):
        await PY.run(["-c", "import time; time.sleep(30)"], timeout=0.5)


async def test_missing_executable_is_adb_unavailable() -> None:
    with pytest.raises(AdbUnavailable):
        await AdbRunner("Z:/definitely/missing/adb.exe").run(["version"])


async def test_stream_lines_and_terminate() -> None:
    code = "import time\nfor i in range(3): print(f'line{i}', flush=True)\ntime.sleep(30)"
    stream = await PY.stream(["-c", code])
    got = []
    async for line in stream.lines():
        got.append(line)
        if len(got) == 3:
            break
    assert got == ["line0", "line1", "line2"]
    assert await stream.terminate(grace_s=2) is not None


async def test_stream_drains_large_stderr_without_blocking_completion() -> None:
    stream = await PY.stream(["-c", "import sys; sys.stderr.write('x'*200000); print('done', flush=True)"])
    assert [line async for line in stream.lines()] == ["done"]
    assert await stream.wait() == 0
    assert len(await stream.stderr_text()) == 4096
    assert await stream.terminate() == 0


async def test_logging_decorator_records_ok_failed_and_errors() -> None:
    store = LogStore()
    configure_logging(store, "WARNING")
    adb = LoggingAdb(PY)
    await adb.run(["-c", "pass"])
    await adb.run(["-c", "import sys; sys.exit(2)"])
    with pytest.raises(AdbTimeout):
        await adb.run(["-c", "import time; time.sleep(5)"], timeout=0.3)
    messages = [(r.level, r.message) for r in store.query(LogQuery(source="adb", limit=0))]
    assert messages == [
        ("INFO", "adb command ok"),
        ("WARNING", "adb command failed"),
        ("ERROR", "adb command error: adb_timeout"),
    ]
    with pytest.raises(AdbError):
        await run_checked(adb, ["-c", "import sys; sys.exit(1)"])


def test_classify_failure() -> None:
    def r(err: str) -> AdbResult:
        return AdbResult((), 1, "", err, 1)

    assert isinstance(classify_failure(r("error: device 'X1' not found"), "X1"), DeviceNotFound)
    assert isinstance(classify_failure(r("error: device offline"), "X1"), DeviceOffline)
    assert isinstance(classify_failure(r("error: no devices/emulators found"), None), DeviceOffline)
    assert type(classify_failure(r("boom"), None)) is AdbError
