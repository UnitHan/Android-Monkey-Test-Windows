"""Build monkey invocations as argument lists (never shell strings) and pick seeds."""

from __future__ import annotations

import secrets

from monkey_api.domain.models import EventMix, SessionConfig

_BASE_FLAGS = (
    "--ignore-crashes",
    "--ignore-security-exceptions",
    "--monitor-native-crashes",
    "--kill-process-after-error",
)


def event_mix_args(mix: EventMix) -> list[str]:
    args: list[str] = []
    for name, value in mix.model_dump().items():
        if value is not None:
            args += [f"--pct-{name}", str(value)]
    return args


def build_monkey_args(config: SessionConfig, seed: int, events: int) -> list[str]:
    """adb arguments (after `-s serial`) for one monkey run."""
    args = [
        "shell",
        "monkey",
        "-p",
        config.package,
        "--throttle",
        str(config.throttle_ms),
        "-s",
        str(seed),
        *_BASE_FLAGS,
        *event_mix_args(config.event_mix),
    ]
    if config.bugreport:
        args.append("--bugreport")
    args += ["-v", "-v", str(events)]
    return args


def random_seed() -> int:
    """4-digit seed (1000-9999) like the legacy tool, from a CSPRNG."""
    return 1000 + secrets.randbelow(9000)


def seed_for_run(config: SessionConfig) -> int:
    if config.seed_mode in ("fixed", "manual") and config.seed is not None:
        return config.seed
    return random_seed()
