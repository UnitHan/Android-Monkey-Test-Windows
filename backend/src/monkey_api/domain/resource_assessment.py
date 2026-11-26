"""Conservative interpretation of measured evidence, never a universal app performance gate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from monkey_api.domain.analysis import CPU_CAPACITY_REFERENCE, MetricStats, PerfStats
from monkey_api.domain.models import PerfSample, Session

MIN_SAMPLES = 30
MIN_OBSERVED_S = 60.0
MIN_COVERAGE = 0.8
SUSTAINED_CPU_S = 30.0


class ResourceFinding(BaseModel):
    metric: str
    status: Literal["insufficient", "observed", "review"]
    title: str
    evidence: str
    recommendation: str
    coverage_percent: float | None


class ResourceAssessment(BaseModel):
    execution_duration_s: float | None
    sample_count: int
    collectors: list[str]
    findings: list[ResourceFinding]
    notes: list[str]


def _finding(metric: str, name: str, stats: MetricStats, execution: float | None) -> ResourceFinding:
    coverage = min(100, stats.observed_duration_s / execution * 100) if execution and execution > 0 else None
    sufficient = stats.samples >= MIN_SAMPLES and stats.observed_duration_s >= MIN_OBSERVED_S
    sufficient = sufficient and coverage is not None and coverage >= MIN_COVERAGE * 100
    evidence = (
        f"유효 표본 {stats.samples}개 · 관측 구간 {stats.observed_duration_s:.1f}초 · 실행 시간 대비 {coverage:.1f}%"
        if coverage is not None
        else f"유효 표본 {stats.samples}개 · 관측 구간 {stats.observed_duration_s:.1f}초 · 실행 시간 정보 없음"
    )
    if stats.samples:
        evidence += f" · 평균 {stats.avg:g}, P90 {stats.p90:g}, 최대 {stats.max:g}, 표준편차 {stats.stddev:g}"
    return ResourceFinding(
        metric=metric,
        status="observed" if sufficient else "insufficient",
        title=f"{name}: {'관측 결과' if sufficient else '판단 보류'}",
        evidence=evidence,
        recommendation="표본 30개·유효 관측 60초·실행 시간 대비 80% 이상을 확보한 뒤 비교하세요."
        if not sufficient
        else "동일 기기·동일 시나리오의 기준 버전 및 앱별 성능 예산과 비교하세요.",
        coverage_percent=round(coverage, 1) if coverage is not None else None,
    )


def _memory(stats: MetricStats, execution: float | None) -> ResourceFinding:
    result = _finding("memory_mb", "메모리 PSS", stats, execution)
    result.recommendation += " 절대 사용량이나 최대값만으로 메모리 누수를 판단하지 않습니다."
    return result


def _cpu(stats: PerfStats, execution: float | None) -> ResourceFinding:
    normalized = stats.cpu_total_percent
    if not normalized.samples:
        result = _finding("cpu_percent", "CPU 코어 합산", stats.cpu_percent, execution)
        result.status, result.title = "insufficient", "CPU: 기기 용량 대비 부하 판단 보류"
        result.recommendation = (
            "기기 전체 용량 대비 CPU 비율이 없습니다. 코어 합산 90%를 기기 전체 90%로 해석하지 않습니다."
        )
        return result
    result = _finding("cpu_total_percent", "CPU 기기 전체 용량 대비", normalized, execution)
    result.evidence += (
        f" · 참고선 {CPU_CAPACITY_REFERENCE:g}% 이상 관측 {normalized.reference_exceeded_s:.1f}초"
        f" · 최장 연속 {normalized.longest_exceeded_s:.1f}초"
    )
    if result.status == "insufficient":
        return result
    sustained = normalized.longest_exceeded_s >= SUSTAINED_CPU_S
    widespread = (normalized.p90 or 0) >= CPU_CAPACITY_REFERENCE
    if sustained and widespread:
        result.status, result.title = "review", "CPU: 지속 사용 구간 확인"
        result.recommendation = (
            "P90이 참고선 이상이며 연속 30초 이상 사용 구간이 관측됐습니다. 사용자 동작과 프로파일을 대조하세요. "
            "결함 판정은 아닙니다."
        )
    elif normalized.max is not None and normalized.max >= CPU_CAPACITY_REFERENCE:
        result.title = "CPU: 일부 구간 상승 관측" if sustained else "CPU: 일시적 피크 관측"
        result.recommendation = (
            "참고선 이상 피크가 있지만 연속 30초 이상 관측되지는 않았습니다. 최대값만으로 최적화를 요구하지 않습니다."
        )
        if sustained:
            result.recommendation = (
                "일부 상승 구간이 있으나 P90은 참고선 미만입니다. 전체 실행의 지속 부하로 일반화하지 않습니다."
            )
    else:
        result.recommendation = (
            "관측 구간에서 참고선 이상 지속 사용은 확인되지 않았습니다. "
            "앱별 성능 목표 충족 여부는 별도 비교가 필요합니다."
        )
    return result


def assess_resources(session: Session, samples: list[PerfSample], stats: PerfStats) -> ResourceAssessment:
    durations = [r.execution_duration_s for r in session.runs]
    execution = sum(durations) if durations and all(v is not None for v in durations) else None
    notes = [
        "평균·표준편차(모집단)·P90/P95는 유효 표본 기준입니다. P90은 정렬된 표본의 90% 지점(올림 순위)입니다.",
        "시간 가중 평균은 인접 표본 사이를 선형 보간합니다. "
        "회차·수집원 변경, 결측, 10초 초과 공백은 연결하지 않습니다.",
        "관측 구간은 유효 인접 표본 사이 시간의 합입니다. 누락된 구간을 정상 상태로 가정하지 않습니다.",
        "CPU 코어 합산은 100%를 넘을 수 있습니다. 부하 참고선은 기기 전체 용량 대비 CPU에만 적용합니다.",
        "판단 보류/관측/구간 확인은 자료 해석이며 합격·불합격 기준이 아닙니다. 메모리 예산과 기준 버전은 미설정입니다.",
        "PSS는 수집기가 약 5초마다 갱신하므로 인접 표본에 같은 측정값이 반복될 수 있습니다.",
    ]
    if session.state.value != "completed":
        notes.append("완료되지 않은 세션의 결과입니다. 수집된 범위만 해석하며 전체 테스트를 대표하지 않습니다.")
    if not any(r.events_sent > 0 for r in session.runs):
        notes.append(
            "주입 이벤트가 기록되지 않았습니다. 이 자료를 Monkey 부하 테스트의 성능 검증으로 인정할 수 없습니다."
        )
    return ResourceAssessment(
        execution_duration_s=round(execution, 3) if execution is not None else None,
        sample_count=len(samples),
        collectors=sorted({s.source for s in samples}),
        findings=[_memory(stats.memory_mb, execution), _cpu(stats, execution)],
        notes=notes,
    )
