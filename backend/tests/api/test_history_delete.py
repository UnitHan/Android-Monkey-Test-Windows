from pathlib import Path

from fakes import PACKAGE, SERIAL
from pytest import raises

from monkey_api.adapters.storage.session_repo import SessionRepository
from monkey_api.core.errors import AppError


def create(api):
    return api.post("/sessions", json={"device_serial": SERIAL, "package": PACKAGE, "preset_id": "smoke"}).json()["id"]


def test_delete_removes_nested_artifacts_export_and_survives_reload(api, settings):
    sid, other = create(api), create(api)
    folder = settings.sessions_dir / sid
    (folder / "nested").mkdir()
    (folder / "nested/raw.log").write_text("test log")
    (folder / "ai-performance.json").write_text("{}")
    exported = Path(api.post(f"/sessions/{sid}/exports/xlsx").json()["path"])
    api.get(f"/sessions/{sid}/report.html")
    assert api.delete(f"/sessions/{sid}").status_code == 204
    assert not folder.exists() and not exported.exists()
    assert api.get(f"/sessions/{sid}").status_code == 404
    assert api.get(f"/sessions/{other}").status_code == 200
    assert [s.id for s in SessionRepository(settings.sessions_dir).list()] == [other]


def test_locked_export_retains_history_for_retry(api, settings, monkeypatch):
    sid = create(api)
    exported = Path(api.post(f"/sessions/{sid}/exports/xlsx").json()["path"])
    unlink = Path.unlink

    def locked(path, *args, **kwargs):
        if path == exported:
            raise PermissionError("workbook is open")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    response = api.delete(f"/sessions/{sid}")
    assert response.status_code == 500
    assert api.get(f"/sessions/{sid}").status_code == 200
    assert (settings.sessions_dir / sid / "session.json").exists()


def test_repository_refuses_path_outside_session_root(api, settings, tmp_path):
    sid = create(api)
    repo = api.client.app.state.container.ledger.repo
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep")
    # Simulate a corrupted repository entry; the resolved deletion target must still be checked.
    repo._sessions["../outside"] = repo.get(sid)
    with raises(AppError):
        repo.delete("../outside")
    assert marker.exists()
