import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fakes import SERIAL

from monkey_api.adapters.adb.app_labels import parse_labels


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("블라인드", "com.teamblind.blind"),
        ("유튜브", "com.google.android.youtube"),
        ("ㅇㅅㅇ", "com.lguplus.aicallagent"),
    ],
)
def test_launcher_search_includes_google_apps(api, monkeypatch, query, expected):
    fixture = (Path(__file__).parents[1] / "fixtures/adb/search_launcher_labels.json").read_text("utf-8")
    labels = parse_labels(json.dumps(json.loads(fixture)))
    service = api.client.app.state.container.packages
    monkeypatch.setattr(service.ops, "list_packages", AsyncMock(return_value=list(labels)))
    monkeypatch.setattr("monkey_api.services.package_service.read_labels", AsyncMock(return_value=labels))
    response = api.get(f"/devices/{SERIAL}/packages", params={"query": query}).json()
    assert expected in [item["name"] for item in response["items"]]
    installed = api.get(f"/devices/{SERIAL}/packages").json()["items"]
    assert "com.sec.imslogger" not in [item["name"] for item in installed]
    all_packages = api.get(f"/devices/{SERIAL}/packages", params={"include_system": True}).json()["items"]
    assert "com.sec.imslogger" in [item["name"] for item in all_packages]


def test_search_uses_device_labels_ranking_and_cached_inventory(api, monkeypatch):
    service = api.client.app.state.container.packages
    labels = {
        "com.first": "모바일매니저",
        "com.second": "U+모바일매니저",
        "com.blind": "blind",
        "com.kakao.talk": "카카오톡",
    }
    names = AsyncMock(return_value=list(labels))
    monkeypatch.setattr(service.ops, "list_packages", names)
    monkeypatch.setattr("monkey_api.services.package_service.read_labels", AsyncMock(return_value=labels))
    path = f"/devices/{SERIAL}/packages"
    assert [item["name"] for item in api.get(path, params={"query": "모"}).json()["items"]] == [
        "com.first",
        "com.second",
    ]
    assert api.get(path, params={"query": "블"}).json()["items"][0]["name"] == "com.blind"
    assert api.get(path, params={"query": "ㅋㅋ"}).json()["items"][0]["display_name"] == "카카오톡"
    assert names.await_count == 1  # Typing must not fetch the full device inventory for every query.
    api.get(path, params={"query": "ㅋㅋ", "refresh": True})
    assert names.await_count == 2
