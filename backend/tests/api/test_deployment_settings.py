import json

import pytest

from monkey_api.adapters.storage.deployment_vault import decrypt_bundle, encrypt_bundle
from monkey_api.adapters.storage.secrets import read_secret, write_secret
from monkey_api.core.errors import ValidationFailed
from monkey_api.services.deployment_settings import ACCOUNT, credential_paths, snapshot

PASSWORD = "synthetic-deployment-password-only"
PAYLOAD = {
    "version": 1,
    "account": ACCOUNT,
    "client": {
        "installed": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "private-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    "oauth": {
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "private-client-secret",
        "refresh_token": "private-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
    },
    "gemini": {"api_key": "private-gemini-key", "model": "test-model"},
    "play_packages": ["com.lguplus.remocon"],
}


def install_bundle(api, tmp_path):
    settings = api.client.app.state.container.settings
    settings.deployment_bundle = tmp_path / "deployment.vault.json"
    settings.deployment_bundle.write_text(encrypt_bundle(PAYLOAD, PASSWORD), encoding="utf-8")
    return settings


def test_bundle_encryption_randomness_and_tampering():
    first, second = encrypt_bundle(PAYLOAD, PASSWORD), encrypt_bundle(PAYLOAD, PASSWORD)
    assert first != second
    assert decrypt_bundle(first, PASSWORD) == PAYLOAD
    assert "private-gemini-key" not in first and "private-refresh-token" not in first
    with pytest.raises(ValidationFailed):
        decrypt_bundle(first, "incorrect-password")
    altered = json.loads(first)
    altered["salt"] = json.loads(second)["salt"]
    with pytest.raises(ValidationFailed):
        decrypt_bundle(json.dumps(altered), PASSWORD)


def test_empty_pc_restores_all_settings_and_repeat_preserves_ciphertexts(api, tmp_path):
    settings = install_bundle(api, tmp_path)
    assert api.get("/settings/deployment").json() == {"available": True, "configured": False, "account": ACCOUNT}
    response = api.post("/settings/deployment/unlock", json={"password": PASSWORD})
    assert response.status_code == 200 and response.json()["configured"]
    paths = credential_paths(settings)
    assert snapshot(settings) == PAYLOAD | {"play_packages": settings.play_packages}
    before = {key: path.read_bytes() for key, path in paths.items()}
    assert api.get("/settings/ai").json()["configured"]
    assert api.get("/play/auth").json()["credentials_saved"]
    assert "저장된" in api.get("/play/auth").json()["message"]
    assert api.post("/settings/deployment/unlock", json={"password": PASSWORD}).status_code == 200
    assert before == {key: path.read_bytes() for key, path in paths.items()}
    logs = api.get("/logs").text
    for secret in (PASSWORD, "private-gemini-key", "private-refresh-token", "private-client-secret"):
        assert secret not in logs + response.text
        assert all(secret.encode() not in raw for raw in before.values())


def test_wrong_password_or_foreign_origin_writes_nothing(api, tmp_path):
    settings = install_bundle(api, tmp_path)
    assert api.post("/settings/deployment/unlock", json={"password": "wrong-password"}).status_code == 422
    assert (
        api.post(
            "/settings/deployment/unlock", json={"password": PASSWORD}, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    assert not any(path.exists() for path in credential_paths(settings).values())


def test_existing_key_is_not_overwritten_when_missing_google_is_restored(api, tmp_path):
    settings = install_bundle(api, tmp_path)
    path = credential_paths(settings)["gemini"]
    existing = {"api_key": "existing-key", "model": "existing-model"}
    write_secret(path, json.dumps(existing))
    before = path.read_bytes()
    assert api.post("/settings/deployment/unlock", json={"password": PASSWORD}).status_code == 200
    assert path.read_bytes() == before and json.loads(read_secret(path)) == existing
    assert settings.gemini_api_key.get_secret_value() == "existing-key"


def test_other_google_client_is_not_overwritten(api, tmp_path):
    settings = install_bundle(api, tmp_path)
    client = json.loads(json.dumps(PAYLOAD["client"]))
    client["installed"]["client_id"] = "other.apps.googleusercontent.com"
    path = credential_paths(settings)["client"]
    write_secret(path, json.dumps(client))
    before = path.read_bytes()
    assert api.post("/settings/deployment/unlock", json={"password": PASSWORD}).status_code == 409
    assert path.read_bytes() == before
    assert not credential_paths(settings)["oauth"].exists()
