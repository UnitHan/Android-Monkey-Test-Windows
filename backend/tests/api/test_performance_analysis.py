import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import httpx
import pytest
from contract import ContractClient
from openpyxl import load_workbook

from monkey_api.adapters.ai.performance import GeminiPerformance
from monkey_api.domain.models import Issue, PerfSample, RunResult, Session
from monkey_api.services.session_service import resolve_config

START = datetime(2026, 11, 26, tzinfo=UTC)
SID = "s_ai_performance"
PATH = f"/sessions/{SID}/performance-analysis"


def conclusion():
    finding = {"verdict": "normal", "reason": "관측 통계에서 지속 부하가 없습니다."}
    return {
        "verdict": "normal",
        "summary": "관측 범위에서 이상 징후가 없습니다.",
        "memory": finding,
        "cpu": finding,
        "stability": finding,
        "recommendations": ["동일 조건의 기준 버전과 비교하세요."],
        "limitations": ["앱별 예산은 없습니다."],
    }


def seed(api: ContractClient, state="completed", samples=41):
    repo = api.client.app.state.container.ledger.repo
    cfg = resolve_config("private-device-serial", "com.private.app", "smoke", None)
    cfg = cfg.model_copy(update={"repeats": 1, "target_minutes_per_run": 80 / 60})
    run = RunResult(
        run=1,
        seed=123,
        events_target=100,
        events_sent=100,
        throttle_ms=250,
        started_at=START,
        ended_at=START + timedelta(seconds=80),
        duration_s=80,
        execution_duration_s=80,
        exit_code=0,
        end_reason="time_limit",
        target_duration_s=80,
    )
    session = Session(
        id=SID, state=state, config=cfg, created_at=START, runs=[run], error="private-error-email@example.com"
    )
    repo.save(session)
    for i in range(samples):
        repo.append_perf(
            SID,
            PerfSample(
                at=START + timedelta(seconds=i * 2),
                run=1,
                memory_mb=200,
                cpu_percent=80,
                cpu_total_percent=10,
                source="appkium",
            ),
        )
    repo.append_issue(
        SID,
        Issue(
            id="i_private",
            kind="crash",
            run=1,
            at=START,
            summary="private-stack",
            lines=["010-1234-5678 token=private-token"],
        ),
    )
    return repo


def use_gemini(api, handler):
    service = api.client.app.state.container.performance_analysis
    service.analyzer = GeminiPerformance("private-api-key", "fake-model", httpx.MockTransport(handler))


def reply(result=None, **kwargs):
    return httpx.Response(
        200,
        json={
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(result or conclusion())}]}}
            ],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 80},
            **kwargs,
        },
    )


def request_body(api):
    preview = api.get(PATH + "/preview")
    assert preview.status_code == 200
    return {"input_hash": preview.json()["input_hash"], "consent": True}


def test_preview_excludes_secrets_and_only_post_calls_gemini(api):
    seed(api)
    sent = []
    use_gemini(api, lambda r: (sent.append(r), reply())[1])
    preview = api.get(PATH + "/preview")
    assert sent == [] and preview.json()["configured"] is True
    body = request_body(api)
    result = api.post(PATH, json=body)
    assert result.status_code == 200 and result.json()["conclusion"]["verdict"] == "normal"
    assert len(sent) == 1 and sent[0].headers["x-goog-api-key"] == "private-api-key"
    wire = sent[0].content.decode()
    for forbidden in (
        "private-device",
        "com.private",
        "private-error",
        "private-stack",
        "010-1234",
        "private-token",
        "private-api-key",
    ):
        assert forbidden not in wire + preview.text
    payload = json.loads(wire)
    assert payload["generationConfig"]["responseJsonSchema"]["properties"]["verdict"]["enum"]
    assert api.post(PATH, json=body).json() == result.json() and len(sent) == 1
    assert api.get(f"/sessions/{SID}/report").json()["ai_performance"] == result.json()
    logs = api.get("/logs").text
    assert "private-api-key" not in logs and "관측 범위에서 이상 징후" not in logs
    assert "input_tokens" in logs and "output_tokens" in logs


def test_consent_and_stale_preview_rejected_without_network(api):
    repo = seed(api)
    use_gemini(api, lambda _: pytest.fail("must not call Gemini"))
    body = request_body(api)
    assert api.post(PATH, json={**body, "consent": False}).status_code == 422
    assert api.post(PATH, json={"input_hash": body["input_hash"]}).status_code == 422
    repo.append_perf(SID, PerfSample(at=START + timedelta(seconds=82), run=1, memory_mb=210, cpu_percent=20))
    assert api.post(PATH, json=body).status_code == 409


@pytest.mark.parametrize("state,samples", [("cancelled", 41), ("completed", 3)])
def test_overconfident_model_is_held_when_evidence_is_insufficient(api, state, samples):
    seed(api, state, samples)
    use_gemini(api, lambda _: reply())
    result = api.post(PATH, json=request_body(api)).json()
    assert result["conclusion"]["verdict"] == "inconclusive" and result["guardrails"]


def test_invalid_response_does_not_replace_report_or_leak_text(api):
    seed(api)
    use_gemini(api, lambda _: reply({"summary": "private-api-key"}))
    response = api.post(PATH, json=request_body(api))
    assert response.status_code == 502 and response.json()["code"] == "ai_response_error"
    assert "private-api-key" not in response.text + api.get("/logs").text
    assert api.get(f"/sessions/{SID}/report").json()["ai_performance"] is None


def test_unconfigured_and_timeout_fail_cleanly(api):
    seed(api)
    assert api.post(PATH, json=request_body(api)).status_code == 503

    def timeout(_):
        raise httpx.ReadTimeout("private-api-key")

    use_gemini(api, timeout)
    response = api.post(PATH, json=request_body(api))
    assert response.status_code == 504 and "private-api-key" not in response.text


def test_running_session_cannot_be_sent(api):
    seed(api, "running")
    assert api.get(PATH + "/preview").status_code == 409


def test_crash_count_overrides_model_normal_and_keeps_summary_consistent(api):
    repo = seed(api)
    s = repo.get(SID)
    repo.save(s.model_copy(update={"issue_counts": s.issue_counts.model_copy(update={"crash": 1})}))
    use_gemini(api, lambda _: reply())
    result = api.post(PATH, json=request_body(api)).json()["conclusion"]
    assert result["stability"]["verdict"] == result["verdict"] == "abnormal"
    assert "이상 징후가 없습니다" not in result["summary"]


def test_completed_but_short_execution_is_not_a_pass(api):
    repo = seed(api)
    s = repo.get(SID)
    repo.save(s.model_copy(update={"config": s.config.model_copy(update={"target_minutes_per_run": 30})}))
    use_gemini(api, lambda _: reply())
    result = api.post(PATH, json=request_body(api)).json()
    assert result["conclusion"]["verdict"] == "inconclusive"
    assert any("실행 시간" in g for g in result["guardrails"])


def test_analysis_is_escaped_in_html_and_not_an_excel_formula(api):
    repo = seed(api)
    c = conclusion()
    c["summary"] = '=HYPERLINK("https://example.com")'
    c["recommendations"] = ["<script>alert(1)</script>"]
    use_gemini(api, lambda _: reply(c))
    assert api.post(PATH, json=request_body(api)).status_code == 200
    html = api.get(f"/sessions/{SID}/report.html").text
    assert "Gemini 성능 판정" in html and "&lt;script&gt;" in html and "<script>" not in html
    workbook = load_workbook(BytesIO(api.get(f"/sessions/{SID}/report.xlsx").content))
    assert workbook["AI Performance"]["B5"].data_type == "s"
    assert workbook["AI Performance"]["B5"].value == c["summary"]
    # A new observation invalidates the saved analysis, including exported reports.
    repo.append_perf(SID, PerfSample(at=START + timedelta(seconds=82), run=1, memory_mb=999, cpu_percent=1))
    assert api.get(f"/sessions/{SID}/report").json()["ai_performance"] is None
