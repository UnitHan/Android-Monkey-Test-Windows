import json
import threading
import time
from types import SimpleNamespace

import httpx
from contract import ContractClient

from monkey_api.adapters.play.publisher import PlayPublisher

CLIENT = {
    "installed": {
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "private-client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}
PATH = "/play/auth"


class FakeOAuth:
    def __init__(self, config: dict) -> None:
        self.cancelled = threading.Event()
        self.ready = threading.Event()
        self.opened = False
        self.server = SimpleNamespace(server_close=lambda: None)

    def open_browser(self) -> None:
        self.opened = True

    def wait(self) -> str:
        while not self.ready.wait(0.01) and not self.cancelled.is_set():
            continue
        return json.dumps({"refresh_token": "private-refresh-token"})

    def close(self) -> None:
        self.cancelled.set()


def configure(api: ContractClient) -> None:
    response = api.post(f"{PATH}/client", json={"client_json": json.dumps(CLIENT)})
    assert response.status_code == 200 and response.json()["client_configured"] is True


def wait_login(api: ContractClient) -> dict:
    for _ in range(100):
        status = api.get(PATH).json()
        if status["phase"] != "pending":
            return status
        time.sleep(0.01)
    raise AssertionError("Login did not complete")


def test_settings_configure_connect_verify_disconnect_and_no_secret_leaks(api: ContractClient) -> None:
    auth = api.client.app.state.container.play_auth
    auth.factory = FakeOAuth
    configure(api)
    assert api.post(f"{PATH}/connect").json()["phase"] == "pending"
    auth.session.ready.set()
    assert wait_login(api)["credentials_saved"] is True
    assert auth.session.opened
    response = api.delete(PATH)
    assert response.json()["credentials_saved"] is False and not auth.provider.path.exists()
    assert response.json()["client_configured"] is True  # Client config survives local sign-out.
    logs = api.get("/logs").text
    assert "private-client-secret" not in logs and "private-refresh-token" not in logs


def test_cancel_prevents_late_callback_from_saving_credentials(api: ContractClient) -> None:
    auth = api.client.app.state.container.play_auth
    auth.factory = FakeOAuth
    configure(api)
    assert api.post(f"{PATH}/connect").status_code == 200
    assert api.post(f"{PATH}/connect").status_code == 409
    assert api.post(f"{PATH}/client", json={"client_json": json.dumps(CLIENT)}).status_code == 409
    assert api.delete(PATH).json()["phase"] == "idle"
    assert not auth.provider.path.exists()


def test_oauth_client_validation_and_origin_rejection(api: ContractClient) -> None:
    for content in (
        "[]",
        '{"web": {}}',
        "private-client-secret",
        json.dumps(CLIENT).replace("oauth2.googleapis.com", "evil.example"),
    ):
        response = api.post(f"{PATH}/client", json={"client_json": content})
        assert response.status_code == 422 and "private-client-secret" not in response.text
    response = api.post(
        f"{PATH}/client", json={"client_json": json.dumps(CLIENT)}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert api.post(f"{PATH}/connect").status_code == 503


def test_host_rebinding_is_rejected(api: ContractClient) -> None:
    configure(api)
    response = api.post(f"{PATH}/connect", headers={"Host": "evil.example"})
    assert response.status_code == 403


def test_connection_check_verifies_real_publisher_boundary(api: ContractClient) -> None:
    async def token():
        return "token"

    play = api.client.app.state.container.play
    play.publisher = PlayPublisher(token, httpx.MockTransport(lambda _: httpx.Response(403, text="private-token")))
    assert api.post(f"{PATH}/check").status_code == 403
    assert api.get(PATH).json()["phase"] == "error"
    play.publisher = PlayPublisher(token, httpx.MockTransport(lambda _: httpx.Response(200, json={})))
    assert api.post(f"{PATH}/check").json()["phase"] == "connected"


def test_client_replacement_clears_previous_login(api: ContractClient) -> None:
    auth = api.client.app.state.container.play_auth
    auth.provider.path.write_text("private-refresh-token", encoding="utf-8")
    configure(api)
    assert not auth.provider.path.exists()


def test_connection_check_accepts_tv_access_when_ixio_is_forbidden(api: ContractClient) -> None:
    async def token():
        return "private-token"

    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={}) if "com.lguplus.remocon" in request.url.path else httpx.Response(403)

    play = api.client.app.state.container.play
    play.packages = frozenset(["com.lguplus.aicallagent", "com.lguplus.remocon"])
    play.publisher = PlayPublisher(token, httpx.MockTransport(respond))
    response = api.post(f"{PATH}/check")
    assert response.status_code == 200 and response.json()["phase"] == "connected"
    assert "com.lguplus.remocon" in response.json()["message"] and len(calls) == 2
