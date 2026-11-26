"""Write SessionReport as an .xlsx workbook (Summary, Runs, Issues, Performance)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from monkey_api.domain.report import SessionReport


def _sheet(wb: Workbook, title: str, header: list[str], rows: list[list[object]]) -> Worksheet:
    ws = wb.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for idx, col in enumerate(ws.columns, 1):
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[ws.cell(1, idx).column_letter].width = min(width + 2, 60)
    return ws


def write_excel(report: SessionReport, path: Path) -> Path:
    s = report.session
    wb = Workbook()
    assert wb.active is not None
    wb.remove(wb.active)
    _sheet(
        wb,
        "Summary",
        ["항목", "값"],
        [
            ["Session", s.id],
            ["Package", s.config.package],
            ["Device", s.device.model if s.device else s.config.device_serial],
            ["Android", s.device.android_version if s.device else ""],
            ["Preset", s.config.preset_id],
            ["State", s.state.value],
            ["Started", s.started_at.isoformat() if s.started_at else ""],
            ["Ended", s.ended_at.isoformat() if s.ended_at else ""],
            ["Events sent", report.total_events_sent],
            ["Crash", s.issue_counts.crash + s.issue_counts.native_crash],
            ["ANR", s.issue_counts.anr],
            *[["Suggestion", x] for x in report.suggestions],
        ],
    )
    _sheet(
        wb,
        "Runs",
        ["Run", "Seed", "Events sent", "Events target", "Duration s", "End", "Crash", "ANR", "Mem peak", "CPU peak"],
        [
            [
                r.run,
                r.seed,
                r.events_sent,
                r.events_target,
                r.duration_s,
                r.end_reason,
                r.crashes,
                r.anrs,
                r.mem_peak_mb,
                r.cpu_peak_percent,
            ]
            for r in s.runs
        ],
    )
    _sheet(
        wb,
        "Issues",
        ["Run", "Kind", "At", "Summary", "Log"],
        [[i.run, i.kind, i.at.isoformat(), i.summary, "\n".join(i.lines)[:32000]] for i in report.issues],
    )
    _sheet(
        wb,
        "Performance",
        ["At", "Run", "Memory MB", "CPU %"],
        [[p.at.isoformat(), p.run, p.memory_mb, p.cpu_percent] for p in report.samples],
    )
    wb.save(path)
    return path
