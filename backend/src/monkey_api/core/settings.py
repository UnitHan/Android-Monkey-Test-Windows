"""Application settings loaded from environment (prefix MONKEY_) and optional .env file."""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_SDK_ADB = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"
_REPO_ROOT = Path(__file__).resolve().parents[4]


def discover_adb() -> str:
    """Locate adb: Android SDK, then PATH. Override with MONKEY_ADB_PATH."""
    if _SDK_ADB.is_file():
        return str(_SDK_ADB)
    return shutil.which("adb") or "adb"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONKEY_", env_file=".env", extra="ignore")

    adb_path: str = Field(default_factory=discover_adb)
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("LOCALAPPDATA", Path.home())) / "MonkeyTest")
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
    log_buffer_size: int = 20_000
    ui_dir: Path | None = Field(default_factory=lambda: _REPO_ROOT / "frontend" / "dist")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost"]

    adb_timeout_s: float = 30.0
    perf_interval_s: float = 2.0
    guard_interval_s: float = 5.0
    app_launch_wait_s: float = 5.0

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
