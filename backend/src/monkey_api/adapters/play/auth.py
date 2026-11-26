"""Load local OAuth credentials and refresh on a worker thread; never log credentials."""

import asyncio
import json
import threading
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from monkey_api.adapters.storage.secrets import read_credentials
from monkey_api.core.play_errors import PlayAuthError, PlayNotConfigured

PLAY_SCOPE = "https://www.googleapis.com/auth/androidpublisher"


class OAuthTokenProvider:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._credentials: Credentials | None = None
        self._mtime: int | None = None

    async def token(self) -> str:
        return await asyncio.to_thread(self._token)

    def invalidate(self) -> None:
        with self._lock:
            self._credentials = None
            self._mtime = None

    def disconnect(self) -> None:
        with self._lock:
            self._credentials = None
            self._mtime = None
            self.path.unlink(missing_ok=True)

    def _token(self) -> str:
        with self._lock:
            try:
                mtime = self.path.stat().st_mtime_ns
                if self._credentials is None or mtime != self._mtime:
                    self._credentials = Credentials.from_authorized_user_info(
                        json.loads(read_credentials(self.path)), scopes=[PLAY_SCOPE]
                    )
                    self._mtime = self.path.stat().st_mtime_ns
                credentials = self._credentials
                if not credentials.valid:
                    request = Request()
                    credentials.refresh(lambda **kwargs: request(timeout=15, **kwargs))
                if not credentials.token:
                    raise PlayAuthError("Google Play 인증을 다시 진행해 주세요.")
                return credentials.token
            except FileNotFoundError:
                raise PlayNotConfigured(
                    "Google Play 계정 연결이 필요합니다. OAuth 인증을 먼저 진행해 주세요."
                ) from None
            except (OSError, ValueError, TypeError, AttributeError, GoogleAuthError):
                self._credentials = None
                raise PlayAuthError("Google Play 인증 파일을 확인하고 계정 연결을 다시 진행해 주세요.") from None
