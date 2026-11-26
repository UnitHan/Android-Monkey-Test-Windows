import pytest
from contract import ContractClient
from fakes import PACKAGE, SERIAL, FakeAdb, FakeStream
from pydantic import SecretStr


def test_time_session_extends_and_exposes_auditable_timing(api: ContractClient, adb: FakeAdb):
    streams = [FakeStream(["Events injected: 13"], delay_s=0.04), FakeStream(["// Sending event #5"], hold=True)]
    adb.on_stream("shell", "monkey", factory=lambda: streams.pop(0))
    session = api.post(
        "/sessions",
        json={
            "device_serial": SERIAL,
            "package": PACKAGE,
            "preset_id": "custom",
            "overrides": {"events": 10, "repeats": 1, "seed": 7, "target_minutes_per_run": 0.01},
        },
    ).json()
    sid = session["id"]
    before = api.get(f"/sessions/{sid}/timing").json()
    assert before["completion_policy"] == "extend_until_deadline" and before["target_total_s"] == 0.6
    api.post(f"/sessions/{sid}/start")
    final = api.wait_state(sid, {"completed", "failed"})
    assert final["state"] == "completed", final.get("error")
    timing = api.get(f"/sessions/{sid}/timing").json()
    result = timing["runs"][0]
    assert timing["extension_count"] == 1 and timing["completed_execution_s"] >= 0.59
    assert result["events_sent"] == 18 and result["end_reason"] == "time_limit"
    assert len(result["segments"]) == 2
    assert result["duration_s"] >= result["execution_duration_s"]
    assert result["preparation_duration_s"] >= 0 and result["cleanup_duration_s"] >= 0
    assert adb.called("shell", "am", "force-stop") == 1
    assert adb.called("logcat", "-c") == 1
    events = api.get(f"/sessions/{sid}/events").json()["items"]
    assert sum(e["type"] == "run_extended" for e in events) == 1
    assert sum(e["type"] == "run_started" for e in events) == 1
    assert sum(e["type"] == "run_finished" for e in events) == 1
    replay = api.client.get(f"/api/v1/sessions/{sid}/events/stream").text
    assert "event: run_extended" in replay and "event: segment_finished" in replay


def test_timing_not_found_and_event_policy(api: ContractClient):
    assert api.get("/sessions/s_missing/timing").status_code == 404
    session = api.post(
        "/sessions",
        json={
            "device_serial": SERIAL,
            "package": PACKAGE,
            "preset_id": "custom",
        },
    ).json()
    timing = api.get(f"/sessions/{session['id']}/timing").json()
    assert timing["mode"] == "events" and timing["target_total_s"] is None
    assert timing["completion_policy"] == "event_count"


def test_ai_settings_exposes_status_not_key(api: ContractClient):
    container = api.client.app.state.container
    container.settings.gemini_api_key = SecretStr("do-not-expose-this-key")
    response = api.get("/settings/ai")
    assert response.json()["configured"] is True
    assert response.json()["restart_required"] is False
    assert response.json()["config_file"].endswith("gemini.enc.json")
    assert "do-not-expose-this-key" not in response.text
    assert "do-not-expose-this-key" not in api.get("/logs").text


@pytest.mark.parametrize("lines,code", [([], 1), (["Events injected: 4", "** Monkey aborted"], 0)])
def test_failed_time_run_does_not_become_success(api: ContractClient, adb: FakeAdb, lines, code):
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(lines, exit_code=code))
    session = api.post(
        "/sessions",
        json={
            "device_serial": SERIAL,
            "package": PACKAGE,
            "preset_id": "custom",
            "overrides": {"repeats": 2, "target_minutes_per_run": 0.01},
        },
    ).json()
    api.post(f"/sessions/{session['id']}/start")
    final = api.wait_state(session["id"], {"completed", "failed"})
    assert final["state"] == "failed" and len(final["runs"]) == 1
    assert len(final["runs"][0]["segments"]) == 1
