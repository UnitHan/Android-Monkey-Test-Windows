"""Atomic local credential writes and strict desktop-client configuration validation."""

import json
import logging
from pathlib import Path

from monkey_api.adapters.storage.secrets import write_secret
from monkey_api.core.errors import ValidationFailed


def quiet_oauth_logs() -> None:
    for name in ("google_auth_oauthlib", "requests_oauthlib", "oauthlib", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def client_config(content: str) -> dict:
    try:
        if len(content) > 64_000:
            raise ValueError("too large")
        data = json.loads(content)["installed"]
        if data["auth_uri"] != "https://accounts.google.com/o/oauth2/auth":
            raise ValueError("auth endpoint")
        if data["token_uri"] != "https://oauth2.googleapis.com/token":
            raise ValueError("token endpoint")
        if not isinstance(data["client_id"], str) or not data["client_id"].endswith(".apps.googleusercontent.com"):
            raise ValueError("client id")
        if not isinstance(data["client_secret"], str) or not data["client_secret"]:
            raise ValueError("client secret")
        return {"installed": {k: data[k] for k in ("client_id", "client_secret", "auth_uri", "token_uri")}}
    except (ValueError, TypeError, KeyError):
        raise ValidationFailed("Google Cloud에서 다운로드한 '데스크톱 앱' 클라이언트 JSON을 선택해 주세요.") from None


def save_credentials(path: Path, content: str) -> None:
    write_secret(path, content)
