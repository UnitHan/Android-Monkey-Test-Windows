"""Adaptive event count: fit next run's events to the per-run time target (pure)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunSample:
    events_sent: int
    duration_s: float


def next_run_events(
    base_events: int,
    history: Sequence[RunSample],
    target_s: float | None,
    margin: float,
    window: int = 3,
) -> int:
    """Return events for the next run.

    Legacy rule (monkey_runner._calculate_adaptive_events), simplified: measure event rate over the
    last `window` runs, aim for `target_s * rate`, clamp to [base, base * (1 + margin)].
    The legacy minimum always equalled the preset base, so events never drop below base.
    """
    usable = [s for s in history[-window:] if s.duration_s > 0 and s.events_sent > 0]
    if target_s is None or margin <= 0 or not usable:
        return base_events
    rate = sum(s.events_sent / s.duration_s for s in usable) / len(usable)
    optimal = int(target_s * rate)
    upper = int(base_events * (1 + margin))
    return max(base_events, min(upper, optimal))


def precision_score(actual_s: float, target_s: float) -> float:
    """0-100 score for how close a run ended to its target duration (legacy scale)."""
    deviation = abs(actual_s - target_s)
    if deviation <= 30:
        score = 100 - deviation / 30 * 5
    elif deviation <= 60:
        score = 95 - (deviation - 30) / 30 * 10
    elif deviation <= 120:
        score = 85 - (deviation - 60) / 60 * 15
    else:
        score = 70 - (deviation - 120) / 60 * 10
    return round(max(0.0, score), 1)
