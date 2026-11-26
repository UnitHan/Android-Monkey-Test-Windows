"""Result analysis: performance statistics and improvement suggestions (pure)."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from monkey_api.domain.models import IssueCounts, PerfSample

MEMORY_PEAK_WARN_MB = 200
MEMORY_AVG_WARN_MB = 100
CPU_PEAK_WARN = 80
CPU_AVG_WARN = 50


class MetricStats(BaseModel):
    samples: int
    min: float | None
    max: float | None
    avg: float | None


class PerfStats(BaseModel):
    memory_mb: MetricStats
    cpu_percent: MetricStats


def metric_stats(values: Iterable[float | None]) -> MetricStats:
    vals = [v for v in values if v is not None]
    if not vals:
        return MetricStats(samples=0, min=None, max=None, avg=None)
    return MetricStats(samples=len(vals), min=min(vals), max=max(vals), avg=round(sum(vals) / len(vals), 1))


def perf_stats(samples: Iterable[PerfSample], run: int | None = None) -> PerfStats:
    selected = [s for s in samples if run is None or s.run == run]
    return PerfStats(
        memory_mb=metric_stats(s.memory_mb for s in selected),
        cpu_percent=metric_stats(s.cpu_percent for s in selected),
    )


def suggestions(counts: IssueCounts, stats: PerfStats) -> list[str]:
    out: list[str] = []
    if counts.crash:
        out.append(f"크래시 {counts.crash}회 발생: 크래시 로그 분석 및 예외 처리 강화 필요")
    if counts.native_crash:
        out.append(f"네이티브 크래시 {counts.native_crash}회 발생: tombstone/NDK 코드 점검 필요")
    if counts.anr:
        out.append(f"ANR {counts.anr}회 발생: 메인 스레드 작업 최적화 및 비동기 처리 필요")
    mem, cpu = stats.memory_mb, stats.cpu_percent
    if mem.max is not None and mem.max > MEMORY_PEAK_WARN_MB:
        out.append(f"메모리 사용량 높음 (최대 {round(mem.max)}MB): 메모리 누수 확인 필요")
    elif mem.avg is not None and mem.avg > MEMORY_AVG_WARN_MB:
        out.append(f"평균 메모리 사용량 주의 ({round(mem.avg)}MB): 메모리 최적화 권장")
    if cpu.max is not None and cpu.max > CPU_PEAK_WARN:
        out.append(f"CPU 사용률 높음 (최대 {round(cpu.max)}%): 연산 최적화 필요")
    elif cpu.avg is not None and cpu.avg > CPU_AVG_WARN:
        out.append(f"평균 CPU 사용률 주의 ({round(cpu.avg)}%): 성능 최적화 권장")
    if not out:
        out.append("특별한 이슈가 발견되지 않았습니다.")
    return out
