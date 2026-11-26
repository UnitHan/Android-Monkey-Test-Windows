"""Session report model and builder (pure)."""

from __future__ import annotations

from pydantic import BaseModel

from monkey_api.domain.ai_performance import PerformanceAnalysis
from monkey_api.domain.analysis import PerfStats, perf_stats, suggestions
from monkey_api.domain.models import Issue, PerfSample, Session
from monkey_api.domain.resource_assessment import ResourceAssessment, assess_resources


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
    issue_suggestions: list[str]
    samples: list[PerfSample]
    resource_assessment: ResourceAssessment
    ai_performance: PerformanceAnalysis | None = None


def build_report(session: Session, issues: list[Issue], samples: list[PerfSample]) -> SessionReport:
    overall = perf_stats(samples)
    assessment = assess_resources(session, samples, overall)
    return SessionReport(
        session=session,
        total_events_sent=sum(r.events_sent for r in session.runs),
        total_duration_s=round(sum(r.duration_s for r in session.runs), 1),
        issues=issues,
        perf=overall,
        per_run=[RunPerf(run=r.run, stats=perf_stats(samples, r.run)) for r in session.runs],
        suggestions=suggestions(session.issue_counts, overall)
        + [f"{f.title} — {f.evidence}. {f.recommendation}" for f in assessment.findings],
        issue_suggestions=suggestions(session.issue_counts, overall),
        samples=samples,
        resource_assessment=assessment,
    )
