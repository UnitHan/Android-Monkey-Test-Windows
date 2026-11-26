"""User-triggered Google connection lifecycle; only this service persists login results."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException

from monkey_api.adapters.play.auth import OAuthTokenProvider
from monkey_api.adapters.play.credential_store import client_config, save_credentials
from monkey_api.adapters.play.desktop_oauth import DesktopOAuth
from monkey_api.adapters.storage.secrets import read_credentials
from monkey_api.core.errors import AppError, Conflict
from monkey_api.core.logging import log
from monkey_api.core.play_errors import PlayAuthError, PlayForbidden, PlayNotConfigured, PlayNotFound
from monkey_api.domain.play_auth import PlayAuthStatus
from monkey_api.services.play_service import PlayService


class PlayAuthService:
    def __init__(self, client_path: Path, provider: OAuthTokenProvider, play: PlayService) -> None:
        self.client_path, self.provider, self.play = client_path, provider, play
        self.phase = "idle"
        self.message = "Google Play 계정을 연결해 주세요."
        self.session: DesktopOAuth | None = None
        self.task: asyncio.Task | None = None
        self.factory: Callable[[dict], DesktopOAuth] = DesktopOAuth

    def status(self) -> PlayAuthStatus:
        saved = self.provider.path.is_file()
        message = self.message
        if self.phase == "idle" and saved:
            message = "저장된 Google 인증 정보가 있습니다. 연결 확인으로 앱 조회 권한을 확인할 수 있습니다."
        return PlayAuthStatus(
            client_configured=self.client_path.is_file(),
            credentials_saved=saved,
            phase=self.phase,
            message=message,
        )

    def configure(self, content: str) -> PlayAuthStatus:
        if self.phase == "pending":
            raise Conflict("로그인이 진행 중입니다. 취소한 뒤 파일을 변경해 주세요.")
        config = client_config(content)
        try:
            save_credentials(self.client_path, json.dumps(config))
            self.provider.disconnect()
        except OSError:
            raise PlayAuthError("인증 설정을 저장하지 못했습니다.") from None
        self.phase, self.message = "idle", "클라이언트 등록 완료. Google 계정을 연결해 주세요."
        return self.status()

    async def start(self) -> PlayAuthStatus:
        if self.task and not self.task.done():
            raise Conflict("Google 로그인이 이미 진행 중입니다.")
        try:
            config = client_config(read_credentials(self.client_path))
            self.session = self.factory(config)
        except FileNotFoundError:
            raise PlayNotConfigured("먼저 Google 클라이언트 파일을 등록해 주세요.") from None
        except OSError:
            raise PlayAuthError("로그인 창을 준비하지 못했습니다.") from None
        self.phase, self.message = "pending", "브라우저에서 Google 로그인을 완료해 주세요."
        self.task = asyncio.create_task(self._connect(self.session))
        return self.status()

    async def _connect(self, session: DesktopOAuth) -> None:
        try:
            await asyncio.to_thread(session.open_browser)
            content = await asyncio.to_thread(session.wait)
            if session.cancelled.is_set():
                return
            save_credentials(self.provider.path, content)
            self.provider.invalidate()
            self.phase, self.message = "connected", "Google 인증 완료. 앱을 선택하거나 연결 확인을 눌러 주세요."
            log("app", "Google Play OAuth connected")
        except (
            AppError,
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            GoogleAuthError,
            OAuth2Error,
            RequestException,
        ) as exc:
            if not session.cancelled.is_set():
                self.phase = "error"
                self.message = (
                    exc.detail if isinstance(exc, AppError) else "Google 인증에 실패했습니다. 다시 연결해 주세요."
                )
                log("app", "Google Play OAuth failed", "WARNING")
        finally:
            session.server.server_close()

    async def disconnect(self) -> PlayAuthStatus:
        await self.close()
        try:
            self.provider.disconnect()
        except OSError:
            raise PlayAuthError("이 PC의 인증 정보를 지우지 못했습니다.") from None
        self.phase, self.message = "idle", "이 PC의 Google 인증 정보를 삭제했습니다."
        return self.status()

    async def verify(self) -> PlayAuthStatus:
        if self.phase == "pending":
            raise Conflict("로그인을 먼저 완료해 주세요.")
        if not self.play.packages:
            raise PlayNotConfigured("조회할 LG유플러스 앱을 설정해 주세요.")
        try:
            package = await self._verify_accessible_app()
        except AppError as exc:
            self.phase, self.message = "error", exc.detail
            raise
        self.phase, self.message = "connected", f"Google Play 앱 조회 권한을 확인했습니다: {package}"
        return self.status()

    async def _verify_accessible_app(self) -> str:
        last_error = None
        for package in sorted(self.play.packages):
            try:
                await self.play.get(package)
                return package
            except (PlayForbidden, PlayNotFound) as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise PlayNotConfigured("연결 확인에 사용할 앱을 설정해 주세요. 선택한 앱의 버전은 직접 조회할 수 있습니다.")

    async def close(self) -> None:
        if self.session:
            self.session.close()
        if self.task:
            await self.task
