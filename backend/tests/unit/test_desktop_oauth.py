import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from monkey_api.adapters.play.desktop_oauth import DesktopOAuth
from monkey_api.core.play_errors import PlayAuthError

CONFIG = {
    "installed": {
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "private-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


@pytest.mark.asyncio
async def test_pkce_state_validation_and_callback_no_secret_logging(monkeypatch, caplog) -> None:
    oauth = DesktopOAuth(CONFIG)
    urls = []
    monkeypatch.setattr("webbrowser.open", lambda url, **kw: urls.append(url) or True)
    oauth.open_browser()
    query = parse_qs(urlsplit(urls[0]).query)
    assert query["state"] == [oauth.state] and query["code_challenge_method"] == ["S256"]
    assert "code_challenge" in query
    assert query["login_hint"] == ["datasvcqa@gmail.com"]
    exchanged = []
    oauth.flow = SimpleNamespace(
        fetch_token=lambda **kw: exchanged.append(kw),
        credentials=SimpleNamespace(
            refresh_token="secret-refresh", to_json=lambda: '{"refresh_token":"secret-refresh"}'
        ),
    )
    pending = asyncio.create_task(asyncio.to_thread(oauth.wait, 3))
    address = f"http://127.0.0.1:{oauth.server.server_port}/"
    async with httpx.AsyncClient(trust_env=False) as client:
        rejected = await client.get(address, params={"state": "wrong", "code": "secret-code"})
        assert rejected.status_code == 400 and not exchanged
        accepted = await client.get(address, params={"state": oauth.state, "code": "secret-code"})
        assert accepted.status_code == 200 and "secret-code" not in accepted.text
    assert "secret-refresh" in await pending
    assert exchanged == [{"code": "secret-code", "timeout": 20}]
    assert "secret-code" not in caplog.text and "secret-refresh" not in caplog.text


@pytest.mark.asyncio
async def test_login_timeout_and_cancellation_close_listener() -> None:
    oauth = DesktopOAuth(CONFIG)
    oauth.close()
    with pytest.raises(PlayAuthError):
        await asyncio.to_thread(oauth.wait, 0.1)
    assert oauth.server.fileno() == -1
