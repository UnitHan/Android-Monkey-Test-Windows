from monkey_api.core.errors import AppError


class IconUnavailable(AppError):
    status = 404
    code = "icon_unavailable"
    title = "Not Found"


class IconToolUnavailable(AppError):
    status = 503
    code = "icon_tool_unavailable"
    title = "Service Unavailable"
