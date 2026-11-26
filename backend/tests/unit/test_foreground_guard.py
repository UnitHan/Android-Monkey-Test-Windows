import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fakes import FakeStream, fixture, healthy_device

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.foreground_events import resumed_package
from monkey_api.adapters.adb.parsers import parse_launcher_component
from monkey_api.core.errors import AdbError
from monkey_api.services import foreground_guard


def test_resume_parser_from_actual_device():
    packages = [resumed_package(line) for line in fixture("foreground_events.txt").splitlines()]
    assert packages[0] == "com.lguplus.aicallagent"
    assert "com.android.chrome" in packages
    assert packages[-1] == "com.samsung.android.messaging"
    assert resumed_package("I/Other( 12): [0,com.other/.MainActivity,reason]") is None
    assert resumed_package("invalid") is None


def test_launcher_component_from_actual_device():
    output = fixture("resolve_ixio_activity.txt")
    assert parse_launcher_component(output, "com.lguplus.aicallagent") == "com.lguplus.aicallagent/.MainActivity"
    assert parse_launcher_component(output, "com.other") is None
    assert parse_launcher_component("No activity found", "com.other") is None


async def test_recovery_is_event_driven_and_cleans_up_tasks():
    lines = [fixture("foreground_events.txt").splitlines()[2]]
    stream = FakeStream(lines, delay_s=0.02, hold=True)
    ops = SimpleNamespace(
        foreground_events=AsyncMock(return_value=stream),
        foreground_package=AsyncMock(side_effect=["target", "com.android.chrome", "target"]),
        launch=AsyncMock(),
    )
    events = []
    before = asyncio.all_tasks()
    task = asyncio.create_task(foreground_guard.guard_foreground(ops, "S", "target", lambda k, d: events.append(d)))
    try:
        async with asyncio.timeout(1):
            while not events:
                await asyncio.sleep(0.005)
        assert events[0]["confirmed"] is True
        ops.launch.assert_awaited_once_with("S", "target")
        assert ops.foreground_package.await_count == 3
        await asyncio.sleep(0.06)
        assert ops.foreground_package.await_count == 3  # idle stream makes no periodic dumpsys calls
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert stream._terminated.is_set()
    assert not (asyncio.all_tasks() - before)


async def test_stale_event_does_not_relaunch_target():
    ops = SimpleNamespace(foreground_package=AsyncMock(return_value="target"), launch=AsyncMock())
    assert not await foreground_guard._recover(ops, "S", "target", lambda *_: None)
    ops.launch.assert_not_awaited()


async def test_event_flood_retains_only_latest_and_terminates():
    lines = fixture("foreground_events.txt").splitlines()
    queue = asyncio.Queue(maxsize=1)
    stream = FakeStream(lines * 100)
    with pytest.raises(AdbError, match="stream ended"):
        await foreground_guard._read(stream, queue)
    assert queue.qsize() == 1
    assert queue.get_nowait() == "com.samsung.android.messaging"


async def test_failed_launch_is_observable_and_worker_survives():
    ops = SimpleNamespace(
        foreground_package=AsyncMock(return_value="other"), launch=AsyncMock(side_effect=AdbError("offline"))
    )
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait("other")
    events = []
    task = asyncio.create_task(foreground_guard._work(ops, "S", "target", queue, lambda k, d: events.append(d)))
    try:
        async with asyncio.timeout(1):
            while not events:
                await asyncio.sleep(0)
        assert events[0]["action"] == "relaunch_failed"
        assert not task.done()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_stream_reconnects_without_polling(monkeypatch):
    monkeypatch.setattr(foreground_guard, "RECONNECT_S", 0.01)
    streams = [FakeStream([]), FakeStream([], hold=True)]
    ops = SimpleNamespace(
        foreground_events=AsyncMock(side_effect=streams),
        foreground_package=AsyncMock(return_value="target"),
        launch=AsyncMock(),
    )
    events = []
    task = asyncio.create_task(foreground_guard.guard_foreground(ops, "S", "target", lambda k, d: events.append(d)))
    try:
        async with asyncio.timeout(1):
            while ops.foreground_events.await_count < 2:
                await asyncio.sleep(0.005)
        assert events[0]["action"] == "foreground_stream_unavailable"
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert all(s._terminated.is_set() for s in streams)


async def test_launch_uses_activity_manager_and_detects_launcher_error():
    adb = healthy_device()
    await DeviceOps(adb).launch("S", "com.example.app")
    assert adb.called("shell", "am", "start") == 1
    assert adb.called("shell", "monkey") == 0
    adb.on("shell", "am", "start", reply="Error: Activity not started, unable to resolve Intent")
    with pytest.raises(AdbError):
        await DeviceOps(adb).launch("S", "com.example.app")
