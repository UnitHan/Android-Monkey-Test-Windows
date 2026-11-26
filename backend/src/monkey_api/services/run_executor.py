"""Execute one monkey run: prepare app, start collectors, drive monkey, stop everything, report result."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.core.ids import utc_now
from monkey_api.core.logging import log
from monkey_api.core.settings import Settings
from monkey_api.domain.analysis import perf_stats
from monkey_api.domain.models import Issue, PerfSample, RunResult, SessionConfig
from monkey_api.services import collectors
from monkey_api.services.monkey_driver import Execution, MonkeyDriver
from monkey_api.services.performance_collector import collect_performance
from monkey_api.services.session_ledger import SessionLedger


@dataclass(slots=True)
class RunContext:
    session_id: str
    config: SessionConfig
    ops: DeviceOps
    ledger: SessionLedger
    settings: Settings
    workdir: Path
    stop: asyncio.Event
    issues: list[Issue] = field(default_factory=list)
    samples: list[PerfSample] = field(default_factory=list)


async def prepare_app(ctx: RunContext) -> bool:
    serial, package = ctx.config.device_serial, ctx.config.package
    await ctx.ops.force_stop(serial, package)
    if pid := await ctx.ops.pid_of(serial, package):
        await ctx.ops.kill(serial, pid)
    await ctx.ops.kill_background(serial)
    await ctx.ops.launch(serial, package)
    await asyncio.sleep(ctx.settings.app_launch_wait_s)
    running = await ctx.ops.pid_of(serial, package) is not None
    log("session", "app prepared", "INFO" if running else "WARNING", running=running)
    return running


def _start_collectors(ctx: RunContext, run: int) -> list[asyncio.Task[None]]:
    cfg, s = ctx.config, ctx.settings

    def on_issue(issue: Issue) -> None:
        ctx.issues.append(issue)
        ctx.ledger.record_issue(ctx.session_id, issue)

    def on_sample(sample: PerfSample) -> None:
        ctx.samples.append(sample)
        ctx.ledger.record_perf(ctx.session_id, sample)

    def on_guard(type_: str, data: dict[str, object]) -> None:
        ctx.ledger.emit(ctx.session_id, type_, {"run": run, **data})

    logcat_path = ctx.workdir / f"logcat_run_{run}.log"
    return [
        asyncio.create_task(
            collectors.collect_logcat(ctx.ops, cfg.device_serial, cfg.package, run, logcat_path, on_issue)
        ),
        asyncio.create_task(
            collect_performance(ctx.ops, cfg.device_serial, cfg.package, run, s.perf_interval_s, on_sample, on_guard)
        ),
        asyncio.create_task(
            collectors.guard_app_state(
                ctx.ops,
                cfg.device_serial,
                cfg.package,
                s.guard_interval_s,
                cfg.keep_foreground,
                cfg.network_guard,
                on_guard,
            )
        ),
    ]


async def execute_run(ctx: RunContext, run: int, events: int, seed: int) -> RunResult:
    cfg = ctx.config
    started_at = utc_now()
    t0 = time.monotonic()
    ctx.issues.clear()
    ctx.samples.clear()
    await prepare_app(ctx)
    await ctx.ops.clear_logcat(cfg.device_serial)
    prepared = time.monotonic()
    tasks = _start_collectors(ctx, run)
    try:
        result = await MonkeyDriver(ctx, run, events, seed).execute()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if result.reason not in ("completed", "stopped") and not await ctx.ops.verify(cfg.device_serial):
        result.reason = "device_lost"
    return _result(ctx, run, events, seed, result, started_at, t0, prepared)


def _result(
    ctx: RunContext,
    run: int,
    events: int,
    seed: int,
    result: Execution,
    started_at: datetime,
    t0: float,
    prepared: float,
) -> RunResult:
    stats = perf_stats(ctx.samples)
    total = time.monotonic() - t0
    return RunResult(
        run=run,
        seed=seed,
        events_target=events,
        events_sent=result.events_sent,
        throttle_ms=ctx.config.throttle_ms,
        started_at=started_at,
        ended_at=utc_now(),
        duration_s=round(total, 3),
        exit_code=result.exit_code,
        end_reason=result.reason,
        target_duration_s=(
            ctx.config.target_minutes_per_run * 60 if ctx.config.target_minutes_per_run is not None else None
        ),
        execution_duration_s=round(result.duration_s, 3),
        preparation_duration_s=round(prepared - t0, 3),
        cleanup_duration_s=round(max(0, total - (prepared - t0) - result.duration_s), 3),
        segments=result.segments,
        crashes=sum(1 for i in ctx.issues if i.kind in ("crash", "native_crash")),
        anrs=sum(1 for i in ctx.issues if i.kind == "anr"),
        mem_peak_mb=stats.memory_mb.max,
        cpu_peak_percent=stats.cpu_percent.max,
    )
