"""Session commands: create, start, stop, delete. Owns runner tasks (one per active session)."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from monkey_api.core.errors import DeviceBusy, SessionActive, ValidationFailed
from monkey_api.core.ids import new_id, utc_now
from monkey_api.core.logging import log, session_id_var
from monkey_api.domain.models import Preset, Session, SessionConfig, SessionOverrides, SessionState
from monkey_api.domain.presets import get_preset
from monkey_api.domain.state_machine import ACTIVE_STATES, TERMINAL_STATES, ensure_transition
from monkey_api.services.session_ledger import SessionLedger
from monkey_api.services.session_runner import SessionRunner


def resolve_config(
    device_serial: str, package: str, preset_id: str, overrides: SessionOverrides | None
) -> SessionConfig:
    preset = get_preset(preset_id)
    if preset is None:
        raise ValidationFailed(f"unknown preset '{preset_id}'", preset_id=preset_id)
    o = overrides or SessionOverrides()
    seed = o.seed if o.seed is not None else preset.fixed_seed
    if preset.seed_mode == "manual" and seed is None:
        raise ValidationFailed("preset 'reproduce' requires overrides.seed")
    try:
        return _build_config(device_serial, package, preset, o, seed)
    except ValidationError as exc:
        raise ValidationFailed("invalid session configuration", errors=exc.errors(include_url=False)) from exc


def _build_config(
    device_serial: str, package: str, preset: Preset, o: SessionOverrides, seed: int | None
) -> SessionConfig:
    return SessionConfig(
        device_serial=device_serial,
        package=package,
        preset_id=preset.id,
        events=o.events or preset.events,
        repeats=o.repeats or preset.repeats,
        throttle_ms=o.throttle_ms if o.throttle_ms is not None else preset.throttle_ms,
        seed_mode="manual" if o.seed is not None else preset.seed_mode,
        seed=seed,
        target_minutes_per_run=o.target_minutes_per_run or preset.target_minutes_per_run,
        event_mix=preset.event_mix,
        bugreport=preset.bugreport,
        adaptive=o.adaptive if o.adaptive is not None else preset.adaptive_margin > 0,
        adaptive_margin=preset.adaptive_margin,
    )


class SessionService:
    def __init__(self, ledger: SessionLedger, runner: SessionRunner) -> None:
        self.ledger = ledger
        self.runner = runner
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stops: dict[str, asyncio.Event] = {}

    def create(self, config: SessionConfig) -> Session:
        session = Session(id=new_id("s"), state=SessionState.CREATED, config=config, created_at=utc_now())
        token = session_id_var.set(session.id)
        try:
            self.ledger.create(session)
            log("session", "session created", package=config.package, preset=config.preset_id)
        finally:
            session_id_var.reset(token)
        return session

    def start(self, session_id: str) -> Session:
        session = self.ledger.get(session_id)
        ensure_transition(session.state, SessionState.PREPARING)
        self._ensure_device_free(session)
        token = session_id_var.set(session_id)
        try:
            session = self.ledger.transition(session_id, SessionState.PREPARING)
            stop = asyncio.Event()
            self._stops[session_id] = stop
            task = asyncio.create_task(self.runner.run(session_id, stop), name=f"session:{session_id}")
            self._tasks[session_id] = task
            task.add_done_callback(lambda _t: self._forget(session_id))
        finally:
            session_id_var.reset(token)
        return session

    def stop(self, session_id: str) -> Session:
        session = self.ledger.get(session_id)
        token = session_id_var.set(session_id)
        try:
            if session.state == SessionState.CREATED:
                return self.ledger.transition(session_id, SessionState.CANCELLED, reason="stopped before start")
            if session.state in (SessionState.STOPPING, SessionState.CANCELLED):
                return session  # idempotent
            ensure_transition(session.state, SessionState.STOPPING)
            session = self.ledger.transition(session_id, SessionState.STOPPING)
            if stop := self._stops.get(session_id):
                stop.set()
            return session
        finally:
            session_id_var.reset(token)

    def delete(self, session_id: str) -> None:
        session = self.ledger.get(session_id)
        if session.state not in TERMINAL_STATES and session.state != SessionState.CREATED:
            raise SessionActive(f"session '{session_id}' is {session.state.value}; stop it first")
        self.ledger.repo.delete(session_id)
        log("session", "session deleted", session_id=session_id)

    def is_running(self, session_id: str) -> bool:
        return session_id in self._tasks

    async def shutdown(self) -> None:
        for stop in self._stops.values():
            stop.set()
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.wait(tasks, timeout=15)
        for task in tasks:
            task.cancel()

    def recover_orphans(self) -> None:
        """Sessions left active by a previous process can never finish: mark them failed."""
        for session in self.ledger.repo.list():
            if session.state in ACTIVE_STATES:
                token = session_id_var.set(session.id)
                try:
                    self.ledger.transition(session.id, SessionState.FAILED, error="server restarted during run")
                finally:
                    session_id_var.reset(token)

    def _ensure_device_free(self, session: Session) -> None:
        for other in self.ledger.repo.list():
            if (
                other.id != session.id
                and other.config.device_serial == session.config.device_serial
                and other.state in ACTIVE_STATES
            ):
                raise DeviceBusy(
                    f"device '{session.config.device_serial}' already runs session '{other.id}'",
                    session_id=other.id,
                )

    def _forget(self, session_id: str) -> None:
        self._tasks.pop(session_id, None)
        self._stops.pop(session_id, None)
