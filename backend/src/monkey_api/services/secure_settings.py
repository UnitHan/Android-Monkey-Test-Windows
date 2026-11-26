"""Migrate local secrets and persist Gemini settings without returning secret values."""

import json
import os
import re
from pathlib import Path

from pydantic import SecretStr

from monkey_api.adapters.storage.secrets import atomic_write, read_credentials, read_secret, write_secret
from monkey_api.core.errors import AppError
from monkey_api.core.settings import ENV_FILE, Settings


def ai_path(settings: Settings) -> Path:
    return settings.data_dir / "credentials" / "gemini.enc.json"


def save_ai(settings: Settings, key: SecretStr | None, model: str) -> None:
    try:
        write_secret(
            ai_path(settings), json.dumps({"api_key": key.get_secret_value() if key else None, "model": model})
        )
    except OSError:
        raise AppError("Gemini 설정을 암호화해서 저장하지 못했습니다.") from None


def load_ai(settings: Settings) -> tuple[SecretStr | None, str]:
    data = json.loads(read_secret(ai_path(settings)))
    return SecretStr(data["api_key"]) if data.get("api_key") else None, data["model"]


def migrate_settings(settings: Settings, env_file: Path = ENV_FILE) -> None:
    """Called only by the real entry point; schema exports/tests never migrate user files."""
    for path in (settings.data_dir / "credentials" / "play-client.json", settings.play_credentials_path):
        if path.is_file():
            read_credentials(path)
    path = ai_path(settings)
    if not path.exists() and settings.gemini_api_key:
        save_ai(settings, settings.gemini_api_key, settings.gemini_model)
    if path.exists():
        data = json.loads(read_secret(path))
        settings.gemini_api_key = SecretStr(data["api_key"]) if data.get("api_key") else None
        settings.gemini_model = data.get("model", settings.gemini_model)
        _remove_env_key(env_file)
        os.environ.pop("MONKEY_GEMINI_API_KEY", None)


def _remove_env_key(path: Path) -> None:
    if not path.is_file():
        return
    # dotenv's parser handles quotes and multiline values; remove complete key bindings.
    text = path.read_text(encoding="utf-8-sig")
    cleaned = re.sub(
        r"(?m)^[ \t]*(?:export[ \t]+)?MONKEY_GEMINI_API_KEY[ \t]*=[ \t]*"
        r"(?:\"(?:\\.|[^\"])*\"|'[^']*'|[^\r\n]*)[^\r\n]*",
        "# Gemini API key is stored in the Windows encrypted credential store.",
        text,
    )
    if cleaned != text:
        atomic_write(path, cleaned)
