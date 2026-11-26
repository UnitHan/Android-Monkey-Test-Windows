"""Render SessionReport as a standalone HTML file (Chart.js from CDN)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, select_autoescape

from monkey_api.domain.report import SessionReport

_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monkey Report {{ s.config.package }}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f9f9f9;--fg:#191919;--card:#fff;--muted:#666;--line:#e7e7e7;--axis:#c2c2c2;--bad:#dc3c3d;--ok:#006c10;--s1:#257de0;--s2:#f47230}
@media (prefers-color-scheme:dark){:root{--bg:#0b0b0b;--fg:#efefef;--card:#191919;--muted:#9c9c9c;--line:#303030;--axis:#474747;--bad:#eb6263;--ok:#53c556;--s1:#338ced;--s2:#e76624}}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,"Noto Sans KR",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}
table{width:100%;border-collapse:collapse}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi div{font-size:22px;font-weight:600}.kpi span{color:var(--muted);font-size:12px;display:block}
.bad{color:var(--bad)}.ok{color:var(--ok)}pre{white-space:pre-wrap;font-size:12px;overflow-x:auto}
</style></head><body><main>
<h1>Monkey Test Report</h1>
<div class="card kpi">
 <div><span>Package</span>{{ s.config.package }}</div>
 <div><span>Device</span>{{ s.device.model if s.device else s.config.device_serial }}</div>
 <div><span>State</span>{{ s.state.value }}</div>
 <div><span>Runs</span>{{ s.runs|length }} / {{ s.config.repeats }}</div>
 <div><span>Events sent</span>{{ "{:,}".format(r.total_events_sent) }}</div>
 <div><span>Crash</span><b class="{{ 'bad' if s.issue_counts.crash + s.issue_counts.native_crash else 'ok' }}">
   {{ s.issue_counts.crash + s.issue_counts.native_crash }}</b></div>
 <div><span>ANR</span><b class="{{ 'bad' if s.issue_counts.anr else 'ok' }}">{{ s.issue_counts.anr }}</b></div>
</div>
<div class="card"><h2>Suggestions</h2><ul>{% for x in r.suggestions %}<li>{{ x }}</li>{% endfor %}</ul></div>
<div class="card"><h2>Performance</h2><div class="charts"><figure><figcaption>Memory (PSS, MB)</figcaption><canvas id="mem" height="160"></canvas></figure><figure><figcaption>CPU (%)</figcaption><canvas id="cpu" height="160"></canvas></figure></div></div>
<div class="card"><h2>Runs</h2><table><tr><th>#</th><th>Seed</th><th>Events</th><th>Duration</th>
<th>End</th><th>Crash</th><th>ANR</th><th>Mem peak</th><th>CPU peak</th></tr>
{% for x in s.runs %}<tr><td>{{ x.run }}</td><td>{{ x.seed }}</td><td>{{ x.events_sent }}/{{ x.events_target }}</td>
<td>{{ "%.0f"|format(x.duration_s) }}s</td><td>{{ x.end_reason }}</td><td>{{ x.crashes }}</td><td>{{ x.anrs }}</td>
<td>{{ x.mem_peak_mb or "-" }}</td><td>{{ x.cpu_peak_percent or "-" }}</td></tr>{% endfor %}</table></div>
<div class="card"><h2>Issues ({{ r.issues|length }})</h2>
{% for i in r.issues %}<details><summary>[run {{ i.run }}] {{ i.kind }}: {{ i.summary }}</summary>
<pre>{{ i.lines|join("\n") }}</pre></details>{% else %}<p>None</p>{% endfor %}</div>
</main>
<script id="data" type="application/json">{{ samples_json }}</script>
<script>
const d = JSON.parse(document.getElementById('data').textContent);
const css = getComputedStyle(document.documentElement), v = n => css.getPropertyValue(n).trim();
const labels = d.map(x => x.at.slice(11, 19));
function line(id, label, values, color, max) {
  new Chart(document.getElementById(id), {type: 'line',
    data: {labels, datasets: [{label, data: values, borderColor: color, borderWidth: 2, pointRadius: 0,
                               pointHoverRadius: 4, spanGaps: true, tension: 0}]},
    options: {animation: false, interaction: {mode: 'index', intersect: false},
      plugins: {legend: {display: false}},
      scales: {x: {ticks: {color: v('--muted'), maxTicksLimit: 6}, grid: {display: false}, border: {color: v('--axis')}},
               y: {beginAtZero: true, max, ticks: {color: v('--muted')}, grid: {color: v('--line')}, border: {display: false}}}}});
}
line('mem', 'Memory MB', d.map(x => x.memory_mb), v('--s1'));
line('cpu', 'CPU %', d.map(x => x.cpu_percent), v('--s2'), 100);
</script></body></html>
"""

_env = Environment(autoescape=select_autoescape(default=True))
_template = _env.from_string(_TEMPLATE)


def render_html(report: SessionReport) -> str:
    samples_json = ("[" + ",".join(s.model_dump_json() for s in report.samples) + "]").replace("</", "<\\/")
    return _template.render(s=report.session, r=report, samples_json=samples_json)


def write_html(report: SessionReport, path: Path) -> Path:
    path.write_text(render_html(report), encoding="utf-8")
    return path
