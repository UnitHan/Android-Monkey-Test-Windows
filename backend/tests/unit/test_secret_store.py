import base64
import json

import pytest
from pydantic import SecretStr

from monkey_api.adapters.storage.secrets import SecretStoreError, read_credentials, read_secret, seal, unseal
from monkey_api.core.errors import AppError
from monkey_api.core.settings import Settings
from monkey_api.services.secure_settings import ai_path, migrate_settings, save_ai


def test_encryption_is_random_user_bound_and_authenticated():
    one, two = seal("private-client-secret"), seal("private-client-secret")
    assert one != two and "private-client-secret" not in one
    assert unseal(one) == unseal(two) == "private-client-secret"
    data = json.loads(one)
    data["salt"] = base64.b64encode(b"x" * 32).decode()
    with pytest.raises(SecretStoreError):
        unseal(json.dumps(data))
    data = json.loads(one)
    ciphertext = bytearray(base64.b64decode(data["ciphertext"]))
    ciphertext[-1] ^= 1
    data["ciphertext"] = base64.b64encode(ciphertext).decode()
    with pytest.raises(SecretStoreError):
        unseal(json.dumps(data))


def test_legacy_oauth_migrates_without_plaintext_temp_files(tmp_path):
    path = tmp_path / "oauth.json"
    content = json.dumps({"refresh_token": "private-refresh-token"})
    path.write_text(content)
    assert read_credentials(path) == content
    assert "private-refresh-token" not in path.read_text()
    assert read_credentials(path) == content
    assert list(tmp_path.iterdir()) == [path]


def test_env_key_migrates_and_deleted_key_does_not_resurrect(tmp_path, monkeypatch):
    monkeypatch.delenv("MONKEY_GEMINI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('MONKEY_GEMINI_API_KEY="test-secret-key"\nMONKEY_GEMINI_MODEL=test-model\n')
    settings = Settings(_env_file=env, data_dir=tmp_path)
    migrate_settings(settings, env)
    assert settings.gemini_api_key.get_secret_value() == "test-secret-key"
    assert "test-secret-key" not in env.read_text()
    assert "test-secret-key" not in ai_path(settings).read_text()
    assert json.loads(read_secret(ai_path(settings)))["api_key"] == "test-secret-key"
    reloaded = Settings(_env_file=env, data_dir=tmp_path)
    migrate_settings(reloaded, env)
    assert reloaded.gemini_api_key == SecretStr("test-secret-key")
    save_ai(reloaded, None, "test-model")
    migrate_settings(reloaded, env)
    assert reloaded.gemini_api_key is None


def test_failed_encryption_preserves_original_plaintext(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("MONKEY_GEMINI_API_KEY=test-key\n")
    settings = Settings(_env_file=env, data_dir=tmp_path)

    def fail(*args):
        raise OSError("unavailable")

    monkeypatch.setattr("monkey_api.services.secure_settings.write_secret", fail)
    with pytest.raises(AppError):
        migrate_settings(settings, env)
    assert "test-key" in env.read_text()
