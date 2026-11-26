"""Composition root: wires adapters and services. Tests build it with a FakeAdb."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from pydantic import SecretStr

from monkey_api.adapters.adb.apk_icon import ApkIconRenderer
from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.adapters.adb.runner import AdbPort, AdbRunner, LoggingAdb
from monkey_api.adapters.ai.advisor import GeminiAdvisor, NoAdvisor, TuningAdvisor
from monkey_api.adapters.ai.performance import GeminiPerformance
from monkey_api.adapters.play.auth import OAuthTokenProvider
from monkey_api.adapters.play.publisher import PlayPublisher
from monkey_api.adapters.storage.session_repo import SessionRepository
from monkey_api.core.logging import LogStore
from monkey_api.core.settings import Settings
from monkey_api.services.event_bus import EventBus
from monkey_api.services.icon_service import IconService
from monkey_api.services.package_service import PackageService
from monkey_api.services.performance_analysis import PerformanceAnalysisService
from monkey_api.services.play_auth_service import PlayAuthService
from monkey_api.services.play_service import PlayService
from monkey_api.services.secure_settings import save_ai
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
    icons: IconService
    play: PlayService
    play_auth: PlayAuthService
    ai_advisor: bool
    performance_analysis: PerformanceAnalysisService

    def configure_ai(self, key: SecretStr | None, model: str) -> None:
        save_ai(self.settings, key, model)
        self.apply_ai(key, model)

    def apply_ai(self, key: SecretStr | None, model: str) -> None:
        self.settings.gemini_api_key, self.settings.gemini_model = key, model
        self.sessions.runner.deps.advisor = GeminiAdvisor(key.get_secret_value(), model) if key else NoAdvisor()
        self.performance_analysis.analyzer = GeminiPerformance(key.get_secret_value() if key else None, model)
        self.ai_advisor = bool(key)


def build_container(
    settings: Settings, log_store: LogStore, adb: AdbPort | None = None, advisor: TuningAdvisor | None = None
) -> Container:
    ops = DeviceOps(LoggingAdb(adb or AdbRunner(settings.adb_path, settings.adb_timeout_s)))
    ledger = SessionLedger(SessionRepository(settings.sessions_dir), EventBus())
    if advisor is None:
        key = settings.gemini_api_key
        advisor = GeminiAdvisor(key.get_secret_value(), settings.gemini_model) if key else NoAdvisor()
    runner = SessionRunner(RunnerDeps(ops=ops, ledger=ledger, settings=settings, advisor=advisor))
    token_provider = OAuthTokenProvider(settings.play_credentials_path)
    play = PlayService(PlayPublisher(token_provider.token), settings.play_packages)
    return Container(
        settings=settings,
        log_store=log_store,
        ops=ops,
        ledger=ledger,
        sessions=SessionService(ledger, runner),
        packages=PackageService(ops),
        icons=IconService(ops.adb, ApkIconRenderer(settings.aapt2_path), settings.data_dir / "icons"),
        play=play,
        play_auth=PlayAuthService(settings.data_dir / "credentials" / "play-client.json", token_provider, play),
        ai_advisor=not isinstance(advisor, NoAdvisor),
        performance_analysis=PerformanceAnalysisService(
            ledger,
            GeminiPerformance(
                settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None,
                settings.gemini_model,
            ),
        ),
    )


def get_container(request: Request) -> Container:
    return request.app.state.container
