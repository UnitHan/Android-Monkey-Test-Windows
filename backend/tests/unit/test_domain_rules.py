import pytest

from monkey_api.core.errors import InvalidTransition, ValidationFailed
from monkey_api.domain.adaptive import RunSample, next_run_events, precision_score
from monkey_api.domain.analysis import perf_stats, suggestions
from monkey_api.domain.estimation import estimate_duration, run_time_limit_s
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


def test_estimate_respects_target_cap() -> None:
    uncapped = estimate_duration(12000, 6, 200)
    capped = estimate_duration(12000, 6, 200, target_minutes_per_run=15)
    assert capped.per_run_s == 900 and capped.total_s < uncapped.total_s
    assert run_time_limit_s(1000, 100, 7) == 420


def test_suggestions_and_stats() -> None:
    samples = [
        PerfSample(at="2026-11-26T00:00:00Z", run=1, memory_mb=250, cpu_percent=10),
        PerfSample(at="2026-11-26T00:00:02Z", run=1, memory_mb=None, cpu_percent=90),
    ]
    stats = perf_stats(samples)
    assert stats.memory_mb.max == 250 and stats.memory_mb.samples == 1 and stats.cpu_percent.avg == 50
    out = suggestions(IssueCounts(crash=2, anr=1), stats)
    assert any("크래시 2회" in s for s in out) and any("ANR 1회" in s for s in out)
    assert any("메모리" in s for s in out) and any("CPU" in s for s in out)
    assert suggestions(IssueCounts(), perf_stats([])) == ["특별한 이슈가 발견되지 않았습니다."]
