"""Single writer for session state.

All state changes go through here: snapshot update + event log + live publish + API log.
Commands (SessionService) and execution (SessionRunner) both use it, never the repo directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from monkey_api.adapters.storage.session_repo import SessionRepository
from monkey_api.core.ids import utc_now
from monkey_api.core.logging import LogLevel, log
from monkey_api.domain.models import Issue, PerfSample, Progress, Session, SessionEvent, SessionState
from monkey_api.domain.state_machine import TERMINAL_STATES, ensure_transition
from monkey_api.services.event_bus import EventBus


class SessionLedger:
    def __init__(self, repo: SessionRepository, bus: EventBus) -> None:
        self.repo = repo
        self.bus = bus

    def get(self, session_id: str) -> Session:
        return self.repo.get(session_id)

    def create(self, session: Session) -> Session:
        self.repo.save(session)
        self.emit(session.id, "state_changed", {"from": None, "to": session.state.value})
        return session

    def update(self, session_id: str, mutate: Callable[[Session], Session]) -> Session:
        session = mutate(self.repo.get(session_id))
        self.repo.save(session)
        return session

    def transition(self, session_id: str, target: SessionState, **data: Any) -> Session:
        current = self.repo.get(session_id)
        ensure_transition(current.state, target)
        changes: dict[str, Any] = {"state": target}
        if target == SessionState.PREPARING:
            changes["started_at"] = utc_now()
        if target in TERMINAL_STATES:
            changes["ended_at"] = utc_now()
        if "error" in data:
            changes["error"] = data["error"]
        session = current.model_copy(update=changes)
        self.repo.save(session)
        level: LogLevel = "ERROR" if target == SessionState.FAILED else "INFO"
        log("session", f"state {current.state.value} -> {target.value}", level, **data)
        self.emit(session_id, "state_changed", {"from": current.state.value, "to": target.value, **data})
        if target in TERMINAL_STATES:
            self.bus.close(session_id)
        return session

    def emit(self, session_id: str, type_: str, data: dict[str, Any]) -> SessionEvent:
        """Persistent event: stored in events.jsonl and published live."""
        event = self.repo.append_event(session_id, type_, data)
        self.bus.publish(session_id, event)
        return event

    def live(self, session_id: str, type_: str, data: dict[str, Any]) -> None:
        """Ephemeral event (seq=0): published live only."""
        self.bus.publish(session_id, SessionEvent(seq=0, type=type_, at=utc_now(), data=data))

    def set_progress(self, session_id: str, progress: Progress) -> None:
        self.update(session_id, lambda s: s.model_copy(update={"progress": progress}))
        self.live(session_id, "progress", progress.model_dump())

    def record_issue(self, session_id: str, issue: Issue) -> None:
        self.repo.append_issue(session_id, issue)

        def bump(s: Session) -> Session:
            counts = s.issue_counts.model_copy(update={issue.kind: getattr(s.issue_counts, issue.kind) + 1})
            return s.model_copy(update={"issue_counts": counts})

        self.update(session_id, bump)
        log("session", f"{issue.kind} detected", "WARNING", run=issue.run, summary=issue.summary)
        self.emit(session_id, "issue", issue.model_dump(mode="json", exclude={"lines"}))

    def record_perf(self, session_id: str, sample: PerfSample) -> None:
        self.repo.append_perf(session_id, sample)
        self.live(session_id, "perf", sample.model_dump(mode="json"))
