"""Optional AI tuning advisor. The session runner works identically without it.

Legacy put the API key in the URL query (leaks into logs/proxies) and hard-coded a retired model.
Here: key in `x-goog-api-key` header, model from settings, JSON-only response, result is clamped
by the caller to the same bounds as the deterministic algorithm.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

import httpx

from monkey_api.core.logging import log
from monkey_api.domain.adaptive import RunSample

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class TuningAdvisor(Protocol):
    async def suggest_events(
        self, base_events: int, history: Sequence[RunSample], target_s: float, throttle_ms: int
    ) -> int | None: ...


class NoAdvisor:
    async def suggest_events(
        self, base_events: int, history: Sequence[RunSample], target_s: float, throttle_ms: int
    ) -> int | None:
        return None


class GeminiAdvisor:
    def __init__(self, api_key: str, model: str, timeout_s: float = 20.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s

    async def suggest_events(
        self, base_events: int, history: Sequence[RunSample], target_s: float, throttle_ms: int
    ) -> int | None:
        prompt = (
            "You tune Android monkey test runs to hit a wall-clock target per run.\n"
            f"Target seconds per run: {target_s}. Throttle: {throttle_ms} ms. Base events: {base_events}.\n"
            "Previous runs (events_sent, duration_s): "
            + json.dumps([[s.events_sent, round(s.duration_s, 1)] for s in history])
            + '\nReply with JSON only: {"events": <int>, "reason": "<short>"}'
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    _ENDPOINT.format(model=self._model), json=body, headers={"x-goog-api-key": self._api_key}
                )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            payload = json.loads(text)
            events = int(payload["events"])
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            log("app", "gemini advisor unavailable, using algorithm", "WARNING", error=type(exc).__name__)
            return None
        log("app", "gemini advisor suggestion", events=events, reason=str(payload.get("reason", ""))[:200])
        return events
