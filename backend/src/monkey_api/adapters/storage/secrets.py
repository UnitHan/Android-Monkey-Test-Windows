"""User-bound Windows DPAPI envelopes. No application master key or plaintext fallback."""

import base64
import ctypes
import json
import os
import secrets
import tempfile
from ctypes import wintypes
from pathlib import Path


class SecretStoreError(OSError):
    def __init__(self) -> None:
        super().__init__("암호화 저장소를 열지 못했습니다. 저장한 Windows 계정으로 실행하거나 다시 등록해 주세요.")


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(value: bytes) -> Blob:
    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    return Blob(len(value), buffer)


def _crypt(value: bytes, salt: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise SecretStoreError()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    source, entropy, result = _blob(value), _blob(salt), Blob()
    # CRYPTPROTECT_UI_FORBIDDEN, deliberately NOT CRYPTPROTECT_LOCAL_MACHINE.
    if not operation(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(result)):
        raise SecretStoreError()
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel.LocalFree(result.data)


def seal(content: str) -> str:
    salt = secrets.token_bytes(32)
    ciphertext = _crypt(content.encode("utf-8"), salt)
    return json.dumps(
        {
            "format": "monkey-dpapi",
            "version": 1,
            "salt": base64.b64encode(salt).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
    )


def unseal(content: str) -> str:
    try:
        envelope = json.loads(content)
        if envelope["format"] != "monkey-dpapi" or envelope["version"] != 1:
            raise ValueError
        salt = base64.b64decode(envelope["salt"], validate=True)
        if len(salt) != 32:
            raise ValueError
        return _crypt(base64.b64decode(envelope["ciphertext"], validate=True), salt, decrypt=True).decode("utf-8")
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise SecretStoreError() from None


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def write_secret(path: Path, content: str) -> None:
    envelope = seal(content)
    if unseal(envelope) != content:
        raise SecretStoreError()
    atomic_write(path, envelope)


def read_secret(path: Path) -> str:
    return unseal(path.read_text(encoding="utf-8"))


def read_credentials(path: Path) -> str:
    """Migrate legacy JSON atomically, only after a verified encryption round trip."""
    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise SecretStoreError()
    if "format" in data:
        return unseal(content)
    write_secret(path, content)
    return content
