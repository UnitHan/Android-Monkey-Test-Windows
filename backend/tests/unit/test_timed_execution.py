"""Execution regressions: early event exhaustion must extend the SAME run."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from fakes import FakeStream

from monkey_api.domain.estimation import MAX_MONKEY_EVENTS, extension_event_budget
from monkey_api.domain.models import EventMix, SessionConfig
from monkey_api.domain.presets import get_preset
from monkey_api.services import monkey_driver
from monkey_api.services.monkey_driver import MonkeyDriver


def driver(streams, target=0.005):
    calls, emitted, progress = [], [], []

    async def monkey(serial, args):
        calls.append(args)
        return streams[min(len(calls) - 1, len(streams) - 1)]

    ctx = SimpleNamespace(
        config=SessionConfig(
            device_serial="S",
            package="com.example.app",
            preset_id="custom",
            events=10,
            repeats=1,
            throttle_ms=1,
            seed_mode="fixed",
            seed=7,
            target_minutes_per_run=target,
            event_mix=EventMix(),
        ),
        stop=asyncio.Event(),
        session_id="audit",
        ops=SimpleNamespace(monkey=monkey),
        ledger=SimpleNamespace(
            emit=lambda _, kind, data: emitted.append((kind, data)),
            set_progress=lambda _, value: progress.append(value),
        ),
    )
    return MonkeyDriver(ctx, 1, 10, 7), calls, emitted, progress


async def test_exhaustion_extends_without_resetting_deadline_or_counts():
    first = FakeStream(["Events injected: 13", "// Monkey finished"], delay_s=0.08)
    second = FakeStream(["Events injected: 5"], hold=True)
    d, calls, emitted, progress = driver([first, second])
    result = await d.execute()
    assert result.reason == "time_limit"
    assert 0.29 <= result.duration_s < 0.42
    assert result.segments[1].duration_s < 0.22
    assert result.events_sent == 18
    assert len(calls) == len(result.segments) == 2
    assert int(calls[1][-1]) > int(calls[0][-1])
    assert [s.seed for s in result.segments] == [7, 8]
    assert [s.end_reason for s in result.segments] == ["completed", "time_limit"]
    assert first._terminated.is_set() and second._terminated.is_set()
    assert any(k == "run_extended" for k, _ in emitted)
    assert progress[-1].events_sent == 18 and progress[-1].run_percent == 100
    assert progress[-1].remaining_s == 0


async def test_event_based_run_does_not_extend():
    d, calls, _, _ = driver([FakeStream(["Events injected: 10"])], target=None)
    result = await d.execute()
    assert result.reason == "completed" and len(calls) == 1 and calls[0][-1] == "10"


@pytest.mark.parametrize(
    "lines,code,reason",
    [
        ([], 1, "failed_to_start"),
        (["Events injected: 4", "** Monkey aborted"], 0, "aborted"),
        (["Events injected: 4"], 1, "aborted"),
        (["// Sending event #4"], 0, "aborted"),
    ],
)
async def test_errors_are_not_hidden_by_restarting(lines, code, reason):
    d, calls, _, _ = driver([FakeStream(lines, exit_code=code)])
    result = await d.execute()
    assert result.reason == reason and len(calls) == 1


async def test_stop_during_extension_terminates_and_does_not_launch_more():
    first = FakeStream(["Events injected: 13"])
    second = FakeStream([], hold=True)
    d, calls, _, _ = driver([first, second], target=1)
    task = asyncio.create_task(d.execute())
    async with asyncio.timeout(2):
        while len(calls) < 2:
            await asyncio.sleep(0.005)
    d.ctx.stop.set()
    result = await task
    assert result.reason == "stopped" and len(calls) == 2
    assert second._terminated.is_set()


async def test_external_cancellation_cleans_stream_and_background_tasks():
    stream = FakeStream([], hold=True)
    d, calls, _, _ = driver([stream], target=1)
    before = asyncio.all_tasks()
    task = asyncio.create_task(d.execute())
    while not calls:
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream._terminated.is_set()
    assert not (asyncio.all_tasks() - before)


async def test_no_output_still_publishes_timer_progress():
    d, _, _, progress = driver([FakeStream([], hold=True)], target=0.02)
    result = await d.execute()
    assert result.reason == "time_limit"
    assert any(0 < p.run_percent < 100 for p in progress)


async def test_slow_launch_is_included_in_deadline():
    d, _, _, _ = driver([FakeStream([], hold=True)])

    async def slow_monkey(*args):
        await asyncio.sleep(10)
        raise AssertionError("launch must be cancelled")

    d.ctx.ops.monkey = slow_monkey
    started = time.monotonic()
    result = await d.execute()
    assert result.reason == "time_limit" and time.monotonic() - started < 0.6


def test_extension_budget_uses_speed_remaining_time_and_integer_cap():
    assert extension_event_budget(100, 100, 1, 9) == 1170
    assert extension_event_budget(100, 1, 10, 0.1) == 101
    assert extension_event_budget(MAX_MONKEY_EVENTS, 100, 0, 100) == MAX_MONKEY_EVENTS


async def test_smoke_five_runs_extend_to_1800_seconds_with_virtual_clock(monkeypatch):
    """Exercise real preset deadlines without driving a connected phone for 30 minutes."""
    now = [1000.0]
    monkeypatch.setattr(monkey_driver, "time", SimpleNamespace(monotonic=lambda: now[0]))
    preset = get_preset("smoke")
    assert preset is not None
    durations = []
    for run in range(1, preset.repeats + 1):
        d, _, emitted, progress = driver([], target=preset.target_minutes_per_run)
        d.ctx.config = d.ctx.config.model_copy(update={"events": preset.events, "throttle_ms": preset.throttle_ms})
        budgets = []

        async def monkey(serial, args, budgets=budgets):
            budgets.append(int(args[-1]))
            now[0] += 90  # each finite invocation exhausts its budget before the run deadline
            return FakeStream([f"Events injected: {args[-1]}", "// Monkey finished"])

        d.ctx.ops.monkey = monkey
        d = MonkeyDriver(d.ctx, run, preset.events, 7)
        result = await d.execute()
        durations.append(result.duration_s)
        assert result.reason == "time_limit" and result.duration_s == 360
        assert len(result.segments) == 4
        assert all(b > a for a, b in zip(budgets, budgets[1:], strict=False))
        assert result.events_sent == sum(budgets)
        assert sum(k == "run_extended" for k, _ in emitted) == 3
        assert progress[-1].remaining_s == 0
    assert sum(durations) == 1800
