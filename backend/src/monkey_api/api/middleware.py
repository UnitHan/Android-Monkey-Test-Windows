"""Request-ID propagation + one `http` log record per request (pure ASGI, streaming-safe)."""

from __future__ import annotations

import re
import secrets
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from monkey_api.api.errors import unhandled_response
from monkey_api.core.logging import log, request_id_var

HEADER = "x-request-id"
_VALID = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(HEADER.encode(), b"").decode()
        rid = incoming if _VALID.match(incoming) else f"r_{secrets.token_hex(6)}"
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((HEADER.encode(), rid.encode()))
            await send(message)

        started_response = False

        async def tracking_send(message: Message) -> None:
            nonlocal started_response
            started_response = started_response or message["type"] == "http.response.start"
            await send_wrapper(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started_response:
                raise
            response = unhandled_response(exc)
            await response(scope, receive, send_wrapper)
        finally:
            path = scope["path"] + (f"?{scope['query_string'].decode()}" if scope.get("query_string") else "")
            level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            if scope["path"].endswith("/logs") and status < 400:
                level = "DEBUG"  # reading logs must not flood logs
            log(
                "http",
                f"{scope['method']} {scope['path']} -> {status}",
                level,
                method=scope["method"],
                path=path,
                status=status,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            request_id_var.reset(token)
