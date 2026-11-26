"""Typed application errors. Mapped to RFC 9457 problem+json once, in api/errors.py."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status: int = 500
    code: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class NotFound(AppError):
    status = 404
    code = "not_found"
    title = "Not Found"


class DeviceNotFound(NotFound):
    code = "device_not_found"


class SessionNotFound(NotFound):
    code = "session_not_found"


class Conflict(AppError):
    status = 409
    code = "conflict"
    title = "Conflict"


class InvalidTransition(Conflict):
    code = "invalid_transition"


class DeviceBusy(Conflict):
    code = "device_busy"


class SessionActive(Conflict):
    code = "session_active"


class ValidationFailed(AppError):
    status = 422
    code = "validation_failed"
    title = "Unprocessable Content"


class AdbError(AppError):
    """ADB command failed (non-zero exit or unusable output)."""

    status = 502
    code = "adb_error"
    title = "Bad Gateway"


class AdbUnavailable(AdbError):
    status = 503
    code = "adb_unavailable"
    title = "Service Unavailable"


class AdbTimeout(AdbError):
    status = 504
    code = "adb_timeout"
    title = "Gateway Timeout"


class DeviceOffline(AdbError):
    code = "device_offline"
