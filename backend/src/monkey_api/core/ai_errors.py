from monkey_api.core.errors import AppError


class AIUnavailable(AppError):
    status = 503
    code = "ai_unavailable"
    title = "Service Unavailable"


class AIResponseError(AppError):
    status = 502
    code = "ai_response_error"
    title = "Bad Gateway"


class AITimeout(AppError):
    status = 504
    code = "ai_timeout"
    title = "Gateway Timeout"
