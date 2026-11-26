"""FastAPI application factory and CLI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from monkey_api import __version__
from monkey_api.adapters.adb.runner import AdbPort
from monkey_api.adapters.ai.advisor import TuningAdvisor
from monkey_api.api.container import build_container
from monkey_api.api.errors import install_error_handlers, problem_responses
from monkey_api.api.middleware import RequestContextMiddleware
from monkey_api.api.routes import devices, sessions, system
from monkey_api.core.logging import LogStore, configure_logging, log
from monkey_api.core.settings import Settings, get_settings

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    adb: AdbPort | None = None,
    log_store: LogStore | None = None,
    advisor: TuningAdvisor | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    store = log_store or LogStore(settings.log_buffer_size, settings.logs_dir / "api.jsonl")
    configure_logging(store, settings.log_level)
    container = build_container(settings, store, adb=adb, advisor=advisor)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.sessions.recover_orphans()
        log("app", "api started", version=__version__, adb_path=settings.adb_path, data_dir=str(settings.data_dir))
        yield
        await container.sessions.shutdown()
        log("app", "api stopped")

    app = FastAPI(
        title="Monkey Test API",
        version=__version__,
        description="REST API for Android Monkey test automation. Errors are RFC 9457 problem+json.",
        lifespan=lifespan,
    )
    app.state.container = container
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    for router in (system.router, devices.router, sessions.router):
        app.include_router(router, prefix=API_PREFIX, responses=problem_responses(500))
    if settings.ui_dir is not None and (settings.ui_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.ui_dir, html=True), name="ui")
    return app


def run() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    run()
