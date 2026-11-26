import json
import statistics
from pathlib import Path

import pytest

from monkey_api.core.errors import InvalidTransition, ValidationFailed
from monkey_api.domain.adaptive import RunSample, next_run_events, precision_score
from monkey_api.domain.analysis import perf_stats, suggestions
from monkey_api.domain.estimation import (
    EFFICIENCY,
    FINALIZE_S,
    PREP_PER_RUN_S,
    estimate_duration,
    expected_events,
    expected_run_s,
    monkey_event_budget,
    run_time_limit_s,
)
from monkey_api.domain.models import EventMix, IssueCounts, PerfSample, SessionOverrides
from monkey_api.domain.models import SessionState as S
from monkey_api.domain.monkey_command import build_monkey_args, random_seed, seed_for_run
from monkey_api.domain.presets import PRESETS, get_preset
from monkey_api.domain.state_machine import can_transition, ensure_transition
from monkey_api.services.session_service import resolve_config


def test_state_machine_happy_path_and_illegal_moves() -> None:
    path = [S.CREATED, S.PREPARING, S.RUNNING, S.STOPPING, S.CANCELLED]
    for a, b in zip(path, path[1:], strict=False):
        assert can_transition(a, b)
    assert can_transition(S.RUNNING, S.COMPLETED)
    with pytest.raises(InvalidTransition):
        ensure_transition(S.COMPLETED, S.RUNNING)
    with pytest.raises(InvalidTransition):
        ensure_transition(S.CREATED, S.RUNNING)


def test_presets_are_valid_and_unique() -> None:
    assert len({p.id for p in PRESETS}) == len(PRESETS)
    deep = get_preset("deep")
    assert deep and deep.fixed_seed == 4850 and deep.throttle_ms == 150 and deep.target_minutes_per_run == 18


def test_event_mix_sum_validated() -> None:
    with pytest.raises(ValueError, match="sum"):
        EventMix(touch=60, motion=50)


def test_monkey_args_are_a_list_without_shell_quoting() -> None:
    cfg = resolve_config("SER", "com.example.app", "deep", None)
    args = build_monkey_args(cfg, seed=4850, events=22000)
    assert args[:4] == ["shell", "monkey", "-p", "com.example.app"]
    assert args[args.index("-s") + 1] == "4850"
    assert "--bugreport" in args and args[-3:] == ["-v", "-v", "22000"]
    assert args[args.index("--pct-touch") + 1] == "30"
    assert "--monitor-native-crashes" not in args  # old device tombstones must not block injection


def test_seed_selection() -> None:
    assert 1000 <= random_seed() <= 9999
    assert seed_for_run(resolve_config("S", "com.a.b", "deep", None)) == 4850
    assert seed_for_run(resolve_config("S", "com.a.b", "reproduce", SessionOverrides(seed=1234))) == 1234


def test_resolve_config_overrides_and_manual_seed_requirement() -> None:
    cfg = resolve_config("S", "com.a.b", "standard", SessionOverrides(events=500, repeats=2, throttle_ms=0))
    assert (cfg.events, cfg.repeats, cfg.throttle_ms, cfg.adaptive) == (500, 2, 0, True)
    with pytest.raises(ValidationFailed):
        resolve_config("S", "com.a.b", "reproduce", None)
    with pytest.raises(ValidationFailed):
        resolve_config("S", "com.a.b", "nope", None)


def test_adaptive_events_clamped_between_base_and_margin() -> None:
    assert next_run_events(1000, [], 600, 0.2) == 1000  # no history
    fast = [RunSample(events_sent=1000, duration_s=300)]  # 3.33 ev/s * 600 = 2000 -> clamp 1200
    assert next_run_events(1000, fast, 600, 0.2) == 1200
    slow = [RunSample(events_sent=1000, duration_s=1200)]  # 500 < base -> base
    assert next_run_events(1000, slow, 600, 0.2) == 1000
    exact = [RunSample(events_sent=1000, duration_s=550)]
    assert next_run_events(1000, exact, 600, 0.2) == 1090


def test_precision_score_scale() -> None:
    assert precision_score(1080, 1080) == 100
    assert precision_score(1110, 1080) == 95
    assert precision_score(5000, 1080) == 0


def test_estimate_time_boxed_follows_time_rule() -> None:
    est = estimate_duration(None, 6, 200, target_minutes_per_run=15)
    assert est.mode == "time" and est.per_run_s == 900 and est.buffer_s == 0
    assert est.total_s == 900 * 6 + PREP_PER_RUN_S * 6 + FINALIZE_S
    assert est.per_run_events == expected_events(15, 200) == 12500
    assert run_time_limit_s(1000, 100, 7) == 420


def test_estimate_event_based_uses_calibrated_efficiency() -> None:
    est = estimate_duration(3000, 2, 200)  # 3000 x 0.2 s x 0.36 = 216 s per run
    assert est.mode == "events" and est.per_run_s == 216 and est.buffer_s == 43.2
    assert run_time_limit_s(3000, 200, None) == pytest.approx(216 * 1.5 + 60)
    with pytest.raises(ValueError):
        estimate_duration(None, 1, 200)


def test_time_boxed_monkey_gets_headroom() -> None:
    assert monkey_event_budget(1000, 7) == 1300
    assert monkey_event_budget(1000, None) == 1000


@pytest.mark.parametrize("preset", [p for p in PRESETS if p.target_minutes_per_run is not None], ids=lambda p: p.id)
def test_time_boxed_presets_are_consistent_with_time_rule(preset) -> None:  # type: ignore[no-untyped-def]
    target_s = preset.target_minutes_per_run * 60
    # expected run time of the preset's events == target (events derived, not hand-typed)
    assert abs(expected_run_s(preset.events, preset.throttle_ms) - target_s) < 1
    # even at the fastest measured efficiency, the headroom budget cannot finish before the target
    fastest_s = monkey_event_budget(preset.events, preset.target_minutes_per_run) * preset.throttle_ms / 1000 * 0.30
    assert fastest_s > target_s
    est = estimate_duration(preset.events, preset.repeats, preset.throttle_ms, preset.target_minutes_per_run)
    assert est.total_s == target_s * preset.repeats + PREP_PER_RUN_S * preset.repeats + FINALIZE_S


def test_preset_total_execution_minutes() -> None:
    rule = {"smoke": 30, "standard": 60, "deep": 180, "extreme": 480}
    assert get_preset("quick") is None
    for pid, minutes in rule.items():
        p = get_preset(pid)
        assert p and p.target_minutes_per_run * p.repeats == minutes


def test_efficiency_matches_measured_calibration() -> None:
    data = json.loads((Path(__file__).parents[1] / "fixtures/calibration/legacy_tuning_runs.json").read_text("utf-8"))
    eff = [
        r["duration_minutes"] * 60 / (r["events"] * r["throttle"] / 1000)
        for preset in data.values()
        for r in preset["results"]
    ]
    assert len(eff) >= 50 and abs(statistics.median(eff) - EFFICIENCY) < 0.01


def test_resolve_config_derives_events_for_time_boxed() -> None:
    assert resolve_config("S", "com.a.b", "smoke", None).events == expected_events(6, 250)
    custom_time = resolve_config("S", "com.a.b", "custom", SessionOverrides(target_minutes_per_run=5, throttle_ms=100))
    assert custom_time.events == expected_events(5, 100) and custom_time.target_minutes_per_run == 5
    explicit = resolve_config("S", "com.a.b", "smoke", SessionOverrides(events=500))
    assert explicit.events == 500


def test_suggestions_and_stats() -> None:
    samples = [
        PerfSample(at="2026-11-26T00:00:00Z", run=1, memory_mb=250, cpu_percent=10),
        PerfSample(at="2026-11-26T00:00:02Z", run=1, memory_mb=None, cpu_percent=90),
    ]
    stats = perf_stats(samples)
    assert stats.memory_mb.max == 250 and stats.memory_mb.samples == 1 and stats.cpu_percent.avg == 50
    out = suggestions(IssueCounts(crash=2, anr=1), stats)
    assert any("크래시 2회" in s for s in out) and any("ANR 1회" in s for s in out)
    assert not any("누수" in s or "최적화 필요" in s for s in out)
    assert any("판단할 수 없습니다" in s for s in suggestions(IssueCounts(), perf_stats([])))
