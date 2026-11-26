from datetime import UTC, datetime, timedelta

from monkey_api.adapters.report.html import render_html
from monkey_api.adapters.report.html_charts import chart_data
from monkey_api.domain.models import Issue, PerfSample, Session
from monkey_api.domain.report import build_report
from monkey_api.services.session_service import resolve_config

START = datetime(2026, 11, 26, tzinfo=UTC)


def point(second, value=0, **kwargs):
    return PerfSample(at=START + timedelta(seconds=second), run=1, memory_mb=value, cpu_percent=value, **kwargs)


def test_report_offline_charts_keep_zero_and_escape_untrusted_logs():
    session = Session(
        id="s_test",
        state="cancelled",
        created_at=START,
        config=resolve_config("SER", "com.example.very.long.package.name", "smoke", None),
    )
    issue = Issue(id="i1", kind="crash", run=1, at=START, summary="<script>alert(1)</script>", lines=["<b>log</b>"])
    html = render_html(build_report(session, [issue], [point(0), point(2, 119)]))
    assert "<script" not in html and "<canvas" not in html and "https://" not in html
    assert html.count("<svg ") == 2 and "<path d=" in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;log&lt;/b&gt;" in html
    assert "최솟값 0" in html and "최댓값 119" in html
    assert "사용자 중단" in html and "전체 테스트 완료를 의미하지 않습니다" in html
    assert "P90" in html and "표준편차" in html and "판단 보류" in html
    assert "2026.11.26 09:00:00" in html


def test_chart_does_not_connect_missing_samples_gaps_or_different_runs():
    samples = [point(0), point(2, 5), point(4, None), point(6, 10), point(30, 20), point(32, 30)]
    samples += [point(34, 40).model_copy(update={"run": 2}), point(36, 99, running=False)]
    data = chart_data(samples, "memory_mb", "메모리", "MB", "blue")
    assert len(data["paths"]) == 2 and len(data["dots"]) == 2
    assert data["stats"].samples == 6 and data["stats"].max == 40


def test_large_series_preserves_peaks_and_cpu_above_100():
    samples = [point(i, 800 if i == 555 else 5) for i in range(1000)]
    data = chart_data(samples, "cpu_percent", "CPU", "%", "blue")
    assert data["stats"].max == 800 and data["stats"].samples == 1000
    assert data["y_ticks"][-1][1] > 800
    assert len(data["paths"][0].split()) <= 400
    assert min(float(p.split(",")[1]) for p in data["paths"][0].split()) < 50


def test_no_samples_report_has_explicit_empty_state():
    session = Session(
        id="s_empty", state="created", created_at=START, config=resolve_config("SER", "com.example.app", "smoke", None)
    )
    html = render_html(build_report(session, [], []))
    assert "수집된 성능 표본이 없습니다" in html and "<svg " not in html
