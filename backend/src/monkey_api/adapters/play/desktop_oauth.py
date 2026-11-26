"""Cancellable, PKCE-protected desktop OAuth with a private loopback callback server."""

import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from google_auth_oauthlib.flow import InstalledAppFlow

from monkey_api.adapters.play.auth import PLAY_SCOPE
from monkey_api.adapters.play.credential_store import quiet_oauth_logs
from monkey_api.core.play_errors import PlayAuthError


class CallbackServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(1)
        return connection, address


class DesktopOAuth:
    def __init__(self, config: dict) -> None:
        quiet_oauth_logs()
        self.flow = InstalledAppFlow.from_client_config(config, scopes=[PLAY_SCOPE], autogenerate_code_verifier=True)
        self.cancelled = threading.Event()
        self.code: str | None = None
        self.denied = False
        self.state = secrets.token_urlsafe(32)
        self.server = CallbackServer(("127.0.0.1", 0), self._handler())
        self.server.timeout = 0.25
        self.flow.redirect_uri = f"http://127.0.0.1:{self.server.server_port}/"

    def _handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                return  # Callback URLs include authorization codes; never log them.

            def do_GET(self) -> None:
                query = parse_qs(urlsplit(self.path).query)
                states = query.get("state", [])
                valid = urlsplit(self.path).path == "/" and len(states) == 1
                valid = valid and secrets.compare_digest(states[0], owner.state)
                if valid:
                    owner.denied = "error" in query
                    codes = query.get("code", [])
                    owner.code = codes[0] if len(codes) == 1 and codes[0] else None
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(
                    b"Return to Monkey Test to check the connection result." if valid else b"Invalid callback."
                )

        return Handler

    def open_browser(self) -> None:
        url, _ = self.flow.authorization_url(
            state=self.state, access_type="offline", prompt="consent", login_hint="datasvcqa@gmail.com"
        )
        try:
            opened = webbrowser.open(url, new=1)
        except webbrowser.Error:
            opened = False
        if not opened:
            raise PlayAuthError("기본 브라우저를 열지 못했습니다. Windows 기본 브라우저 설정을 확인해 주세요.")

    def wait(self, timeout: float = 300) -> str:
        deadline = time.monotonic() + timeout
        try:
            while not self.cancelled.is_set() and not self.code and not self.denied and time.monotonic() < deadline:
                self.server.handle_request()
            if self.cancelled.is_set() or self.denied or not self.code:
                raise PlayAuthError("Google 로그인이 취소되었거나 제한 시간이 지났습니다. 다시 연결해 주세요.")
            self.flow.fetch_token(code=self.code, timeout=20)
            if not self.flow.credentials.refresh_token:
                raise PlayAuthError("자동 인증 갱신 권한을 받지 못했습니다. 다시 연결해 주세요.")
            return self.flow.credentials.to_json()
        finally:
            self.server.server_close()

    def close(self) -> None:
        self.cancelled.set()
