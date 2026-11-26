"""Portable authenticated encryption; deployment password is never shipped in the app."""

import base64
import json
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from monkey_api.core.errors import ValidationFailed

_AAD = b"monkey-deployment-v1:scrypt-32768-8-1:aes-256-gcm"


def _key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode("utf-8"))


def encrypt_bundle(payload: dict, password: str) -> str:
    if len(password) < 16:
        raise ValidationFailed("배포 암호는 16자 이상이어야 합니다.")
    salt, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    encrypted = AESGCM(_key(password, salt)).encrypt(nonce, raw, _AAD)
    return json.dumps(
        {
            "format": "monkey-deployment",
            "version": 1,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(encrypted).decode(),
        }
    )


def decrypt_bundle(content: str, password: str) -> dict:
    try:
        if len(content) > 128_000 or not 1 <= len(password) <= 512:
            raise ValueError
        data = json.loads(content)
        if data["format"] != "monkey-deployment" or data["version"] != 1:
            raise ValueError
        salt = base64.b64decode(data["salt"], validate=True)
        nonce = base64.b64decode(data["nonce"], validate=True)
        if len(salt) != 32 or len(nonce) != 12:
            raise ValueError
        encrypted = base64.b64decode(data["ciphertext"], validate=True)
        payload = json.loads(AESGCM(_key(password, salt)).decrypt(nonce, encrypted, _AAD))
        if not isinstance(payload, dict):
            raise ValueError
        return payload
    except (InvalidTag, ValueError, TypeError, KeyError):
        raise ValidationFailed("배포 암호가 올바르지 않거나 설치 설정 파일이 손상되었습니다.") from None
