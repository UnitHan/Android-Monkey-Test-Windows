import asyncio
from types import SimpleNamespace

import httpx

from monkey_api.adapters.ai.advisor import GeminiAdvisor
from monkey_api.services.session_runner import SessionRunner


async def test_advisor_reuses_configured_key_and_model(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"events": 123, "reason": "test"}'}],
                        }
                    }
                ]
            },
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle),
            **kwargs,
        ),
    )
    advisor = GeminiAdvisor("local-test-key", "test-model")
    for _ in range(2):
        assert await advisor.suggest_events(100, [], 60, 200) == 123
    assert all(r.headers["x-goog-api-key"] == "local-test-key" for r in requests)
    assert all("test-model:generateContent" in str(r.url) for r in requests)
    assert all("local-test-key" not in str(r.url) for r in requests)


async def test_stop_cancels_pending_advisor():
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def pending(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    runner = SessionRunner(SimpleNamespace(advisor=SimpleNamespace(suggest_events=pending)))
    stop = asyncio.Event()
    task = asyncio.create_task(runner._suggest_until_stopped(100, [], 60, 200, stop))
    await asyncio.wait_for(started.wait(), 1)
    stop.set()
    assert await asyncio.wait_for(task, 1) is None
    assert cleaned.is_set()
