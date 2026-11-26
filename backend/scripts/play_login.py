"""One-time desktop OAuth login. Run with --help; credentials stay in the user's data directory."""

import argparse
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google_auth_oauthlib.flow import InstalledAppFlow
from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException

from monkey_api.adapters.play.auth import PLAY_SCOPE
from monkey_api.adapters.play.credential_store import client_config, quiet_oauth_logs, save_credentials
from monkey_api.core.errors import AppError
from monkey_api.core.logging import LogStore, configure_logging, log
from monkey_api.core.settings import Settings


def login(client_file: Path, output: Path) -> None:
    quiet_oauth_logs()
    config = client_config(client_file.read_text(encoding="utf-8"))
    flow = InstalledAppFlow.from_client_config(config, scopes=[PLAY_SCOPE], autogenerate_code_verifier=True)
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        timeout_seconds=300,
        authorization_prompt_message="Google 로그인 창에서 Play Console 계정을 선택해 주세요.",
        success_message="Google login response received. Check the terminal for the connection result.",
        login_hint="datasvcqa@gmail.com",
        prompt="consent",
        access_type="offline",
    )
    if not credentials.refresh_token:
        raise ValueError("No refresh token returned")
    save_credentials(output, credentials.to_json())


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect a Play Console user using a Google Desktop OAuth client.")
    parser.add_argument("--client-secrets", required=True, type=Path, help="Downloaded Desktop OAuth client JSON path")
    parser.add_argument("--output", type=Path, default=Settings().play_credentials_path)
    args = parser.parse_args()
    configure_logging(LogStore(), "INFO")
    try:
        login(args.client_secrets, args.output)
    except (AppError, OSError, ValueError, TypeError, AttributeError, GoogleAuthError, OAuth2Error, RequestException):
        parser.exit(1, "Google Play 연결 실패: 클라이언트 파일, 계정 동의 또는 로그인 제한 시간을 확인해 주세요.\n")
    log("app", "Google Play 계정 연결 완료. 앱에서 새로고침을 눌러 주세요.")


if __name__ == "__main__":
    main()
