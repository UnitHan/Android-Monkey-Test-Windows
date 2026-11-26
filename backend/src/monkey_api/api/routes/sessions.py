"""Test sessions: commands, snapshot, event log (+SSE), issues, perf, reports, logcat."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from monkey_api.adapters.report.excel import write_excel
from monkey_api.adapters.report.html import write_html
from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.api.schemas import (
    EventList,
    IssueList,
    PerfList,
    ReportExportOut,
    SessionCreateIn,
    SessionList,
    SessionTimingOut,
)
from monkey_api.core.errors import NotFound
from monkey_api.domain.ai_evidence import AnalysisPreview
from monkey_api.domain.ai_performance import AnalysisRequest, PerformanceAnalysis
from monkey_api.domain.models import Session, SessionEvent
from monkey_api.domain.report import SessionReport
from monkey_api.domain.state_machine import TERMINAL_STATES
from monkey_api.services.event_bus import EventBus
from monkey_api.services.report_export import export_excel
from monkey_api.services.session_runner import build_session_report
from monkey_api.services.session_service import resolve_config

router = APIRouter(prefix="/sessions", tags=["sessions"])
SessionId = Path(pattern=r"^s_[A-Za-z0-9_]+$")
_NF = problem_responses(404)
_CMD = problem_responses(404, 409, 422)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=SessionList)
async def list_sessions(c: Container = Depends(get_container)) -> SessionList:
    return SessionList(items=c.ledger.repo.list())


@router.post("", response_model=Session, status_code=201, responses=_CMD)
async def create_session(body: SessionCreateIn, c: Container = Depends(get_container)) -> Session:
    config = resolve_config(body.device_serial, body.package, body.preset_id, body.overrides)
    return c.sessions.create(config)


@router.get("/{session_id}", response_model=Session, responses=_NF)
async def get_session(session_id: str = SessionId, c: Container = Depends(get_container)) -> Session:
    return c.ledger.get(session_id)


@router.get("/{session_id}/timing", response_model=SessionTimingOut, responses=_NF)
async def get_timing(session_id: str = SessionId, c: Container = Depends(get_container)) -> SessionTimingOut:
    """Deadline policy, current progress and measured per-segment execution history."""
    session = c.ledger.get(session_id)
    target = session.config.target_minutes_per_run
    measured = [run.execution_duration_s for run in session.runs]
    return SessionTimingOut(
        session_id=session.id,
        mode="time" if target is not None else "events",
        completion_policy="extend_until_deadline" if target is not None else "event_count",
        target_per_run_s=target * 60 if target is not None else None,
        target_total_s=target * 60 * session.config.repeats if target is not None else None,
        completed_execution_s=round(sum(v for v in measured if v is not None), 3)
        if all(v is not None for v in measured)
        else None,
        extension_count=sum(max(0, len(r.segments) - 1) for r in session.runs)
        + (
            max(0, session.progress.segment - 1)
            if session.progress.current_run not in {r.run for r in session.runs}
            else 0
        ),
        progress=session.progress,
        runs=session.runs,
    )


@router.post("/{session_id}/start", response_model=Session, status_code=202, responses=_CMD)
async def start_session(session_id: str = SessionId, c: Container = Depends(get_container)) -> Session:
    return c.sessions.start(session_id)


@router.post("/{session_id}/stop", response_model=Session, status_code=202, responses=_CMD)
async def stop_session(session_id: str = SessionId, c: Container = Depends(get_container)) -> Session:
    return c.sessions.stop(session_id)


@router.delete("/{session_id}", status_code=204, responses=_CMD)
async def delete_session(session_id: str = SessionId, c: Container = Depends(get_container)) -> None:
    c.sessions.delete(session_id)


@router.get("/{session_id}/events", response_model=EventList, responses=_NF)
async def list_events(
    session_id: str = SessionId,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=10_000),
    c: Container = Depends(get_container),
) -> EventList:
    items = c.ledger.repo.events(session_id, after_seq, limit)
    return EventList(items=items, last_seq=items[-1].seq if items else after_seq)


def _sse(event: SessionEvent) -> str:
    head = f"id: {event.seq}\n" if event.seq else ""
    return f"{head}event: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"


@router.get(
    "/{session_id}/events/stream",
    responses={200: {"content": {"text/event-stream": {}}}, **_NF},
    response_class=StreamingResponse,
)
async def stream_events(
    session_id: str = SessionId,
    after_seq: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> StreamingResponse:
    """Server-Sent Events. Replays persisted events after `after_seq` (or Last-Event-ID), then live."""
    c.ledger.get(session_id)
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after_seq
    bus: EventBus = c.ledger.bus

    async def gen() -> AsyncIterator[str]:
        sub = bus.subscribe(session_id)  # registered before replay so nothing is missed
        try:
            seen = cursor
            for event in c.ledger.repo.events(session_id, cursor, limit=100_000):
                seen = event.seq
                yield _sse(event)
            if c.ledger.get(session_id).state in TERMINAL_STATES:
                return
            while (event := await sub.next()) is not None:
                if event.seq == 0 or event.seq > seen:
                    seen = max(seen, event.seq)
                    yield _sse(event)
        finally:
            sub.close()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/{session_id}/issues", response_model=IssueList, responses=_NF)
async def list_issues(session_id: str = SessionId, c: Container = Depends(get_container)) -> IssueList:
    c.ledger.get(session_id)
    return IssueList(items=c.ledger.repo.issues(session_id))


@router.get("/{session_id}/perf", response_model=PerfList, responses=_NF)
async def list_perf(
    session_id: str = SessionId, run: int | None = Query(default=None, ge=1), c: Container = Depends(get_container)
) -> PerfList:
    c.ledger.get(session_id)
    return PerfList(items=[p for p in c.ledger.repo.perf(session_id) if run is None or p.run == run])


@router.get("/{session_id}/report", response_model=SessionReport, responses=_NF)
async def get_report(session_id: str = SessionId, c: Container = Depends(get_container)) -> SessionReport:
    return build_session_report(c.ledger, session_id)


@router.get("/{session_id}/performance-analysis/preview", response_model=AnalysisPreview, responses=_CMD)
async def preview_performance_analysis(
    session_id: str = SessionId,
    c: Container = Depends(get_container),
) -> AnalysisPreview:
    return c.performance_analysis.preview(session_id)


@router.post(
    "/{session_id}/performance-analysis",
    response_model=PerformanceAnalysis,
    responses=problem_responses(404, 409, 422, 502, 503, 504),
)
async def analyze_performance(
    body: AnalysisRequest,
    session_id: str = SessionId,
    c: Container = Depends(get_container),
) -> PerformanceAnalysis:
    return await c.performance_analysis.analyze(session_id, body)


@router.get("/{session_id}/report.html", response_class=FileResponse, responses=_NF)
async def get_report_html(session_id: str = SessionId, c: Container = Depends(get_container)) -> FileResponse:
    path = write_html(build_session_report(c.ledger, session_id), c.ledger.repo.dir_for(session_id) / "report.html")
    return FileResponse(path, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})


@router.get("/{session_id}/report.xlsx", response_class=FileResponse, responses=_NF)
async def get_report_xlsx(session_id: str = SessionId, c: Container = Depends(get_container)) -> FileResponse:
    path = write_excel(build_session_report(c.ledger, session_id), c.ledger.repo.dir_for(session_id) / "report.xlsx")
    return FileResponse(path, media_type=_XLSX, filename=f"{session_id}.xlsx")


@router.get("/{session_id}/logcat/{run}", response_class=PlainTextResponse, responses=_NF)
async def get_logcat(
    session_id: str = SessionId, run: int = Path(ge=1), c: Container = Depends(get_container)
) -> PlainTextResponse:
    c.ledger.get(session_id)
    path = c.ledger.repo.dir_for(session_id) / f"logcat_run_{run}.log"
    if not path.exists():
        raise NotFound(f"no logcat for run {run}", run=run)
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))


@router.post("/{session_id}/exports/xlsx", response_model=ReportExportOut, responses=_NF)
async def export_report_xlsx(session_id: str = SessionId, c: Container = Depends(get_container)) -> ReportExportOut:
    path = export_excel(c.ledger, session_id, c.settings.export_dir)
    return ReportExportOut(path=str(path), filename=path.name)
