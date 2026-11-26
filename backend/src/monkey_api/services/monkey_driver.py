"""Keep one run alive across finite Monkey invocations, with one monotonic deadline."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from monkey_api.core.logging import log
from monkey_api.domain.estimation import extension_event_budget, monkey_event_budget, run_time_limit_s
from monkey_api.domain.models import Progress, RunEndReason, RunSegment
from monkey_api.domain.monkey_command import build_monkey_args
from monkey_api.domain.monkey_output import MonkeyOutputTracker

if TYPE_CHECKING:
    from monkey_api.services.run_executor import RunContext


@dataclass
class Execution:
    events_sent: int = 0
    duration_s: float = 0.0
    reason: RunEndReason = "stopped"
    exit_code: int | None = None
    segments: list[RunSegment] = field(default_factory=list)


class MonkeyDriver:
    def __init__(self, ctx: RunContext, run: int, events: int, seed: int) -> None:
        self.ctx, self.run, self.events, self.seed = ctx, run, events, seed
        self.timed = ctx.config.target_minutes_per_run is not None
        self.limit = run_time_limit_s(events, ctx.config.throttle_ms, ctx.config.target_minutes_per_run)
        self.budget = monkey_event_budget(events, ctx.config.target_minutes_per_run)
        self.started = time.monotonic()
        self.deadline = self.started + self.limit
        self.result = Execution()
        self.tracker = MonkeyOutputTracker()
        self.segment = 0
        self.total_budget = 0
        self.stderr = ""

    def _progress(self) -> None:
        elapsed = time.monotonic() - self.started
        sent = self.result.events_sent + self.tracker.events_sent
        pct = elapsed / self.limit if self.timed else sent / self.events
        self.ctx.ledger.set_progress(
            self.ctx.session_id,
            Progress(
                current_run=self.run,
                total_runs=self.ctx.config.repeats,
                run_percent=min(100, int(pct * 100)),
                events_sent=sent,
                events_target=self.events,
                elapsed_s=round(elapsed, 3),
                target_duration_s=self.limit if self.timed else None,
                remaining_s=round(max(0, self.deadline - time.monotonic()), 3) if self.timed else None,
                segment=self.segment,
                events_budget=self.total_budget,
            ),
        )

    async def _ticker(self) -> None:
        while True:
            self._progress()
            await asyncio.sleep(1)

    async def _work(self, seed: int) -> RunEndReason:
        args = build_monkey_args(self.ctx.config, seed, self.budget)
        stream = await self.ctx.ops.monkey(self.ctx.config.device_serial, args)
        try:
            async for line in stream.lines():
                self.tracker.feed(line)
                if self.tracker.lines_seen % 256 == 0:
                    await asyncio.sleep(0)  # buffered stdout must not starve the deadline/stop tasks
            code = await stream.wait()
            self.stderr = (await stream.stderr_text())[:500]
            if self.tracker.aborted:
                return "aborted"
            if not self.tracker.events_sent:
                return "failed_to_start"
            if code != 0 or not (self.tracker.finished or self.tracker.injected is not None):
                return "aborted"
            return "completed"
        finally:
            self.result.exit_code = await stream.terminate()

    async def _wait(self, seed: int) -> float:
        work = asyncio.create_task(self._work(seed))
        stop = asyncio.create_task(self.ctx.stop.wait())
        try:
            done, _ = await asyncio.wait(
                {work, stop},
                timeout=max(0, self.deadline - time.monotonic()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            ended = time.monotonic()
            self.result.reason = (
                "stopped" if self.ctx.stop.is_set() else work.result() if work in done else "time_limit"
            )
        finally:
            work.cancel()
            stop.cancel()
            results = await asyncio.gather(work, stop, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    raise result
        return ended

    async def _segment(self) -> None:
        self.segment += 1
        self.result.exit_code = None
        self.stderr = ""
        seed = self.seed if self.segment == 1 else (self.seed + self.segment - 1) % 2_147_483_648
        self.total_budget += self.budget
        started = time.monotonic()
        self.ctx.ledger.emit(
            self.ctx.session_id,
            "segment_started",
            {
                "run": self.run,
                "segment": self.segment,
                "seed": seed,
                "events_budget": self.budget,
            },
        )
        self._progress()
        ended = await self._wait(seed)
        self.result.duration_s = ended - self.started
        segment = RunSegment(
            segment=self.segment,
            seed=seed,
            events_budget=self.budget,
            events_sent=self.tracker.events_sent,
            duration_s=round(ended - started, 3),
            end_reason=self.result.reason,
            exit_code=self.result.exit_code,
        )
        self.result.segments.append(segment)
        self.result.events_sent += self.tracker.events_sent
        self.tracker = MonkeyOutputTracker()
        self.ctx.ledger.emit(self.ctx.session_id, "segment_finished", {"run": self.run, **segment.model_dump()})
        if self.result.reason in ("aborted", "failed_to_start"):
            log(
                "session",
                f"monkey {self.result.reason}",
                "ERROR",
                run=self.run,
                exit_code=self.result.exit_code,
                stderr=self.stderr,
            )

    def _extend(self) -> None:
        last = self.result.segments[-1]
        remaining = max(0, self.deadline - time.monotonic())
        self.budget = extension_event_budget(self.budget, last.events_sent, last.duration_s, remaining)
        data = {
            "run": self.run,
            "next_segment": self.segment + 1,
            "events_budget": self.budget,
            "events_sent": self.result.events_sent,
            "remaining_s": round(remaining, 3),
        }
        self.ctx.ledger.emit(self.ctx.session_id, "run_extended", data)
        log("session", "monkey event budget extended", **data)

    async def execute(self) -> Execution:
        ticker = asyncio.create_task(self._ticker())
        try:
            while not self.ctx.stop.is_set():
                if time.monotonic() >= self.deadline:
                    self.result.reason = "time_limit"
                    self.result.duration_s = time.monotonic() - self.started
                    break
                await self._segment()
                if self.result.reason != "completed" or not self.timed:
                    break
                if time.monotonic() >= self.deadline:
                    self.result.reason = "time_limit"
                    self.result.duration_s = time.monotonic() - self.started
                    break
                self._extend()
            if self.ctx.stop.is_set():
                self.result.reason = "stopped"
        finally:
            ticker.cancel()
            await asyncio.gather(ticker, return_exceptions=True)
            self._progress()
        return self.result
