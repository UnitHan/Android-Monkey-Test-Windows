"""Built-in test presets as data.

Time-boxed presets (target_minutes_per_run set) follow the time rule in domain/estimation.py:
normal event completion extends until the deadline; errors/stop are recorded separately.
`events` is derived from target and throttle, never hand-typed.

Total execution targets: Smoke 30 minutes, Standard 60, Deep 180, Extreme 480.
Preparation and cleanup are outside these targets. Quick is no longer offered.
"""

from __future__ import annotations

from monkey_api.domain.estimation import expected_events
from monkey_api.domain.models import EventMix, Preset

_LIGHT_MIX = EventMix(
    touch=25,
    motion=20,
    trackball=0,
    nav=15,
    majornav=10,
    syskeys=5,
    appswitch=3,
    anyevent=22,
    pinchzoom=0,
    rotation=0,
)

PRESETS: tuple[Preset, ...] = (
    Preset(
        id="smoke",
        name="Smoke Test",
        description="빠른 안정성 확인",
        events=expected_events(6, 250),
        repeats=5,
        throttle_ms=250,
        target_minutes_per_run=6,
        seed_mode="random",
        event_mix=_LIGHT_MIX,
        adaptive_margin=0.20,
    ),
    Preset(
        id="standard",
        name="Standard Test",
        description="표준 품질 보증 테스트",
        events=expected_events(10, 200),
        repeats=6,
        throttle_ms=200,
        target_minutes_per_run=10,
        seed_mode="random",
        event_mix=EventMix(
            touch=28,
            motion=23,
            trackball=0,
            nav=14,
            majornav=12,
            syskeys=6,
            appswitch=5,
            anyevent=12,
            pinchzoom=0,
            rotation=0,
        ),
        adaptive_margin=0.12,
    ),
    Preset(
        id="deep",
        name="Deep Test",
        description="고강도 장시간 테스트 (고정 시드)",
        events=expected_events(18, 150),
        repeats=10,
        throttle_ms=150,
        target_minutes_per_run=18,
        seed_mode="fixed",
        fixed_seed=4850,
        event_mix=EventMix(
            touch=30,
            motion=30,
            nav=10,
            majornav=10,
            syskeys=5,
            appswitch=3,
            anyevent=10,
            pinchzoom=2,
        ),
        bugreport=True,
        adaptive_margin=0.10,
    ),
    Preset(
        id="extreme",
        name="Extreme Test",
        description="최대 강도 내구성 테스트 (고정 시드)",
        events=expected_events(32, 180),
        repeats=15,
        throttle_ms=180,
        target_minutes_per_run=32,
        seed_mode="fixed",
        fixed_seed=4850,
        event_mix=EventMix(
            touch=30,
            motion=30,
            nav=10,
            majornav=10,
            syskeys=5,
            appswitch=3,
            anyevent=10,
            pinchzoom=2,
        ),
        bugreport=True,
        adaptive_margin=0.15,
    ),
    Preset(
        id="reproduce",
        name="재현테스트",
        description="지정 시드로 이슈 재현",
        events=3000,
        repeats=5,
        throttle_ms=300,
        target_minutes_per_run=None,
        seed_mode="manual",
        event_mix=_LIGHT_MIX,
    ),
    Preset(
        id="custom",
        name="Custom",
        description="사용자 지정 (overrides 사용)",
        events=3000,
        repeats=5,
        throttle_ms=200,
        target_minutes_per_run=None,
        seed_mode="random",
        event_mix=_LIGHT_MIX,
    ),
)

_BY_ID = {p.id: p for p in PRESETS}


def get_preset(preset_id: str) -> Preset | None:
    return _BY_ID.get(preset_id)
