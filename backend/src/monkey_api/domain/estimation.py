"""Timing model: how long monkey runs take, and the time rule for presets (pure functions).

Calibration
-----------
55 measured historical runs, preserved in tests/fixtures/calibration/legacy_tuning_runs.json, give

    run seconds ≈ events × throttle_ms / 1000 × EFFICIENCY      (median EFFICIENCY = 0.358)

i.e. monkey is *faster* than events × throttle. The legacy estimate divided by 0.35 instead
(~8x too long); legacy's own throttle calibration multiplied. We multiply.

Time rule
---------
A config with `target_minutes_per_run` runs against one monotonic deadline.
The first invocation gets HEADROOM × expected events. If its events finish early,
the driver starts another invocation using observed throughput and remaining time.
Errors and user stop can end a run early. Preparation and final cleanup are measured separately.
Total is an estimate: target × repeats + preparation. AI wait is not included.
Configs without a target are *event-based* and do not extend.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

EFFICIENCY = 0.36
HEADROOM = 1.3
MAX_MONKEY_EVENTS = 2_147_483_647
MIN_CYCLE_MS = 10  # throttle 0 still costs injection time per event
PREP_PER_RUN_S = 12  # force-stop, relaunch + 5 s load wait, logcat clear, 2 s gap between runs
FINALIZE_S = 5  # report generation
EVENT_BASED_BUFFER = 0.10  # measured efficiency spread (IQR) for event-based runs

EstimateMode = Literal["time", "events"]


class Estimate(BaseModel):
    mode: EstimateMode
    per_run_s: float
    per_run_events: int
    overhead_s: float
    buffer_s: float
    total_s: int


def _cycle_s(throttle_ms: int) -> float:
    return max(throttle_ms, MIN_CYCLE_MS) / 1000 * EFFICIENCY


def expected_run_s(events: int, throttle_ms: int) -> float:
    """Expected wall time of a monkey run that executes all `events`."""
    return events * _cycle_s(throttle_ms)


def expected_events(target_minutes: float, throttle_ms: int) -> int:
    """Events monkey is expected to execute in `target_minutes` at `throttle_ms`."""
    return round(target_minutes * 60 / _cycle_s(throttle_ms))


def monkey_event_budget(events: int, target_minutes_per_run: float | None) -> int:
    """Event count passed to monkey. Time-boxed runs get headroom so time, not events, ends them."""
    return math.ceil(events * HEADROOM) if target_minutes_per_run is not None else events


def extension_event_budget(previous_budget: int, events_sent: int, elapsed_s: float, remaining_s: float) -> int:
    """Grow a completed segment's budget using observed speed and remaining wall time.

    The deadline, not this estimate, decides when a time-based run ends. Clamp to
    Monkey's signed integer count; even at the cap another segment can follow.
    """
    rate = events_sent / max(elapsed_s, 0.001)
    return min(MAX_MONKEY_EVENTS, max(previous_budget + 1, math.ceil(rate * remaining_s * HEADROOM)))


def estimate_duration(
    events: int | None,
    repeats: int,
    throttle_ms: int,
    target_minutes_per_run: float | None = None,
) -> Estimate:
    if target_minutes_per_run is not None:
        per_run = target_minutes_per_run * 60
        per_run_events = expected_events(target_minutes_per_run, throttle_ms)
        mode: EstimateMode = "time"
    else:
        if events is None:
            raise ValueError("events or target_minutes_per_run is required")
        per_run = expected_run_s(events, throttle_ms)
        per_run_events = events
        mode = "events"
    overhead = PREP_PER_RUN_S * repeats + FINALIZE_S
    buffer = per_run * repeats * EVENT_BASED_BUFFER if mode == "events" else 0.0
    return Estimate(
        mode=mode,
        per_run_s=round(per_run, 1),
        per_run_events=per_run_events,
        overhead_s=float(overhead),
        buffer_s=round(buffer, 1),
        total_s=round(per_run * repeats + overhead + buffer),
    )


def run_time_limit_s(events: int, throttle_ms: int, target_minutes_per_run: float | None) -> float:
    """Wall-clock cap for one run: exactly the target when time-boxed, else a generous safety cap."""
    if target_minutes_per_run is not None:
        return target_minutes_per_run * 60
    return expected_run_s(events, throttle_ms) * 1.5 + 60
