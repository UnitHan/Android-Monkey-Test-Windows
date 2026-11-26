"""Session state machine: the only place that defines legal transitions."""

from __future__ import annotations

from monkey_api.core.errors import InvalidTransition
from monkey_api.domain.models import SessionState as S

TRANSITIONS: dict[S, frozenset[S]] = {
    S.CREATED: frozenset({S.PREPARING, S.CANCELLED}),
    S.PREPARING: frozenset({S.RUNNING, S.STOPPING, S.FAILED}),
    S.RUNNING: frozenset({S.STOPPING, S.COMPLETED, S.FAILED}),
    S.STOPPING: frozenset({S.CANCELLED, S.FAILED, S.COMPLETED}),
    S.COMPLETED: frozenset(),
    S.FAILED: frozenset(),
    S.CANCELLED: frozenset(),
}

ACTIVE_STATES = frozenset({S.PREPARING, S.RUNNING, S.STOPPING})
TERMINAL_STATES = frozenset({S.COMPLETED, S.FAILED, S.CANCELLED})


def can_transition(current: S, target: S) -> bool:
    return target in TRANSITIONS[current]


def ensure_transition(current: S, target: S) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(
            f"cannot move session from '{current.value}' to '{target.value}'",
            current=current.value,
            target=target.value,
        )
