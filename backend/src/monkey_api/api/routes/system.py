"""Health, presets, estimates, API logs."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from monkey_api import __version__
from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.api.schemas import AdbStatus, EstimateIn, Health, LogList, LogRecordOut, PresetList
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import LogLevel, LogQuery, LogSource
from monkey_api.domain.estimation import Estimate, estimate_duration
from monkey_api.domain.presets import PRESETS

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Health)
async def health(c: Container = Depends(get_container)) -> Health:
    try:
        version: str | None = await c.ops.version()
    except AdbError:
        version = None
    return Health(
        status="ok" if version else "degraded",
        version=__version__,
        adb=AdbStatus(path=c.settings.adb_path, available=version is not None, version=version),
    )


@router.get("/presets", response_model=PresetList)
async def list_presets() -> PresetList:
    return PresetList(items=list(PRESETS))


@router.post("/estimates", response_model=Estimate, responses=problem_responses(422))
async def estimate(body: EstimateIn) -> Estimate:
    return estimate_duration(body.events, body.repeats, body.throttle_ms, body.target_minutes_per_run)


@router.get("/logs", response_model=LogList, responses=problem_responses(422))
async def query_logs(
    level: LogLevel | None = None,
    source: LogSource | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    since_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=5000),
    c: Container = Depends(get_container),
) -> LogList:
    records = c.log_store.query(LogQuery(level, source, session_id, request_id, since_seq, limit))
    return LogList(
        items=[LogRecordOut(**asdict(r)) for r in records],
        last_seq=records[-1].seq if records else since_seq,
    )
