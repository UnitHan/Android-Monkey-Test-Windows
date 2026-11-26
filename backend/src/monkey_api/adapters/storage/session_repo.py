"""File-backed session store: one directory per session.

<sessions_dir>/<id>/session.json   snapshot (rewritten atomically)
                   events.jsonl    append-only SessionEvent log
                   issues.jsonl    detected crash/ANR blocks
                   perf.jsonl      performance samples
                   logcat_run_N.log, report.html, report.xlsx
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from monkey_api.core.errors import SessionNotFound
from monkey_api.core.ids import utc_now
from monkey_api.domain.models import Issue, PerfSample, Session, SessionEvent


class SessionRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
        self._seq: dict[str, int] = {}
        self._lock = threading.RLock()
        self._load_all()

    # ---- sessions ----

    def dir_for(self, session_id: str) -> Path:
        return self.root / session_id

    def save(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.id] = session
            d = self.dir_for(session.id)
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / "session.json.tmp"
            tmp.write_text(session.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(d / "session.json")

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(f"session '{session_id}' not found", session_id=session_id)
        return session

    def list(self) -> list[Session]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self.get(session_id)
            self._sessions.pop(session_id)
            self._seq.pop(session_id, None)
            d = self.dir_for(session_id)
            for f in d.glob("*"):
                f.unlink()
            d.rmdir()

    # ---- append-only logs ----

    def append_event(self, session_id: str, type_: str, data: dict[str, Any]) -> SessionEvent:
        with self._lock:
            seq = self._seq.get(session_id, 0) + 1
            self._seq[session_id] = seq
            event = SessionEvent(seq=seq, type=type_, at=utc_now(), data=data)
            self._append(session_id, "events.jsonl", event)
            return event

    def events(self, session_id: str, after_seq: int = 0, limit: int = 1000) -> list[SessionEvent]:
        self.get(session_id)
        items = [SessionEvent.model_validate(r) for r in self._read(session_id, "events.jsonl")]
        return [e for e in items if e.seq > after_seq][:limit]

    def append_issue(self, session_id: str, issue: Issue) -> None:
        self._append(session_id, "issues.jsonl", issue)

    def issues(self, session_id: str) -> list[Issue]:
        return [Issue.model_validate(r) for r in self._read(session_id, "issues.jsonl")]

    def append_perf(self, session_id: str, sample: PerfSample) -> None:
        self._append(session_id, "perf.jsonl", sample)

    def perf(self, session_id: str) -> list[PerfSample]:
        return [PerfSample.model_validate(r) for r in self._read(session_id, "perf.jsonl")]

    # ---- internals ----

    def _append(self, session_id: str, name: str, item: BaseModel) -> None:
        with self._lock:
            path = self.dir_for(session_id) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(item.model_dump_json() + "\n")

    def _read(self, session_id: str, name: str) -> list[dict[str, Any]]:
        path = self.dir_for(session_id) / name
        if not path.exists():
            return []
        with self._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def _load_all(self) -> None:
        for snapshot in self.root.glob("*/session.json"):
            session = Session.model_validate_json(snapshot.read_text(encoding="utf-8"))
            self._sessions[session.id] = session
            events = self._read(session.id, "events.jsonl")
            self._seq[session.id] = events[-1]["seq"] if events else 0
