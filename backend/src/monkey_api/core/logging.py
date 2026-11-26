"""Structured logging with request/session context and a queryable in-memory store.

Every record lands in LogStore (served by GET /api/v1/logs) and optionally a JSONL file.
Use `log(source, message, level=..., **data)` everywhere instead of ad-hoc f-string logs.
"""

from __future__ import annotations

import itertools
import json
import logging
import threading
from collections import deque
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

LogSource = Literal["http", "adb", "session", "app"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)

_LEVELS: dict[str, int] = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


@dataclass(frozen=True, slots=True)
class LogRecord:
    seq: int
    at: str
    level: LogLevel
    source: LogSource
    message: str
    request_id: str | None = None
    session_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LogQuery:
    level: LogLevel | None = None
    source: LogSource | None = None
    session_id: str | None = None
    request_id: str | None = None
    since_seq: int = 0
    limit: int = 200


class LogStore:
    """Thread-safe ring buffer of structured log records with optional JSONL persistence."""

    def __init__(self, capacity: int = 20_000, file_path: Path | None = None) -> None:
        self._records: deque[LogRecord] = deque(maxlen=capacity)
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self._file_path = file_path
        if file_path is not None:
            file_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        source: LogSource,
        message: str,
        level: LogLevel = "INFO",
        data: dict[str, Any] | None = None,
    ) -> LogRecord:
        with self._lock:
            record = LogRecord(
                seq=next(self._seq),
                at=datetime.now(UTC).isoformat(timespec="milliseconds"),
                level=level,
                source=source,
                message=message,
                request_id=request_id_var.get(),
                session_id=session_id_var.get(),
                data=data or {},
            )
            self._records.append(record)
            if self._file_path is not None:
                with self._file_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")
        return record

    def query(self, q: LogQuery) -> list[LogRecord]:
        min_level = _LEVELS[q.level] if q.level else 0
        with self._lock:
            snapshot = list(self._records)
        result = [
            r
            for r in snapshot
            if r.seq > q.since_seq
            and _LEVELS[r.level] >= min_level
            and (q.source is None or r.source == q.source)
            and (q.session_id is None or r.session_id == q.session_id)
            and (q.request_id is None or r.request_id == q.request_id)
        ]
        return result[-q.limit :] if q.limit else result

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


_store = LogStore()
_py_logger = logging.getLogger("monkey_api")


def configure_logging(store: LogStore, level: str = "INFO") -> None:
    global _store
    _store = store
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def get_log_store() -> LogStore:
    return _store


def log(source: LogSource, message: str, level: LogLevel = "INFO", **data: Any) -> LogRecord:
    """Write one structured record to the API log store and the console logger."""
    record = _store.append(source, message, level, data)
    _py_logger.log(
        _LEVELS[level],
        "[%s] %s rid=%s sid=%s %s",
        source,
        message,
        record.request_id,
        record.session_id,
        json.dumps(data, ensure_ascii=False, default=str) if data else "",
    )
    return record
