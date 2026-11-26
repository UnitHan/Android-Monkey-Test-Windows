"""In-process pub/sub for live session events (feeds SSE).

Persistent events (seq > 0) are also in the session's events.jsonl, so clients can resume with
`after_seq`. Ephemeral events (seq == 0: progress, perf) are live-only; current values are always
available from the session snapshot / perf endpoint.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from monkey_api.domain.models import SessionEvent

_QUEUE_SIZE = 1000


class Subscription:
    """Registered on creation, so callers can subscribe *before* replaying history."""

    def __init__(self, bus: EventBus, session_id: str) -> None:
        self._bus = bus
        self.session_id = session_id
        self.queue: asyncio.Queue[SessionEvent | None] = asyncio.Queue(_QUEUE_SIZE)
        bus._subs[session_id].add(self.queue)

    async def next(self) -> SessionEvent | None:
        """Next event, or None when the stream was closed (session reached a terminal state)."""
        return await self.queue.get()

    def close(self) -> None:
        subs = self._bus._subs.get(self.session_id)
        if subs is not None:
            subs.discard(self.queue)
            if not subs:
                self._bus._subs.pop(self.session_id, None)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[SessionEvent | None]]] = defaultdict(set)

    def publish(self, session_id: str, event: SessionEvent) -> None:
        for queue in list(self._subs.get(session_id, ())):
            if queue.full():
                queue.get_nowait()  # drop oldest for slow consumers
            queue.put_nowait(event)

    def close(self, session_id: str) -> None:
        """Signal end-of-stream to all subscribers of a session."""
        for queue in list(self._subs.get(session_id, ())):
            queue.put_nowait(None)

    def subscribe(self, session_id: str) -> Subscription:
        return Subscription(self, session_id)

    def subscriber_count(self, session_id: str) -> int:
        return len(self._subs.get(session_id, ()))
