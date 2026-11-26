import json

from monkey_api.adapters.storage.secrets import read_secret
from monkey_api.services.secure_settings import ai_path


def test_api_key_saved_encrypted_and_never_returned_or_logged(api):
    secret = "synthetic-private-api-key"
    response = api.request("PUT", "/settings/ai", json={"api_key": secret, "model": "test-model"})
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["restart_required"] is False
    container = api.client.app.state.container
    path = ai_path(container.settings)
    assert secret not in path.read_text()
    assert json.loads(read_secret(path))["api_key"] == secret
    assert container.performance_analysis.analyzer.key == secret
    assert secret not in response.text + api.get("/settings/ai").text + api.get("/logs").text
    assert api.delete("/settings/ai").json()["configured"] is False
    assert container.performance_analysis.analyzer.key is None


def test_secret_writes_reject_foreign_origin_and_invalid_body(api):
    body = {"api_key": "synthetic-secret"}
    assert (
        api.request("PUT", "/settings/ai", json=body, headers={"Origin": "https://attacker.invalid"}).status_code == 403
    )
    body["model"] = "synthetic-secret/invalid"
    response = api.request("PUT", "/settings/ai", json=body)
    assert response.status_code == 422
    assert "synthetic-secret" not in response.text + api.get("/logs").text
