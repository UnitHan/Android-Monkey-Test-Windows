"""Allowlisted numerical evidence; no log text, identifiers, credentials or raw samples."""

import hashlib
import json

from pydantic import BaseModel

from monkey_api.domain.ai_performance import POLICY_VERSION, AIConclusion, AIFinding
from monkey_api.domain.analysis import PerfStats
from monkey_api.domain.models import IssueCounts, SessionState
from monkey_api.domain.report import RunPerf, SessionReport
from monkey_api.domain.resource_assessment import ResourceAssessment


class PerformanceEvidence(BaseModel):
    policy_version: str = POLICY_VERSION
    state: SessionState
    planned_runs: int
    recorded_runs: int
    events_sent: int
    target_duration_s: float | None
    issue_counts: IssueCounts
    statistics: PerfStats
    per_run: list[RunPerf]
    assessment: ResourceAssessment
    baseline_available: bool = False
    app_budget_available: bool = False


class AnalysisPreview(BaseModel):
    input_hash: str
    model: str
    configured: bool
    evidence: PerformanceEvidence


def evidence_for(report: SessionReport) -> PerformanceEvidence:
    s = report.session
    minutes = s.config.target_minutes_per_run
    return PerformanceEvidence(
        state=s.state,
        planned_runs=s.config.repeats,
        recorded_runs=len(s.runs),
        events_sent=report.total_events_sent,
        target_duration_s=minutes * 60 * s.config.repeats if minutes is not None else None,
        issue_counts=s.issue_counts,
        statistics=report.perf,
        per_run=report.per_run,
        assessment=report.resource_assessment,
    )


def evidence_hash(evidence: PerformanceEvidence) -> str:
    data = json.dumps(evidence.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def constrain_conclusion(result: AIConclusion, evidence: PerformanceEvidence) -> tuple[AIConclusion, list[str]]:
    result = result.model_copy(deep=True)
    guards = []
    for metric, finding in zip(("memory", "cpu"), evidence.assessment.findings, strict=True):
        if finding.status == "insufficient":
            setattr(
                result,
                metric,
                AIFinding(verdict="inconclusive", reason=finding.evidence + ". " + finding.recommendation),
            )
            guards.append(f"{metric}: 수집 근거 부족으로 판단 보류")
    counts = evidence.issue_counts
    if counts.crash + counts.native_crash + counts.anr > 0:
        result.stability = AIFinding(
            verdict="abnormal",
            reason=f"크래시 {counts.crash + counts.native_crash}건, ANR {counts.anr}건이 기록됐습니다.",
        )
        guards.append("기록된 크래시·ANR을 정상 판정에서 제외")
    incomplete = evidence.state != "completed" or evidence.events_sent == 0
    incomplete = incomplete or evidence.recorded_runs != evidence.planned_runs
    execution = evidence.assessment.execution_duration_s
    if evidence.target_duration_s and (execution is None or execution < evidence.target_duration_s * 0.98):
        incomplete = True
        guards.append("설정한 실행 시간 대비 관측된 실행 시간이 부족합니다.")
    if incomplete:
        guards.append("미완료 또는 이벤트 미주입 세션: 전체 테스트 정상 여부 판단 보류")
    _overall(result, incomplete)
    return result, guards


def _overall(result: AIConclusion, incomplete: bool) -> None:
    original = result.verdict
    severities = [result.memory.verdict, result.cpu.verdict, result.stability.verdict]
    if incomplete or "inconclusive" in severities:
        result.verdict = "inconclusive"
        result.summary = "전체 성능의 정상 여부는 판단 보류입니다. 항목별 근거와 이상 징후를 확인하세요."
    elif "abnormal" in severities:
        result.verdict = "abnormal"
    elif "attention" in severities and result.verdict == "normal":
        result.verdict = "attention"
    if result.verdict != original and result.verdict in ("abnormal", "attention"):
        result.summary = "항목별 관측 근거에서 주의 또는 이상 징후가 확인되었습니다. 세부 판정과 권고사항을 확인하세요."
