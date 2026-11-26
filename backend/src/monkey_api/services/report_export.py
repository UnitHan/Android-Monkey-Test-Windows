"""Save a generated workbook to the desktop user's export directory."""

from pathlib import Path

from monkey_api.adapters.report.excel import write_excel
from monkey_api.core.errors import AppError
from monkey_api.core.logging import log
from monkey_api.services.session_ledger import SessionLedger
from monkey_api.services.session_runner import build_session_report


def export_excel(ledger: SessionLedger, session_id: str, directory: Path) -> Path:
    report = build_session_report(ledger, session_id)
    path = directory / f"{session_id}.xlsx"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        write_excel(report, path)
    except OSError as exc:
        raise AppError("엑셀 파일을 저장하지 못했습니다. 파일이 열려 있는지와 폴더 쓰기 권한을 확인해 주세요.") from exc
    log("session", "Excel report exported", session_id=session_id, filename=path.name)
    return path.resolve()


def delete_export(session_id: str, directory: Path) -> None:
    path = directory / f"{session_id}.xlsx"
    if path.resolve().parent != directory.resolve() or path.is_symlink():
        raise AppError("안전한 보고서 경로가 아니어서 삭제하지 않았습니다.")
    try:
        path.unlink(missing_ok=True)
    except OSError:
        raise AppError("내보낸 엑셀 보고서를 삭제하지 못했습니다. 엑셀에서 파일을 닫고 다시 시도해 주세요.") from None
