from pathlib import Path

from fakes import PACKAGE, SERIAL
from openpyxl import load_workbook

from monkey_api.services import report_export


def create(api):
    return api.post("/sessions", json={"device_serial": SERIAL, "package": PACKAGE, "preset_id": "smoke"}).json()["id"]


def test_excel_export_saves_a_real_workbook_and_returns_path(api, settings):
    sid = create(api)
    response = api.post(f"/sessions/{sid}/exports/xlsx")
    assert response.status_code == 200
    path = Path(response.json()["path"])
    assert path.parent == settings.export_dir
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["Summary", "Runs", "Issues", "Performance", "Resource Statistics"]
    assert workbook["Summary"]["B2"].value == sid
    html = api.get(f"/sessions/{sid}/report.html")
    assert html.status_code == 200 and "text/html" in html.headers["content-type"]
    assert "attachment" not in html.headers.get("content-disposition", "")


def test_export_missing_session_and_write_failure_are_visible(api, monkeypatch):
    assert api.post("/sessions/s_missing/exports/xlsx").status_code == 404
    sid = create(api)

    def locked(*args):
        raise PermissionError("locked workbook")

    monkeypatch.setattr(report_export, "write_excel", locked)
    response = api.post(f"/sessions/{sid}/exports/xlsx")
    assert response.status_code == 500
    assert "저장하지 못했습니다" in response.json()["detail"]
