"""Duration estimation and run-time limits (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class Overheads:
    app_restart_per_run_s: float = 15
    logcat_setup_s: float = 5
    cleanup_per_run_s: float = 5
    monkey_startup_s: float = 8
    performance_monitoring_s: float = 4
    final_report_s: float = 20
    buffer_ratio: float = 0.25
    throttle_efficiency: float = 0.35


DEFAULT_OVERHEADS = Overheads()


class Estimate(BaseModel):
    per_run_s: float
    overhead_s: float
    buffer_s: float
    total_s: int


def event_time_s(events: int, throttle_ms: int, o: Overheads = DEFAULT_OVERHEADS) -> float:
    """Expected pure monkey time for one run (legacy calibrated formula)."""
    return events * throttle_ms / 1000 / o.throttle_efficiency


def estimate_duration(
    events: int,
    repeats: int,
    throttle_ms: int,
    target_minutes_per_run: float | None = None,
    o: Overheads = DEFAULT_OVERHEADS,
) -> Estimate:
    per_run = event_time_s(events, throttle_ms, o)
    if target_minutes_per_run is not None:
        per_run = min(per_run, target_minutes_per_run * 60)
    per_run_overhead = o.app_restart_per_run_s + o.logcat_setup_s + o.cleanup_per_run_s
    fixed_overhead = o.monkey_startup_s + o.performance_monitoring_s + o.final_report_s
    total = (per_run + per_run_overhead) * repeats + fixed_overhead
    buffer = total * o.buffer_ratio
    return Estimate(
        per_run_s=round(per_run, 1),
        overhead_s=round(per_run_overhead * repeats + fixed_overhead, 1),
        buffer_s=round(buffer, 1),
        total_s=int(total + buffer),
    )


def run_time_limit_s(events: int, throttle_ms: int, target_minutes_per_run: float | None) -> float:
    """Hard wall-clock cap for one run.

    With a target the run is stopped exactly at the target (legacy did this for Deep Test only).
    Without a target: 1.5x expected + 60s (legacy rule for short runs; 1.2x + 120s above 10 min).
    """
    if target_minutes_per_run is not None:
        return target_minutes_per_run * 60
    expected = event_time_s(events, throttle_ms) + DEFAULT_OVERHEADS.monkey_startup_s
    return expected * 1.2 + 120 if expected > 600 else expected * 1.5 + 60
