import json

import pytest
from contract import ContractClient
from fakes import SERIAL, FakeAdb, fail, fixture

from monkey_api.adapters.adb.app_labels import parse_labels

PACKAGE = "com.lguplus.remocon"


def setup_labels(adb: FakeAdb, raw: str):
    adb.on("shell", "pm", "list", "packages", reply=f"package:{PACKAGE}\n")
    adb.default = lambda args, serial: raw if len(args) > 1 and args[1].startswith("CLASSPATH=") else ""


def test_device_label_replaces_catalog_and_is_searchable(api: ContractClient, adb: FakeAdb):
    setup_labels(adb, fixture("device_app_labels.json"))
    path = f"/devices/{SERIAL}/packages"
    items = api.get(path).json()["items"]
    assert items == [{"name": PACKAGE, "display_name": "U+tv모바일"}]
    assert api.get(path, params={"query": "U+tv모바일"}).json()["total"] == 1
    assert api.get(path, params={"query": "리모컨"}).json()["total"] == 1  # old names remain search aliases
    assert adb.called("push") == 1
    assert adb.called("shell", "rm", "-f") == 1
    assert adb.called("shell", "chmod", "444") == 1
    assert not adb.called("install") and not adb.called("pull")


def test_refresh_reads_changed_device_name(api: ContractClient, adb: FakeAdb):
    raw = fixture("device_app_labels.json")
    setup_labels(adb, raw)
    path = f"/devices/{SERIAL}/packages"
    api.get(path)
    setup_labels(adb, raw.replace("U+tv모바일", "새 단말 이름"))
    assert api.get(path).json()["items"][0]["display_name"] == "U+tv모바일"
    assert api.get(path, params={"refresh": True}).json()["items"][0]["display_name"] == "새 단말 이름"
    assert adb.called("push") == 2


def test_helper_failure_falls_back_to_package_and_cleans_up(api: ContractClient, adb: FakeAdb):
    setup_labels(adb, "not valid JSON")
    adb.on("push", reply=fail("device denied file transfer"))
    items = api.get(f"/devices/{SERIAL}/packages").json()["items"]
    assert items == [{"name": PACKAGE, "display_name": PACKAGE}]
    assert adb.called("shell", "rm", "-f") == 1


def test_real_device_label_fixture_and_validation():
    assert parse_labels(fixture("device_app_labels.json"))[PACKAGE] == "U+tv모바일"
    for raw in ("bad data", '{"version":2,"labels":{}}', '{"version":1,"labels":[]}'):
        with pytest.raises(ValueError):
            parse_labels(raw)
    raw = json.dumps({"version": 1, "labels": {"bad;name": "injected", PACKAGE: None, "com.test.ok": "Good"}})
    assert parse_labels(raw) == {"com.test.ok": "Good"}
