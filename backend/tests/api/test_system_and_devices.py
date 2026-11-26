from contract import ContractClient
from fakes import PACKAGE, SERIAL, FakeAdb, fail


def test_health_reports_adb(api: ContractClient) -> None:
    body = api.get("/health").json()
    assert body["status"] == "ok" and body["adb"]["available"] is True


def test_health_degraded_when_adb_missing(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("version", reply=fail("adb: not runnable"))
    body = api.get("/health").json()
    assert body["status"] == "degraded" and body["adb"]["version"] is None


def test_request_id_is_echoed_and_logged(api: ContractClient) -> None:
    resp = api.get("/presets", headers={"X-Request-ID": "test-rid-1"})
    assert resp.headers["x-request-id"] == "test-rid-1"
    logs = api.get("/logs", params={"request_id": "test-rid-1", "source": "http"}).json()["items"]
    assert logs and logs[0]["data"]["path"].endswith("/presets") and logs[0]["data"]["status"] == 200


def test_presets_and_estimate(api: ContractClient) -> None:
    presets = api.get("/presets").json()["items"]
    assert {p["id"] for p in presets} == {"smoke", "standard", "deep", "extreme", "reproduce", "custom"}
    est = api.post("/estimates", json={"events": 12000, "repeats": 6, "throttle_ms": 200,
                                       "target_minutes_per_run": 15}).json()  # fmt: skip
    assert est["per_run_s"] == 900 and est["total_s"] > 900 * 6


def test_estimate_validation_is_problem_json(api: ContractClient) -> None:
    resp = api.post("/estimates", json={"events": 0, "repeats": 1, "throttle_ms": 1})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "validation_failed" and body["request_id"] == resp.headers["x-request-id"]
    assert body["errors"][0]["loc"][-1] == "events"


def test_list_devices(api: ContractClient) -> None:
    items = api.get("/devices").json()["items"]
    assert [d["serial"] for d in items][:2] == [SERIAL, "192.168.0.23:5555"]


def test_device_info(api: ContractClient) -> None:
    body = api.get(f"/devices/{SERIAL}").json()
    assert body == {"serial": SERIAL, "connection": "usb", "model": "SM-G991N", "android_version": "14",
                    "api_level": "34"}  # fmt: skip


def test_unknown_device_is_404_with_logged_reason(api: ContractClient) -> None:
    resp = api.get("/devices/NOPE123")
    assert resp.status_code == 404 and resp.json()["code"] == "device_not_found"
    rid = resp.headers["x-request-id"]
    logs = api.get("/logs", params={"request_id": rid, "level": "WARNING"}).json()["items"]
    assert any(r["data"].get("code") == "device_not_found" for r in logs)


def test_adb_failure_maps_to_502_and_adb_log_has_exit_code(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("devices", "-l", reply=fail("error: protocol fault (couldn't read status)", code=1))
    resp = api.get("/devices")
    assert resp.status_code == 502 and resp.json()["code"] == "adb_error"
    adb_logs = api.get("/logs", params={"request_id": resp.headers["x-request-id"], "source": "adb"}).json()
    failed = [r for r in adb_logs["items"] if r["message"] == "adb command failed"]
    assert failed and failed[0]["data"]["exit_code"] == 1 and "protocol fault" in failed[0]["data"]["stderr"]


def test_offline_device_maps_to_device_offline(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("shell", "getprop", reply=fail("error: device offline"))
    resp = api.get(f"/devices/{SERIAL}")
    assert resp.status_code == 502 and resp.json()["code"] == "device_offline"


def test_packages_filtered_named_and_searchable(api: ContractClient) -> None:
    body = api.get(f"/devices/{SERIAL}/packages").json()
    names = [p["name"] for p in body["items"]]
    assert "com.android.settings" not in names and PACKAGE in names  # system packages filtered
    all_pkgs = api.get(f"/devices/{SERIAL}/packages", params={"include_system": True}).json()
    named = {p["name"]: p["display_name"] for p in all_pkgs["items"]}
    assert named["com.sec.imslogger"] == "com.sec.imslogger"  # no device label: no stale catalog name
    found = api.get(f"/devices/{SERIAL}/packages", params={"query": "ims", "include_system": True}).json()
    assert [p["name"] for p in found["items"]] == ["com.sec.imslogger"]


def test_package_list_falls_back_for_hardened_devices(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("shell", "pm", "list", "packages", reply=fail("SecurityException: Shell does not have permission"))
    adb.on("shell", "pm", "list", "packages", "--user", "0", reply="package:com.example.app\n")
    assert api.get(f"/devices/{SERIAL}/packages").json()["total"] == 1
    warn = api.get("/logs", params={"source": "adb", "level": "WARNING"}).json()["items"]
    assert any(r["message"] == "package list variant failed, trying next" for r in warn)


def test_package_version(api: ContractClient) -> None:
    body = api.get(f"/devices/{SERIAL}/packages/{PACKAGE}").json()
    assert body == {"package": PACKAGE, "version_name": "4.2.1", "version_code": "4021"}


def test_wireless_connect_and_validation(api: ContractClient, adb: FakeAdb) -> None:
    adb.on("connect", reply="connected to 192.168.0.50:5555\n")
    assert api.post("/devices/connect", json={"host": "192.168.0.50"}).json() == {"serial": "192.168.0.50:5555"}
    adb.on("connect", reply="failed to connect to '192.168.0.51:5555': Connection refused\n")
    resp = api.post("/devices/connect", json={"host": "192.168.0.51"})
    assert resp.status_code == 502 and "Connection refused" in resp.json()["detail"]
    assert api.post("/devices/connect", json={"host": "bad host;rm"}).status_code == 422
    assert api.post("/devices/pair", json={"host": "10.0.0.1", "port": 37000, "code": "12"}).status_code == 422


def test_unknown_route_is_problem_json(api: ContractClient) -> None:
    resp = api.client.get("/api/v1/nope")
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"
    assert resp.headers["x-request-id"]


def test_reboot_and_launch(api: ContractClient, adb: FakeAdb) -> None:
    assert api.post(f"/devices/{SERIAL}/reboot").json() == {"message": "reboot requested"}
    assert adb.called("reboot") == 1
    assert api.post(f"/devices/{SERIAL}/packages/{PACKAGE}/launch").status_code == 204
    assert any(args[:3] == ("shell", "am", "start") and args[-1] == f"{PACKAGE}/.MainActivity" for args, _ in adb.calls)
    assert adb.called("shell", "monkey") == 0
    assert api.post("/devices/NOPE1/reboot").status_code == 404
    assert api.post(f"/devices/{SERIAL}/packages/bad%20pkg/launch").status_code == 422


def test_enable_tcpip(api: ContractClient, adb: FakeAdb) -> None:
    assert api.post(f"/devices/{SERIAL}/tcpip", json={"port": 5555}).status_code == 202
    assert (("tcpip", "5555"), SERIAL) in adb.calls
    assert api.post(f"/devices/{SERIAL}/tcpip", json={"port": 0}).status_code == 422
