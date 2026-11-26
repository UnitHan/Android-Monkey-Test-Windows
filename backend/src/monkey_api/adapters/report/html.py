"""Standalone, script-free HTML reports, including offline SVG charts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from monkey_api.adapters.report.html_charts import chart_data
from monkey_api.domain.ai_performance import LABELS
from monkey_api.domain.report import SessionReport

_DIR = Path(__file__).parent
_KST = timezone(timedelta(hours=9))
_STATES = {
    "created": "대기",
    "preparing": "준비 중",
    "running": "진행 중",
    "stopping": "중단 처리 중",
    "completed": "완료",
    "cancelled": "사용자 중단",
    "failed": "실패",
}
_ENDS = {
    "completed": "이벤트 완료",
    "time_limit": "시간 제한 도달",
    "stopped": "사용자 중단",
    "failed_to_start": "시작 실패",
    "aborted": "실행 중단",
    "device_lost": "기기 연결 끊김",
}


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:,.2f}".rstrip("0").rstrip(".")


def _duration(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 60:
        return f"{value:.1f}초"
    hours, rest = divmod(round(value), 3600)
    minutes, seconds = divmod(rest, 60)
    return (f"{hours}시간 " if hours else "") + f"{minutes}분 {seconds}초"


def _date(value: datetime | None) -> str:
    return value.astimezone(_KST).strftime("%Y.%m.%d %H:%M:%S") if value else "—"


_env = Environment(loader=FileSystemLoader(_DIR), autoescape=select_autoescape(default=True))
_env.filters.update(number=_number, duration=_duration, kst=_date)
_template = _env.get_template("report.html.j2")
_css = (_DIR / "report.css").read_text("utf-8")


def render_html(report: SessionReport) -> str:
    charts = [
        chart_data(report.samples, "memory_mb", "메모리 · PSS", "MB", "#2563eb"),
        chart_data(report.samples, "cpu_percent", "CPU · 코어 합산", "%", "#7c3aed"),
    ]
    return _template.render(r=report, s=report.session, css=_css, states=_STATES, ends=_ENDS, charts=charts, verdicts=LABELS)


def write_html(report: SessionReport, path: Path) -> Path:
    path.write_text(render_html(report), encoding="utf-8")
    return path
