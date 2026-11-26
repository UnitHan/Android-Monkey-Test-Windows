import httpx
import pytest
from contract import ContractClient
from fakes import PACKAGE, SERIAL

from monkey_api.adapters.play.publisher import PlayPublisher
from monkey_api.domain.play import PUBLISHED

APP = "com.lguplus.aicallagent"
PATH = f"/play/packages/{APP}"


async def token() -> str:
    return "private-access-token"


def publisher(api: ContractClient, handler) -> None:
    api.client.app.state.container.play.publisher = PlayPublisher(token, httpx.MockTransport(handler))


@pytest.mark.parametrize("package", [APP, "com.lguplus.remocon", "com.example.console.managed"])
def test_read_only_official_endpoint_and_metadata_contract(api: ContractClient, package: str) -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "releases": [
                    {
                        "releaseName": "November rollout (not versionName)",
                        "track": "production",
                        "activeArtifacts": [{"versionCode": 99}, {"versionCode": 100}, {"versionCode": 100}],
                        "releaseLifecycleState": PUBLISHED,
                    }
                ]
            },
        )

    publisher(api, respond)
    response = api.get(f"/play/packages/{package}")
    assert response.status_code == 200
    body = response.json()
    assert body["package"] == package
    assert body["source"] == "google_play_developer_api" and body["track"] == "production"
    assert body["releases"][0]["version_codes"] == ["100", "99"]
    assert body["releases"][0]["release_name"] == "November rollout (not versionName)"
    assert "version_name" not in body["releases"][0] and body["checked_at"]
    assert len(calls) == 1 and calls[0].method == "GET"
    assert str(calls[0].url) == (
        f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/tracks/production/releases"
    )
    assert calls[0].headers["Authorization"] == "Bearer private-access-token"


def test_unconfigured_play_does_not_break_installed_version(api: ContractClient) -> None:
    response = api.get(PATH)
    assert response.status_code == 503 and response.json()["code"] == "play_not_configured"
    assert api.get(f"/devices/{SERIAL}/packages/{PACKAGE}").json()["version_code"] == "4021"


def test_google_permissions_reject_apps_outside_console_access(api: ContractClient) -> None:
    publisher(api, lambda _: httpx.Response(403))
    response = api.get("/play/packages/com.nhn.android.search")
    assert response.status_code == 403 and response.json()["code"] == "play_forbidden"


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "play_auth_required"),
        (403, "play_forbidden"),
        (404, "play_not_found"),
        (429, "play_rate_limited"),
        (500, "play_error"),
        (302, "play_error"),
    ],
)
def test_google_errors_are_typed_and_do_not_leak_tokens(api: ContractClient, status: int, code: str) -> None:
    publisher(api, lambda _: httpx.Response(status, text="private-access-token private-refresh-token"))
    response = api.get(PATH)
    assert response.status_code == (status if status in (401, 403, 404, 429) else 502)
    assert response.json()["code"] == code
    logs = api.get("/logs").text
    assert "private-access-token" not in response.text + logs
    assert "private-refresh-token" not in response.text + logs


@pytest.mark.parametrize("payload", [{"releases": None}, {"releases": [{"track": "production"}]}, ["invalid"]])
def test_malformed_google_payload(api: ContractClient, payload: object) -> None:
    publisher(api, lambda _: httpx.Response(200, json=payload))
    response = api.get(PATH)
    assert response.status_code == 502 and response.json()["code"] == "play_error"


def test_empty_release_list(api: ContractClient) -> None:
    publisher(api, lambda _: httpx.Response(200, json={}))
    assert api.get(PATH).json()["releases"] == []


def test_timeout_is_reported_without_upstream_details(api: ContractClient) -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-access-token")

    publisher(api, timeout)
    response = api.get(PATH)
    assert response.status_code == 504 and response.json()["code"] == "play_timeout"
    assert "private-access-token" not in response.text


def test_unpublished_release_keeps_its_state_and_wrong_track_is_excluded(api: ContractClient) -> None:
    publisher(
        api,
        lambda _: httpx.Response(
            200,
            json={
                "releases": [
                    {
                        "track": "production",
                        "releaseLifecycleState": "RELEASE_LIFECYCLE_STATE_IN_REVIEW",
                        "activeArtifacts": [{"versionCode": 999}],
                    },
                    {"track": "beta", "releaseLifecycleState": PUBLISHED, "activeArtifacts": [{"versionCode": 1000}]},
                ]
            },
        ),
    )
    releases = api.get(PATH).json()["releases"]
    assert len(releases) == 1
    assert releases[0]["lifecycle_state"] == "RELEASE_LIFECYCLE_STATE_IN_REVIEW"
