"""Application settings loaded from environment (prefix MONKEY_) and optional .env file."""

from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SDK_ADB = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"
_FROZEN = bool(getattr(sys, "frozen", False))
_REPO_ROOT = Path(sys.executable).parent if _FROZEN else Path(__file__).resolve().parents[4]
_TOOLS = _REPO_ROOT / "tools"
ENV_FILE = _REPO_ROOT / ".env"


def discover_adb() -> str:
    """Locate adb: Android SDK, then PATH. Override with MONKEY_ADB_PATH."""
    if (_TOOLS / "adb.exe").is_file():
        return str(_TOOLS / "adb.exe")
    if _SDK_ADB.is_file():
        return str(_SDK_ADB)
    return shutil.which("adb") or "adb"


def discover_aapt2() -> str:
    if (_TOOLS / "aapt2.exe").is_file():
        return str(_TOOLS / "aapt2.exe")
    roots = [Path(os.environ[k]) for k in ("ANDROID_HOME", "ANDROID_SDK_ROOT") if os.environ.get(k)]
    roots.append(_SDK_ADB.parent.parent)
    for root in roots:
        candidates = list((root / "build-tools").glob("*/aapt2.exe"))
        if candidates:
            return str(
                max(candidates, key=lambda p: tuple(int(n) if n.isdigit() else 0 for n in p.parent.name.split(".")))
            )
    return shutil.which("aapt2") or "aapt2"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MONKEY_", env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    adb_path: str = Field(default_factory=discover_adb)
    aapt2_path: str = Field(default_factory=discover_aapt2)
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("LOCALAPPDATA", Path.home())) / "MonkeyTest")
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
    log_buffer_size: int = 20_000
    ui_dir: Path | None = Field(default_factory=lambda: _REPO_ROOT / "frontend" / "dist")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
    ]

    adb_timeout_s: float = 30.0
    perf_interval_s: float = 2.0
    guard_interval_s: float = 5.0
    app_launch_wait_s: float = 5.0
    export_dir: Path = Field(default_factory=lambda: Path.home() / "Downloads" / "MonkeyTest")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    deployment_bundle: Path = Field(default_factory=lambda: _REPO_ROOT / "deployment.vault.json")

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def empty_key_is_disabled(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    play_oauth_file: Path | None = None
    # Known apps used by the connection check; selected-app queries use Google permissions.
    play_packages: list[str] = ["com.lguplus.aicallagent", "com.lguplus.remocon"]

    @property
    def play_credentials_path(self) -> Path:
        return self.play_oauth_file or self.data_dir / "credentials" / "play-oauth.json"

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
