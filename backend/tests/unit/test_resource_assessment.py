from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from monkey_api.domain.analysis import metric_stats, perf_stats
from monkey_api.domain.models import PerfSample
from monkey_api.domain.resource_assessment import assess_resources

START = datetime(2026, 11, 26, tzinfo=UTC)


def sample(second, memory=257, cpu=10, **kwargs):
    return PerfSample(
        at=START + timedelta(seconds=second),
        run=1,
        memory_mb=memory,
        cpu_percent=cpu * 8,
        cpu_total_percent=cpu,
        source="appkium",
        **kwargs,
    )


def assess(samples, execution=80, events=100):
    session = SimpleNamespace(
        runs=[SimpleNamespace(execution_duration_s=execution, events_sent=events)],
        state=SimpleNamespace(value="completed"),
    )
    return assess_resources(session, samples, perf_stats(samples))


def test_statistics_exclude_missing_nonfinite_and_negative_but_keep_zero():
    s = metric_stats([None, float("nan"), float("inf"), -1, 0, 10, 20, 30])
    assert s.samples == 4 and s.avg == 15 and s.min == 0 and s.max == 30
    assert s.stddev == 11.18 and s.median == 15 and s.p90 == s.p95 == 30
    assert metric_stats([]).avg is None


def test_time_weighting_uses_timestamps_not_sampling_frequency():
    s = perf_stats([sample(0, 0), sample(1, 0), sample(10, 100)]).memory_mb
    assert s.avg == 33.33 and s.time_weighted_avg == 45 and s.observed_duration_s == 10


def test_missing_values_long_gaps_runs_and_collectors_are_not_bridged():
    points = [sample(0, 0), sample(2, 10), sample(4, None), sample(6, 20), sample(30, 30), sample(32, 40)]
    s = perf_stats(points).memory_mb
    assert s.observed_duration_s == 4 and s.time_weighted_avg == 20
    changed = sample(34, 50).model_copy(update={"run": 2})
    switched = sample(36, 60).model_copy(update={"run": 2, "source": "adb"})
    assert perf_stats([*points, changed, switched]).memory_mb.observed_duration_s == 4


def test_short_screenshot_like_session_is_inconclusive_not_leak_or_optimization():
    points = [sample(i * 2, memory=257, cpu=90 / 8).model_copy(update={"cpu_total_percent": None}) for i in range(9)]
    result = assess(points, execution=24, events=0)
    assert all(f.status == "insufficient" for f in result.findings)
    assert "누수를 판단하지 않습니다" in result.findings[0].recommendation
    assert "기기 전체 90%로 해석하지 않습니다" in result.findings[1].recommendation
    assert any("주입 이벤트가 기록되지" in note for note in result.notes)


def test_large_stable_memory_is_not_automatically_a_leak():
    points = [sample(i * 2, memory=1024) for i in range(41)]
    memory = assess(points).findings[0]
    assert memory.status == "observed"
    assert "예산" in memory.recommendation
    assert perf_stats(points).memory_mb.stddev == 0


def test_equal_cpu_peaks_get_different_context_for_burst_and_sustained_load():
    burst = [sample(i * 2, cpu=90 if i == 20 else 10) for i in range(41)]
    sustained = [sample(i * 2, cpu=90) for i in range(41)]
    b, s = assess(burst).findings[1], assess(sustained).findings[1]
    assert b.status == "observed" and "일시적 피크" in b.title
    assert s.status == "review" and "지속 사용" in s.title
    assert "결함 판정은 아닙니다" in s.recommendation
    assert perf_stats(burst).cpu_total_percent.p90 == 10
    assert perf_stats(sustained).cpu_total_percent.longest_exceeded_s == 80


@pytest.mark.parametrize("duration", [None, 1000])
def test_unknown_or_low_coverage_does_not_produce_strong_conclusions(duration):
    points = [sample(i * 2, cpu=99) for i in range(41)]
    assert all(f.status == "insufficient" for f in assess(points, execution=duration).findings)


def test_stopped_app_samples_are_not_resource_usage_observations():
    points = [sample(0, running=False), sample(2, running=False)]
    assert perf_stats(points).memory_mb.samples == 0
    assert perf_stats(points).cpu_total_percent.samples == 0
