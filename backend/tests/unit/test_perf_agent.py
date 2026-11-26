import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fakes import FakeStream, fixture, healthy_device

from monkey_api.adapters.adb.perf_agent import PerfAgent, parse_sample
from monkey_api.core.errors import AdbError
from monkey_api.services import performance_collector


def test_real_agent_sample_units_and_unavailable_values():
    records = [json.loads(s) for s in fixture("perf_agent.jsonl").splitlines()]
    raw = records[-1]
    sample = parse_sample(raw, 2)
    assert sample.source == "appkium" and sample.run == 2
    assert sample.memory_mb == raw["pssKb"] / 1024
    assert sample.cpu_percent == raw["appCpu"] * raw["cores"]
    assert sample.cpu_total_percent == raw["appCpu"]
    assert sample.fps == raw["fps"] and sample.running
    missing = parse_sample({**raw, "running": False}, 1)
    assert missing.memory_mb is missing.cpu_percent is missing.fps is None
    assert parse_sample({"running": True, "appCpu": float("nan")}, 1).cpu_percent is None


async def test_agent_cancellation_cleans_stream_tasks_and_jar():
    adb = healthy_device()
    agent = PerfAgent(adb, "S", "com.example.app", 1)
    samples = []
    before = asyncio.all_tasks()
    task = asyncio.create_task(agent.collect(1, samples.append))
    try:
        async with asyncio.timeout(1):
            while not samples:
                await asyncio.sleep(0.005)
        assert samples[-1].source == "appkium"
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not (asyncio.all_tasks() - before)
    assert adb.called("push") == 1
    assert adb.called("shell", "rm", "-f", agent.remote) == 1


async def test_protocol_mismatch_fails_instead_of_consuming_bad_values():
    agent = PerfAgent(healthy_device(), "S", "com.example.app", 1)
    stream = FakeStream([json.dumps({"type": "hello", "protocol": 99, "package": "com.example.app", "pid": 12})])
    with pytest.raises(AdbError, match="protocol"):
        await agent._read(stream, 1, lambda s: None)


async def test_retries_then_explicit_shell_fallback(monkeypatch):
    collect = AsyncMock(side_effect=AdbError("not supported"))
    fallback = AsyncMock()
    monkeypatch.setattr(PerfAgent, "collect", collect)
    monkeypatch.setattr(performance_collector, "sample_performance", fallback)
    monkeypatch.setattr(performance_collector, "asyncio", type("Clock", (), {"sleep": AsyncMock()})())
    events = []
    ops = type("Ops", (), {"adb": healthy_device()})()
    await performance_collector.collect_performance(
        ops, "S", "com.example.app", 1, 2, lambda s: None, lambda k, d: events.append(d)
    )
    assert collect.await_count == 3
    fallback.assert_awaited_once()
    assert events[-1] == {"source": "adb", "state": "fallback"}
