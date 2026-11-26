"""Drive a whole session: prepare → runs (adaptive) → finish → reports. Runs as one asyncio task."""

from __future__ import annotations

import asyncio
import contextlib
import traceback
from dataclasses import dataclass

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.ai.advisor import TuningAdvisor
from monkey_api.adapters.report.excel import write_excel
from monkey_api.adapters.report.html import write_html
from monkey_api.core.errors import AppError
from monkey_api.core.logging import log, session_id_var
from monkey_api.core.settings import Settings
from monkey_api.domain.adaptive import RunSample, next_run_events
from monkey_api.domain.estimation import estimate_duration
from monkey_api.domain.models import RunResult, Session, SessionState
from monkey_api.domain.monkey_command import seed_for_run
from monkey_api.domain.report import SessionReport, build_report
from monkey_api.services.run_executor import RunContext, execute_run
from monkey_api.services.session_ledger import SessionLedger

_BETWEEN_RUNS_S = 2.0


@dataclass(slots=True)
class RunnerDeps:
    ops: DeviceOps
    ledger: SessionLedger
    settings: Settings
    advisor: TuningAdvisor


def build_session_report(ledger: SessionLedger, session_id: str) -> SessionReport:
    repo = ledger.repo
    return build_report(repo.get(session_id), repo.issues(session_id), repo.perf(session_id))


class SessionRunner:
    def __init__(self, deps: RunnerDeps) -> None:
        self.deps = deps

    async def run(self, session_id: str, stop: asyncio.Event) -> None:
        session_id_var.set(session_id)
        ledger = self.deps.ledger
        try:
            await self._prepare(session_id)
            if stop.is_set():
                ledger.transition(session_id, SessionState.CANCELLED, reason="stopped during prepare")
                return
            ledger.transition(session_id, SessionState.RUNNING)
            await self._run_all(session_id, stop)
            final = SessionState.CANCELLED if stop.is_set() else SessionState.COMPLETED
            self._write_reports(session_id)
            ledger.transition(session_id, final)
        except asyncio.CancelledError:
            log("session", "runner task cancelled", "WARNING")
            self._fail(session_id, "server shutdown")
            raise
        except AppError as exc:
            self._fail(session_id, exc.detail, code=exc.code)
        except Exception as exc:  # noqa: BLE001 - last-resort boundary: record, never swallow silently
            self._fail(session_id, f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-2000:])

    async def _prepare(self, session_id: str) -> None:
        ops, ledger = self.deps.ops, self.deps.ledger
        cfg = ledger.get(session_id).config
        device = await ops.device_info(cfg.device_serial)
        version = await ops.package_version(cfg.device_serial, cfg.package)
        if version.version_code is None and version.version_name is None:
            raise AppError(f"package '{cfg.package}' is not installed on {cfg.device_serial}")
        estimate = estimate_duration(cfg.events, cfg.repeats, cfg.throttle_ms, cfg.target_minutes_per_run)
        ledger.update(
            session_id,
            lambda s: s.model_copy(
                update={"device": device, "app_version": version, "estimated_total_s": estimate.total_s}
            ),
        )
        log(
            "session",
            "session prepared",
            device=device.model,
            version=version.version_name,
            estimated_total_s=estimate.total_s,
        )

    async def _run_all(self, session_id: str, stop: asyncio.Event) -> None:
        ledger, settings = self.deps.ledger, self.deps.settings
        cfg = ledger.get(session_id).config
        workdir = ledger.repo.dir_for(session_id)
        ctx = RunContext(session_id, cfg, self.deps.ops, ledger, settings, workdir, stop)
        history: list[RunSample] = []
        for run in range(1, cfg.repeats + 1):
            if stop.is_set():
                break
            events = await self._events_for(
                cfg.events, history, cfg.target_minutes_per_run, cfg.adaptive, cfg.adaptive_margin, cfg.throttle_ms
            )
            seed = seed_for_run(cfg)
            ledger.emit(session_id, "run_started", {"run": run, "events": events, "seed": seed})
            result = await execute_run(ctx, run, events, seed)
            self._append_run(session_id, result)
            if result.end_reason == "device_lost" and not await self.deps.ops.reconnect(cfg.device_serial):
                raise AppError(f"device {cfg.device_serial} lost during run {run}")
            history.append(RunSample(result.events_sent, result.duration_s))
            if run < cfg.repeats:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), _BETWEEN_RUNS_S)

    async def _events_for(
        self,
        base: int,
        history: list[RunSample],
        target_min: float | None,
        adaptive: bool,
        margin: float,
        throttle_ms: int,
    ) -> int:
        if not adaptive or target_min is None or not history:
            return base
        target_s = target_min * 60
        algo = next_run_events(base, history, target_s, margin)
        suggested = await self.deps.advisor.suggest_events(base, history, target_s, throttle_ms)
        if suggested is None:
            return algo
        bounded = max(base, min(int(base * (1 + margin)), suggested))
        log("session", "advisor suggestion applied", algorithm=algo, advisor=suggested, applied=bounded)
        return bounded

    def _append_run(self, session_id: str, result: RunResult) -> None:
        def add(s: Session) -> Session:
            return s.model_copy(update={"runs": [*s.runs, result]})

        self.deps.ledger.update(session_id, add)
        level = "INFO" if result.end_reason in ("completed", "time_limit", "stopped") else "WARNING"
        log("session", "run finished", level, **result.model_dump(mode="json"))
        self.deps.ledger.emit(session_id, "run_finished", result.model_dump(mode="json"))

    def _write_reports(self, session_id: str) -> None:
        report = build_session_report(self.deps.ledger, session_id)
        workdir = self.deps.ledger.repo.dir_for(session_id)
        write_html(report, workdir / "report.html")
        write_excel(report, workdir / "report.xlsx")
        self.deps.ledger.emit(session_id, "report_ready", {"files": ["report.html", "report.xlsx"]})

    def _fail(self, session_id: str, error: str, **data: object) -> None:
        ledger = self.deps.ledger
        state = ledger.get(session_id).state
        if state in (SessionState.PREPARING, SessionState.RUNNING, SessionState.STOPPING):
            ledger.transition(session_id, SessionState.FAILED, error=error, **data)
