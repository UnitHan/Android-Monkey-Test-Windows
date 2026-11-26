"""Composition root: wires adapters and services. Tests build it with a FakeAdb."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.runner import AdbPort, AdbRunner, LoggingAdb
from monkey_api.adapters.ai.advisor import GeminiAdvisor, NoAdvisor, TuningAdvisor
from monkey_api.adapters.storage.session_repo import SessionRepository
from monkey_api.core.logging import LogStore
from monkey_api.core.settings import Settings
from monkey_api.services.event_bus import EventBus
from monkey_api.services.package_service import PackageService
from monkey_api.services.session_ledger import SessionLedger
from monkey_api.services.session_runner import RunnerDeps, SessionRunner
from monkey_api.services.session_service import SessionService


@dataclass(slots=True)
class Container:
    settings: Settings
    log_store: LogStore
    ops: DeviceOps
    ledger: SessionLedger
    sessions: SessionService
    packages: PackageService
    ai_advisor: bool


def build_container(
    settings: Settings, log_store: LogStore, adb: AdbPort | None = None, advisor: TuningAdvisor | None = None
) -> Container:
    ops = DeviceOps(LoggingAdb(adb or AdbRunner(settings.adb_path, settings.adb_timeout_s)))
    ledger = SessionLedger(SessionRepository(settings.sessions_dir), EventBus())
    if advisor is None:
        key = settings.gemini_api_key
        advisor = GeminiAdvisor(key.get_secret_value(), settings.gemini_model) if key else NoAdvisor()
    runner = SessionRunner(RunnerDeps(ops=ops, ledger=ledger, settings=settings, advisor=advisor))
    return Container(
        settings=settings,
        log_store=log_store,
        ops=ops,
        ledger=ledger,
        sessions=SessionService(ledger, runner),
        packages=PackageService(ops),
        ai_advisor=not isinstance(advisor, NoAdvisor),
    )


def get_container(request: Request) -> Container:
    return request.app.state.container
