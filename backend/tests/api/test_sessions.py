import json

from contract import ContractClient
from fakes import PACKAGE, SERIAL, FakeAdb, FakeStream, fail, fixture
from fastapi.testclient import TestClient

from monkey_api.main import create_app

QUICK = {"events": 300, "repeats": 2, "throttle_ms": 0}


def create(api: ContractClient, preset: str = "custom", **overrides: object) -> dict:
    body = {"device_serial": SERIAL, "package": PACKAGE, "preset_id": preset, "overrides": {**QUICK, **overrides}}
    resp = api.post("/sessions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_session_resolves_preset(api: ContractClient) -> None:
    s = create(api, preset="deep", repeats=1)
    assert s["state"] == "created" and s["config"]["seed"] == 4850 and s["config"]["bugreport"] is True
    assert s["config"]["repeats"] == 1 and s["config"]["events"] == 300


def test_create_rejects_bad_package_and_unknown_preset(api: ContractClient) -> None:
    bad = api.post("/sessions", json={"device_serial": SERIAL, "package": "x; rm -rf /"})
    assert bad.status_code == 422
    unknown = api.post("/sessions", json={"device_serial": SERIAL, "package": PACKAGE, "preset_id": "zzz"})
    assert unknown.status_code == 422 and unknown.json()["code"] == "validation_failed"


def test_full_lifecycle_detects_crash_and_builds_report(api: ContractClient, adb: FakeAdb) -> None:
    s = create(api)
    started = api.post(f"/sessions/{s['id']}/start")
    assert started.status_code == 202 and started.json()["state"] == "preparing"
    done = api.wait_state(s["id"], {"completed", "failed"})
    assert done["state"] == "completed", done.get("error")
    assert [r["end_reason"] for r in done["runs"]] == ["completed", "completed"]
    assert all(r["events_sent"] == 300 for r in done["runs"])
    assert done["issue_counts"]["crash"] == 2  # one per run from logcat fixture
    assert done["device"]["model"] == "SM-G991N" and done["app_version"]["version_name"] == "4.2.1"

    events = api.get(f"/sessions/{s['id']}/events").json()["items"]
    types = [e["type"] for e in events]
    assert types[0] == "state_changed" and types.count("run_finished") == 2 and "report_ready" in types
    states = [e["data"]["to"] for e in events if e["type"] == "state_changed"]
    assert states == ["created", "preparing", "running", "completed"]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))

    issues = api.get(f"/sessions/{s['id']}/issues").json()["items"]
    assert issues[0]["kind"] == "crash" and "NullPointerException" in issues[0]["summary"]
    samples = api.get(f"/sessions/{s['id']}/perf").json()["items"]
    assert samples[0]["source"] == "appkium" and samples[0]["memory_mb"] is None
    assert any(p["memory_mb"] is not None and p["memory_mb"] > 0 for p in samples)
    report = api.get(f"/sessions/{s['id']}/report").json()
    assert report["total_events_sent"] == 600 and any("크래시" in x for x in report["suggestions"])
    assert report["perf"]["memory_mb"]["p90"] is not None
    assert all(f["status"] == "insufficient" for f in report["resource_assessment"]["findings"])
    html = api.get(f"/sessions/{s['id']}/report.html")
    assert html.status_code == 200 and "NullPointerException" in html.text
    assert "P90" in html.text and "표준편차" in html.text and "판단 보류" in html.text
    xlsx = api.get(f"/sessions/{s['id']}/report.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    logcat = api.get(f"/sessions/{s['id']}/logcat/1")
    assert "FATAL EXCEPTION" in logcat.text and "\\n" not in logcat.text  # legacy wrote literal \n

    # event-based run: monkey gets exactly the configured events (no time-box headroom)
    assert all(args[-1] == "300" for args, _ in adb.calls if args[:2] == ("shell", "monkey") and "--throttle" in args)
    # monkey was called with argument lists (never shell strings) on the right serial
    monkey_calls = [args for args, serial in adb.calls if args[:2] == ("shell", "monkey") and serial == SERIAL]
    assert any("--throttle" in a for a in monkey_calls)

    # session logs are queryable by session id and carry the session id
    slogs = api.get("/logs", params={"session_id": s["id"], "source": "session"}).json()["items"]
    assert any(r["message"] == "run finished" for r in slogs)


def test_illegal_commands_return_409(api: ContractClient) -> None:
    s = create(api)
    api.post(f"/sessions/{s['id']}/start")
    api.wait_state(s["id"], {"completed"})
    again = api.post(f"/sessions/{s['id']}/start")
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"
    assert again.json()["extra"] == {"current": "completed", "target": "preparing"}


def test_stop_before_start_cancels(api: ContractClient) -> None:
    s = create(api)
    assert api.post(f"/sessions/{s['id']}/stop").json()["state"] == "cancelled"


def test_stop_running_session(api: ContractClient, adb: FakeAdb) -> None:
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(["    // Sending event #100"], hold=True))
    s = create(api, repeats=3)
    api.post(f"/sessions/{s['id']}/start")
    api.wait_state(s["id"], {"running"})
    stopped = api.post(f"/sessions/{s['id']}/stop")
    assert stopped.status_code == 202 and stopped.json()["state"] == "stopping"
    assert api.post(f"/sessions/{s['id']}/stop").json()["state"] in {"stopping", "cancelled"}  # idempotent
    final = api.wait_state(s["id"], {"cancelled"})
    assert len(final["runs"]) == 1 and final["runs"][0]["end_reason"] == "stopped"


def test_time_limit_ends_run(api: ContractClient, adb: FakeAdb) -> None:
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(["    // Sending event #100"], hold=True))
    s = create(api, repeats=1, target_minutes_per_run=0.005)  # 0.3 s
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"completed", "failed"})
    assert final["runs"][0]["end_reason"] == "time_limit" and final["runs"][0]["events_sent"] == 100


def test_device_busy_when_second_session_on_same_device(api: ContractClient, adb: FakeAdb) -> None:
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream([], hold=True))
    first, second = create(api), create(api)
    api.post(f"/sessions/{first['id']}/start")
    resp = api.post(f"/sessions/{second['id']}/start")
    assert resp.status_code == 409 and resp.json()["code"] == "device_busy"
    api.post(f"/sessions/{first['id']}/stop")
    api.wait_state(first["id"], {"cancelled"})


def test_failure_is_recorded_with_reason_in_state_and_logs(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("shell", "dumpsys", "package", reply="Unable to find package: com.example.app\n")
    s = create(api)
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"failed"})
    assert "not installed" in final["error"]
    errors = api.get("/logs", params={"session_id": s["id"], "level": "ERROR"}).json()["items"]
    assert any("not installed" in json.dumps(r["data"]) for r in errors)


def test_monkey_failed_to_start_is_logged_with_stderr(api: ContractClient, adb: FakeAdb) -> None:
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream([], exit_code=1, stderr="Error: Unknown option"))
    s = create(api, repeats=1)
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"completed", "failed"})
    assert final["runs"][0]["end_reason"] == "failed_to_start"
    logs = api.get("/logs", params={"session_id": s["id"], "level": "ERROR"}).json()["items"]
    assert any(r["message"] == "monkey failed_to_start" and "Unknown option" in r["data"]["stderr"] for r in logs)


def test_guard_relaunches_app_when_it_leaves_foreground(api: ContractClient, adb: FakeAdb) -> None:
    other = fixture("activity_activities.txt").replace("com.example.app", "com.android.launcher")
    adb.on("shell", "dumpsys", "activity", "activities", reply=other)
    lines = ["    // Sending event #1"] * 30 + ["Events injected: 300", "// Monkey finished"]
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(lines, delay_s=0.02))
    s = create(api, repeats=1)
    api.post(f"/sessions/{s['id']}/start")
    api.wait_state(s["id"], {"completed"})
    events = api.get(f"/sessions/{s['id']}/events").json()["items"]
    assert any(e["type"] == "guard" and e["data"]["action"] == "relaunch" for e in events)


def test_sse_replays_persisted_events_for_finished_session(api: ContractClient) -> None:
    s = create(api, repeats=1)
    api.post(f"/sessions/{s['id']}/start")
    api.wait_state(s["id"], {"completed"})
    resp = api.client.get(f"/api/v1/sessions/{s['id']}/events/stream")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    frames = [f for f in resp.text.split("\n\n") if f.strip()]
    ids = [int(line[4:]) for f in frames for line in f.splitlines() if line.startswith("id: ")]
    assert ids == sorted(ids) and ids[0] == 1
    resumed = api.client.get(f"/api/v1/sessions/{s['id']}/events/stream", headers={"Last-Event-ID": str(ids[-2])})
    assert resumed.text.count("id: ") == 1


def test_delete_rules(api: ContractClient, adb: FakeAdb) -> None:
    s = create(api)
    assert api.delete(f"/sessions/{s['id']}").status_code == 204
    assert api.get(f"/sessions/{s['id']}").status_code == 404
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream([], hold=True))
    running = create(api)
    api.post(f"/sessions/{running['id']}/start")
    resp = api.delete(f"/sessions/{running['id']}")
    assert resp.status_code == 409 and resp.json()["code"] == "session_active"
    api.post(f"/sessions/{running['id']}/stop")
    api.wait_state(running["id"], {"cancelled"})


def test_adaptive_events_grow_toward_target(api: ContractClient, adb: FakeAdb) -> None:
    lines = [f"    // Sending event #{n}" for n in range(100, 301, 100)] + ["Events injected: 300"]
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(lines, delay_s=0.01))
    s = create(api, preset="smoke", repeats=2, target_minutes_per_run=0.005)
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"completed"})
    first, second = final["runs"]
    assert first["events_target"] == 300
    assert second["events_target"] == int(300 * 1.2)  # fast device: capped at +20% smoke margin


def test_orphaned_active_sessions_fail_on_restart(settings, adb, log_store) -> None:  # type: ignore[no-untyped-def]
    with TestClient(create_app(settings, adb=adb, log_store=log_store)) as c1:
        adb.on_stream("shell", "monkey", factory=lambda: FakeStream([], hold=True))
        body = {"device_serial": SERIAL, "package": PACKAGE, "preset_id": "custom", "overrides": QUICK}
        sid = c1.post("/api/v1/sessions", json=body).json()["id"]
        c1.post(f"/api/v1/sessions/{sid}/start")
        c1.app.state.container.sessions._stops.clear()  # simulate crash: runner never told to stop
        c1.app.state.container.sessions._tasks.clear()
    with TestClient(create_app(settings, adb=adb, log_store=log_store)) as c2:
        state = c2.get(f"/api/v1/sessions/{sid}").json()
        assert state["state"] in {"failed", "cancelled", "completed"}


def test_unhandled_error_keeps_request_id(api: ContractClient, adb: FakeAdb) -> None:
    def boom(args, serial):  # type: ignore[no-untyped-def]
        raise RuntimeError("fake adb exploded")

    adb.on("devices", "-l", reply=boom)
    resp = api.get("/devices")
    assert resp.status_code == 500 and resp.json()["code"] == "internal_error"
    logs = api.get("/logs", params={"request_id": resp.headers["x-request-id"], "level": "ERROR"}).json()["items"]
    assert any("fake adb exploded" in r["message"] and "fake adb exploded" in r["data"]["trace"] for r in logs)


def test_package_not_installed_adb_failure_on_start(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("shell", "getprop", reply=fail("error: device offline"))
    s = create(api)
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"failed"})
    assert final["error"] == "error: device offline"


def test_time_boxed_run_launches_monkey_with_headroom(api: ContractClient, adb: FakeAdb) -> None:
    adb.on_stream("shell", "monkey", factory=lambda: FakeStream(["    // Sending event #100"], hold=True))
    s = create(api, repeats=1, target_minutes_per_run=0.005)
    api.post(f"/sessions/{s['id']}/start")
    final = api.wait_state(s["id"], {"completed", "failed"})
    assert final["runs"][0]["end_reason"] == "time_limit" and final["runs"][0]["events_target"] == 300
    budgets = [args[-1] for args, _ in adb.calls if args[:2] == ("shell", "monkey") and "--throttle" in args]
    assert budgets == ["390"]  # ceil(300 * 1.3)


def test_estimate_accepts_time_only_and_rejects_empty(api: ContractClient) -> None:
    est = api.post("/estimates", json={"repeats": 5, "throttle_ms": 250, "target_minutes_per_run": 7}).json()
    assert est["mode"] == "time" and est["per_run_events"] == 4667 and est["total_s"] == 420 * 5 + 12 * 5 + 5
    bad = api.post("/estimates", json={"repeats": 5, "throttle_ms": 250})
    assert bad.status_code == 422 and bad.json()["code"] == "validation_failed"
