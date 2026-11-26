"""Session report model and builder (pure)."""

from __future__ import annotations

from pydantic import BaseModel

from monkey_api.domain.analysis import PerfStats, perf_stats, suggestions
from monkey_api.domain.models import Issue, PerfSample, Session


class RunPerf(BaseModel):
    run: int
    stats: PerfStats


class SessionReport(BaseModel):
    session: Session
    total_events_sent: int
    total_duration_s: float
    issues: list[Issue]
    perf: PerfStats
    per_run: list[RunPerf]
    suggestions: list[str]
    samples: list[PerfSample]


def build_report(session: Session, issues: list[Issue], samples: list[PerfSample]) -> SessionReport:
    overall = perf_stats(samples)
    return SessionReport(
        session=session,
        total_events_sent=sum(r.events_sent for r in session.runs),
        total_duration_s=round(sum(r.duration_s for r in session.runs), 1),
        issues=issues,
        perf=overall,
        per_run=[RunPerf(run=r.run, stats=perf_stats(samples, r.run)) for r in session.runs],
        suggestions=suggestions(session.issue_counts, overall),
        samples=samples,
    )
