"""Execute one monkey run: prepare app, start collectors, drive monkey, stop everything, report result."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.runner import AdbStream
from monkey_api.core.ids import utc_now
from monkey_api.core.logging import log
from monkey_api.core.settings import Settings
from monkey_api.domain.analysis import perf_stats
from monkey_api.domain.estimation import run_time_limit_s
from monkey_api.domain.models import Issue, PerfSample, Progress, RunEndReason, RunResult, SessionConfig
from monkey_api.domain.monkey_command import build_monkey_args
from monkey_api.domain.monkey_output import MonkeyOutputTracker
from monkey_api.services import collectors
from monkey_api.services.session_ledger import SessionLedger

_EARLY_EXIT_S = 3.0
_PROGRESS_EVERY_S = 1.0


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
            collectors.sample_performance(ctx.ops, cfg.device_serial, cfg.package, run, s.perf_interval_s, on_sample)
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


async def _consume(
    ctx: RunContext, stream: AdbStream, tracker: MonkeyOutputTracker, run: int, events: int, started: float
) -> None:
    last = 0.0
    limit = run_time_limit_s(events, ctx.config.throttle_ms, ctx.config.target_minutes_per_run)
    async for line in stream.lines():
        tracker.feed(line)
        now = time.monotonic()
        if now - last >= _PROGRESS_EVERY_S:
            last = now
            elapsed = now - started
            pct = max(tracker.events_sent / events if events else 0, elapsed / limit if limit else 0)
            ctx.ledger.set_progress(
                ctx.session_id,
                Progress(
                    current_run=run,
                    total_runs=ctx.config.repeats,
                    run_percent=min(100, int(pct * 100)),
                    events_sent=tracker.events_sent,
                    events_target=events,
                    elapsed_s=round(elapsed, 1),
                ),
            )


async def _drive_monkey(
    ctx: RunContext, stream: AdbStream, tracker: MonkeyOutputTracker, run: int, events: int
) -> RunEndReason:
    started = time.monotonic()
    limit = run_time_limit_s(events, ctx.config.throttle_ms, ctx.config.target_minutes_per_run)
    consume = asyncio.create_task(_consume(ctx, stream, tracker, run, events, started))
    stop = asyncio.create_task(ctx.stop.wait())
    done, _ = await asyncio.wait({consume, stop}, timeout=limit, return_when=asyncio.FIRST_COMPLETED)
    stop.cancel()
    if consume not in done:
        consume.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consume
        return "stopped" if ctx.stop.is_set() else "time_limit"
    consume.result()  # re-raise reader errors
    if time.monotonic() - started < _EARLY_EXIT_S and tracker.events_sent == 0:
        return "failed_to_start"
    return "aborted" if tracker.aborted else "completed"


async def execute_run(ctx: RunContext, run: int, events: int, seed: int) -> RunResult:
    cfg = ctx.config
    started_at = utc_now()
    t0 = time.monotonic()
    ctx.issues.clear()
    ctx.samples.clear()
    await prepare_app(ctx)
    await ctx.ops.clear_logcat(cfg.device_serial)
    tasks = _start_collectors(ctx, run)
    tracker = MonkeyOutputTracker()
    exit_code: int | None = None
    try:
        args = build_monkey_args(cfg, seed, events)
        log("session", "monkey run starting", run=run, seed=seed, events=events, args=args)
        stream = await ctx.ops.monkey(cfg.device_serial, args)
        reason = await _drive_monkey(ctx, stream, tracker, run, events)
        exit_code = await stream.terminate()
        if reason in ("failed_to_start", "aborted"):
            log(
                "session",
                f"monkey {reason}",
                "ERROR",
                run=run,
                exit_code=exit_code,
                stderr=(await stream.stderr_text())[:500],
            )
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if reason not in ("completed", "stopped") and not await ctx.ops.verify(cfg.device_serial):
        reason = "device_lost"
    stats = perf_stats(ctx.samples)
    return RunResult(
        run=run,
        seed=seed,
        events_target=events,
        events_sent=tracker.events_sent,
        throttle_ms=cfg.throttle_ms,
        started_at=started_at,
        ended_at=utc_now(),
        duration_s=round(time.monotonic() - t0, 1),
        exit_code=exit_code,
        end_reason=reason,
        crashes=sum(1 for i in ctx.issues if i.kind in ("crash", "native_crash")),
        anrs=sum(1 for i in ctx.issues if i.kind == "anr"),
        mem_peak_mb=stats.memory_mb.max,
        cpu_peak_percent=stats.cpu_percent.max,
    )
