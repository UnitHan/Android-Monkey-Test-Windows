import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from monkey_api.adapters.play.auth import PLAY_SCOPE, OAuthTokenProvider
from monkey_api.core.play_errors import PlayAuthError, PlayNotConfigured


def write_credentials(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "authorized_user",
                "client_id": "test.apps.googleusercontent.com",
                "client_secret": "private-client-secret",
                "refresh_token": "private-refresh-token",
                "scopes": [PLAY_SCOPE],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["private-refresh-token", "[]", "{}", "null"])
async def test_missing_and_invalid_credentials_are_sanitized(tmp_path: Path, content: str) -> None:
    path = tmp_path / "oauth.json"
    provider = OAuthTokenProvider(path)
    with pytest.raises(PlayNotConfigured):
        await provider.token()
    path.write_text(content, encoding="utf-8")
    with pytest.raises(PlayAuthError) as error:
        await provider.token()
    assert "private-refresh-token" not in str(error.value)


@pytest.mark.asyncio
async def test_refresh_is_cached_and_login_file_replacement_is_detected(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "oauth.json"
    write_credentials(path)
    refreshed = []

    def refresh(credentials, request):
        refreshed.append(True)
        credentials.token = "refreshed-token"
        credentials.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    provider = OAuthTokenProvider(path)
    assert await provider.token() == await provider.token() == "refreshed-token"
    assert len(refreshed) == 1
    path.unlink()
    with pytest.raises(PlayNotConfigured):
        await provider.token()
    write_credentials(path)
    provider._mtime = -1  # Force timestamp difference even on coarse filesystems.
    assert await provider.token() == "refreshed-token"
    assert len(refreshed) == 2


@pytest.mark.asyncio
async def test_refresh_error_never_exposes_oauth_response(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "oauth.json"
    write_credentials(path)

    def refresh(credentials, request):
        raise RefreshError("invalid_grant private-refresh-token")

    monkeypatch.setattr(Credentials, "refresh", refresh)
    with pytest.raises(PlayAuthError) as error:
        await OAuthTokenProvider(path).token()
    assert "private-refresh-token" not in str(error.value)
