"""Sanitized errors: OAuth tokens and upstream response bodies never reach API logs."""

from monkey_api.core.errors import AppError


class PlayError(AppError):
    status = 502
    code = "play_error"
    title = "Bad Gateway"


class PlayNotConfigured(PlayError):
    status = 503
    code = "play_not_configured"
    title = "Service Unavailable"


class PlayAuthError(PlayError):
    status = 401
    code = "play_auth_required"
    title = "Unauthorized"


class PlayForbidden(PlayError):
    status = 403
    code = "play_forbidden"
    title = "Forbidden"


class PlayUnsupported(PlayForbidden):
    code = "play_unsupported_package"


class PlayNotFound(PlayError):
    status = 404
    code = "play_not_found"
    title = "Not Found"


class PlayRateLimited(PlayError):
    status = 429
    code = "play_rate_limited"
    title = "Too Many Requests"


class PlayTimeout(PlayError):
    status = 504
    code = "play_timeout"
    title = "Gateway Timeout"
