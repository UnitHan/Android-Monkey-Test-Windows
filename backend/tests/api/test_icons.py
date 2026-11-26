import base64
from pathlib import Path
from unittest.mock import AsyncMock

from contract import ContractClient
from fakes import SERIAL, FakeAdb, fixture

from monkey_api.core.icon_errors import IconUnavailable

PACKAGE = "com.lguplus.aicallagent"
PATH = f"/devices/{SERIAL}/packages/{PACKAGE}/icon"
PNG = b"\x89PNG\r\n\x1a\nfixture-png"  # Renderer boundary is tested separately with actual PNG decoding.


def setup_icon(api: ContractClient, adb: FakeAdb, monkeypatch) -> None:
    monkeypatch.setattr("monkey_api.services.icon_service.read_icon", AsyncMock(side_effect=ValueError("old device")))
    adb.on("shell", "pm", "path", reply=fixture("ixio_pm_path.txt"))
    adb.on("shell", "dumpsys", "package", reply=fixture("ixio_version.txt"))

    def pull(args, serial):
        Path(args[-1]).write_bytes(b"apk fixture")
        return "1 file pulled"

    adb.on("pull", reply=pull)
    monkeypatch.setattr(api.client.app.state.container.icons.renderer, "render", lambda apks: PNG)


def test_selected_icon_is_cached_and_invalidated_by_install_change(
    api: ContractClient, adb: FakeAdb, monkeypatch
) -> None:
    setup_icon(api, adb, monkeypatch)
    first = api.get(PATH).json()
    assert first["cached"] is False and base64.b64decode(first["data_base64"]) == PNG
    assert api.get(PATH).json()["cached"] is True and adb.called("pull") == 1
    adb.on("shell", "dumpsys", "package", reply=fixture("ixio_version.txt").replace("21:58:01", "22:58:01"))
    changed = api.get(PATH).json()
    assert changed["cached"] is False and changed["fingerprint"] != first["fingerprint"]
    assert adb.called("pull") == 2
    assert not any(args[0] in ("install", "push") for args, _ in adb.calls)


def test_corrupt_cache_is_rebuilt(api: ContractClient, adb: FakeAdb, monkeypatch) -> None:
    setup_icon(api, adb, monkeypatch)
    first = api.get(PATH).json()
    root = api.client.app.state.container.icons.root
    (root / f"{first['fingerprint']}.png").write_bytes(b"truncated")
    assert api.get(PATH).json()["cached"] is False and adb.called("pull") == 2


def test_icon_failure_does_not_break_version_and_cleans_temporary_apks(
    api: ContractClient, adb: FakeAdb, monkeypatch
) -> None:
    setup_icon(api, adb, monkeypatch)

    def fail(_):
        raise IconUnavailable("unsupported")

    monkeypatch.setattr(api.client.app.state.container.icons.renderer, "render", fail)
    response = api.get(PATH)
    assert response.status_code == 404 and response.json()["code"] == "icon_unavailable"
    assert api.get(f"/devices/{SERIAL}/packages/{PACKAGE}").json()["version_code"] == "13424"
    assert list(api.client.app.state.container.icons.root.iterdir()) == []


def test_device_drawable_icon_avoids_apk_download_and_is_cached(api: ContractClient, adb: FakeAdb):
    package = "com.google.android.youtube"
    adb.on("shell", "pm", "path", reply=fixture("ixio_pm_path.txt"))
    adb.on("shell", "dumpsys", "package", reply=fixture("ixio_version.txt"))
    raw = fixture("youtube_icon.json")
    adb.default = lambda args, serial: raw if len(args) > 1 and args[1].startswith("CLASSPATH=") else ""
    path = f"/devices/{SERIAL}/packages/{package}/icon"
    first = api.get(path).json()
    assert first["cached"] is False
    assert base64.b64decode(first["data_base64"]).startswith(b"\x89PNG\r\n\x1a\n")
    assert api.get(path).json()["cached"] is True
    assert adb.called("push") == 1 and adb.called("shell", "rm", "-f") == 1
    assert not adb.called("pull") and not adb.called("install")
