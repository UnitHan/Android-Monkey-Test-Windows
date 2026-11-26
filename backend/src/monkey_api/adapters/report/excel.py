"""Write SessionReport as an .xlsx workbook (Summary, Runs, Issues, Performance)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from monkey_api.domain.ai_performance import LABELS
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
        [
            "At",
            "Run",
            "Memory PSS MB",
            "CPU core sum %",
            "Collector",
            "CPU device capacity %",
            "RSS MB",
            "FPS",
            "Jank",
            "Max frame ms",
            "Threads",
            "Battery temp C",
            "Sample cost ms",
        ],
        [
            [
                p.at.isoformat(),
                p.run,
                p.memory_mb,
                p.cpu_percent,
                p.source,
                p.cpu_total_percent,
                p.rss_mb,
                p.fps,
                p.jank_count,
                p.frame_time_max_ms,
                p.threads,
                p.battery_temp_c,
                p.sample_cost_ms,
            ]
            for p in report.samples
        ],
    )
    _statistics_sheet(wb, report)
    if report.ai_performance:
        _analysis_sheet(wb, report)
    wb.save(path)
    return path


def _analysis_sheet(wb: Workbook, report: SessionReport) -> None:
    ai = report.ai_performance
    assert ai is not None
    rows = [
        ["모델", ai.model],
        ["분석 시각", ai.created_at.isoformat()],
        ["판정", LABELS[ai.conclusion.verdict]],
        ["요약", ai.conclusion.summary],
        ["범위", "관측 범위의 AI 해석이며 출시 합격 판정은 아닙니다."],
    ]
    for key, label in (("memory", "메모리"), ("cpu", "CPU"), ("stability", "안정성")):
        f = getattr(ai.conclusion, key)
        rows.append([label, f"{LABELS[f.verdict]}: {f.reason}"])
    rows += [["권고사항", text] for text in ai.conclusion.recommendations]
    rows += [["한계", text] for text in ai.conclusion.limitations + ai.guardrails]
    ws = _sheet(wb, "AI Performance", ["항목", "내용"], rows)
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Model text is never an Excel formula.


def _statistics_sheet(wb: Workbook, report: SessionReport) -> None:
    rows: list[list[object]] = []
    scopes = [("전체", report.perf), *[(f"{r.run}회차", r.stats) for r in report.per_run]]
    for scope, stats in scopes:
        for key, label in (
            ("memory_mb", "PSS MB"),
            ("cpu_percent", "CPU 코어 합산 %"),
            ("cpu_total_percent", "CPU 기기 용량 대비 %"),
        ):
            metric = getattr(stats, key)
            rows.append(
                [
                    scope,
                    label,
                    metric.samples,
                    metric.avg,
                    metric.time_weighted_avg,
                    metric.min,
                    metric.max,
                    metric.stddev,
                    metric.median,
                    metric.p90,
                    metric.p95,
                    metric.observed_duration_s,
                    metric.reference_exceeded_s if key == "cpu_total_percent" else None,
                    metric.longest_exceeded_s if key == "cpu_total_percent" else None,
                ]
            )
    ws = _sheet(
        wb,
        "Resource Statistics",
        [
            "범위",
            "지표",
            "표본",
            "평균",
            "시간 가중 평균",
            "최소",
            "최대",
            "표준편차",
            "P50",
            "P90",
            "P95",
            "관측 초",
            "CPU 참고선 이상 초",
            "CPU 최장 연속 초",
        ],
        rows,
    )
    ws.append([])
    for note in report.resource_assessment.notes:
        ws.append([note])
