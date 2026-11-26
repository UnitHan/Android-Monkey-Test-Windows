from monkey_api.core.settings import ENV_FILE, Settings


def test_env_is_absolute_and_key_is_loaded_once_per_settings_instance(tmp_path, monkeypatch):
    monkeypatch.delenv("MONKEY_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MONKEY_GEMINI_MODEL", raising=False)
    assert ENV_FILE.is_absolute() and Settings.model_config["env_file"] == ENV_FILE
    path = tmp_path / ".env"
    path.write_text("MONKEY_GEMINI_API_KEY=test-key-one\nMONKEY_GEMINI_MODEL=test-model\n")
    monkeypatch.chdir(tmp_path.parent)
    settings = Settings(_env_file=path)
    path.write_text("MONKEY_GEMINI_API_KEY=test-key-two\n")
    assert settings.gemini_api_key.get_secret_value() == "test-key-one"
    assert settings.gemini_model == "test-model"
    assert "test-key-one" not in repr(settings)
    assert Settings(_env_file=path).gemini_api_key.get_secret_value() == "test-key-two"


def test_blank_key_disables_ai(tmp_path, monkeypatch):
    monkeypatch.delenv("MONKEY_GEMINI_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text('MONKEY_GEMINI_API_KEY="   "\n')
    assert Settings(_env_file=path).gemini_api_key is None
