"""Restore bundled credentials into this Windows account, preserving existing settings."""

import json
from pathlib import Path

from google.oauth2.credentials import Credentials

from monkey_api.adapters.play.credential_store import client_config
from monkey_api.adapters.storage.deployment_vault import decrypt_bundle
from monkey_api.adapters.storage.secrets import atomic_write, read_credentials, read_secret, seal, unseal
from monkey_api.core.errors import AppError, Conflict, NotFound, ValidationFailed
from monkey_api.core.settings import Settings
from monkey_api.services.secure_settings import ai_path

ACCOUNT = "datasvcqa@gmail.com"


def credential_paths(settings: Settings) -> dict[str, Path]:
    return {
        "client": settings.data_dir / "credentials/play-client.json",
        "oauth": settings.play_credentials_path,
        "gemini": ai_path(settings),
    }


def snapshot(settings: Settings) -> dict:
    paths = credential_paths(settings)
    try:
        payload = {
            "version": 1,
            "account": ACCOUNT,
            **{key: json.loads(read_secret(path)) for key, path in paths.items()},
            "play_packages": settings.play_packages,
        }
        validate_payload(payload)
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        raise ValidationFailed(
            "Google 로그인과 Gemini 키가 모두 저장되어 있어야 기존 설정을 포함해 빌드할 수 있습니다."
        ) from None


def validate_payload(payload: dict) -> None:
    try:
        if payload["version"] != 1 or payload["account"] != ACCOUNT:
            raise ValueError
        client = client_config(json.dumps(payload["client"]))["installed"]
        oauth = payload["oauth"]
        Credentials.from_authorized_user_info(oauth)
        if oauth["client_id"] != client["client_id"] or oauth["client_secret"] != client["client_secret"]:
            raise ValueError
        if not isinstance(payload["gemini"]["api_key"], str) or not payload["gemini"]["api_key"].strip():
            raise ValueError
        if not isinstance(payload["gemini"]["model"], str) or not payload["gemini"]["model"]:
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValidationFailed("설치 패키지의 인증 설정이 완전하지 않습니다.") from None


def restore(settings: Settings, password: str) -> None:
    if not settings.deployment_bundle.is_file():
        raise NotFound("설치 파일에 포함된 인증 설정이 없습니다.")
    payload = decrypt_bundle(settings.deployment_bundle.read_text(encoding="utf-8"), password)
    validate_payload(payload)
    paths = credential_paths(settings)
    missing = {key: path for key, path in paths.items() if not path.exists()}
    if not missing:
        return
    _check_existing_google(paths, payload)
    _write_missing(missing, payload)


def _check_existing_google(paths: dict[str, Path], payload: dict) -> None:
    for name in ("client", "oauth"):
        if paths[name].exists():
            existing = json.loads(read_credentials(paths[name]))
            actual = existing["installed"] if name == "client" else existing
            expected = payload["client"]["installed"]
            if any(actual.get(field) != expected[field] for field in ("client_id", "client_secret")):
                raise Conflict("현재 Google 설정이 패키지와 다릅니다. 기존 인증을 보호하기 위해 복원하지 않았습니다.")


def _write_missing(paths: dict[str, Path], payload: dict) -> None:
    # Encrypt and verify every value before creating any destination file.
    envelopes = {key: seal(json.dumps(payload[key])) for key in paths}
    for key, envelope in envelopes.items():
        if json.loads(unseal(envelope)) != payload[key]:
            raise AppError("인증 설정 암호화 검증에 실패했습니다.")
    created = []
    try:
        for key, path in paths.items():
            if path.exists():
                raise Conflict("설정이 변경되었습니다. 현재 설정을 확인한 뒤 다시 시도해 주세요.")
            atomic_write(path, envelopes[key])
            created.append(path)
    except (OSError, Conflict):
        for path in created:
            path.unlink(missing_ok=True)
        raise AppError("설정 복원을 완료하지 못했습니다. 기존 인증 정보는 유지됩니다.") from None
