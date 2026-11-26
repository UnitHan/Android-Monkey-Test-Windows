"""Descriptive resource statistics; missing values and run gaps are never zero-filled."""

from __future__ import annotations

import math
from collections.abc import Iterable
from statistics import median, pstdev

from pydantic import BaseModel, Field

from monkey_api.domain.models import IssueCounts, PerfSample

MAX_OBSERVED_GAP_S = 10.0
CPU_CAPACITY_REFERENCE = 80.0


class MetricStats(BaseModel):
    samples: int
    min: float | None
    max: float | None
    avg: float | None
    stddev: float | None = None
    median: float | None = None
    p90: float | None = None
    p95: float | None = None
    time_weighted_avg: float | None = None
    observed_duration_s: float = 0
    reference_exceeded_s: float = 0
    longest_exceeded_s: float = 0


class PerfStats(BaseModel):
    memory_mb: MetricStats
    cpu_percent: MetricStats
    cpu_total_percent: MetricStats = Field(default_factory=lambda: metric_stats([]))


def metric_stats(values: Iterable[float | None]) -> MetricStats:
    vals = sorted(v for v in values if v is not None and math.isfinite(v) and v >= 0)
    if not vals:
        return MetricStats(samples=0, min=None, max=None, avg=None)
    return MetricStats(
        samples=len(vals),
        min=min(vals),
        max=max(vals),
        avg=round(sum(vals) / len(vals), 2),
        stddev=round(pstdev(vals), 2),
        median=median(vals),
        p90=vals[math.ceil(len(vals) * 0.90) - 1],
        p95=vals[math.ceil(len(vals) * 0.95) - 1],
    )


def _value(sample: PerfSample, metric: str) -> float | None:
    value = getattr(sample, metric)
    if sample.running is False or value is None or not math.isfinite(value) or value < 0:
        return None
    if metric == "cpu_total_percent" and value > 100:
        return None
    return value


def timed_metric(samples: list[PerfSample], metric: str) -> MetricStats:
    ordered = sorted(samples, key=lambda s: (s.run, s.at))
    stats = metric_stats(_value(s, metric) for s in ordered)
    area = duration = exceeded = longest = streak = 0.0
    for before, after in zip(ordered, ordered[1:], strict=False):
        dt = (after.at - before.at).total_seconds()
        a, b = _value(before, metric), _value(after, metric)
        if before.run != after.run or before.source != after.source or not 0 < dt <= MAX_OBSERVED_GAP_S:
            streak = 0
            continue
        if a is None or b is None:
            streak = 0
            continue
        duration += dt
        area += (a + b) / 2 * dt
        if metric == "cpu_total_percent" and min(a, b) >= CPU_CAPACITY_REFERENCE:
            exceeded += dt
            streak += dt
            longest = max(longest, streak)
        else:
            streak = 0
    return stats.model_copy(
        update={
            "time_weighted_avg": round(area / duration, 2) if duration else None,
            "observed_duration_s": round(duration, 3),
            "reference_exceeded_s": round(exceeded, 3),
            "longest_exceeded_s": round(longest, 3),
        }
    )


def perf_stats(samples: Iterable[PerfSample], run: int | None = None) -> PerfStats:
    selected = [s for s in samples if run is None or s.run == run]
    return PerfStats(**{key: timed_metric(selected, key) for key in ("memory_mb", "cpu_percent", "cpu_total_percent")})


def suggestions(counts: IssueCounts, stats: PerfStats) -> list[str]:
    """Issue facts only; resource interpretation lives in resource_assessment."""
    out: list[str] = []
    if counts.crash:
        out.append(f"크래시 {counts.crash}회 기록: 해당 스택과 발생 직전 로그로 원인을 확인하세요.")
    if counts.native_crash:
        out.append(f"네이티브 크래시 {counts.native_crash}회 기록: 해당 tombstone과 심볼 정보를 대조하세요.")
    if counts.anr:
        out.append(
            f"ANR {counts.anr}회 기록: 스레드 덤프에서 대기·락·I/O 상태를 확인하세요. 원인은 아직 확정되지 않았습니다."
        )
    if not out:
        out.append("수집된 로그에서 크래시·ANR이 기록되지 않았습니다. 성능 적합성 판정과는 별개입니다.")
    if not stats.memory_mb.samples and not stats.cpu_percent.samples:
        out.append("유효한 성능 표본이 없어 자원 사용량은 판단할 수 없습니다.")
    return out
