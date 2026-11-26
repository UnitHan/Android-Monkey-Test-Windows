import type { Schemas } from "../api/client";
import { AIPerformance } from "./AIPerformance";

type Stats = Schemas["PerfStats"];
const metrics: [keyof Stats, string][] = [
  ["memory_mb", "메모리 PSS (MB)"], ["cpu_percent", "CPU 코어 합산 (%)"], ["cpu_total_percent", "CPU 기기 용량 대비 (%)"],
];
const num = (v: number | null | undefined) => v == null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });

function StatsTable({ stats }: { stats: Stats }) {
  return <div className="resource-table" tabIndex={0} aria-label="성능 자원 통계"><table><thead><tr>
    <th>지표</th><th>표본</th><th>평균</th><th>시간 가중 평균</th><th>최소</th><th>최대</th><th>표준편차 σ</th><th>P50</th><th>P90</th><th>P95</th><th>관측 구간</th>
  </tr></thead><tbody>{metrics.map(([key, label]) => {
    const s = stats[key]!;
    return <tr key={key}><th>{label}</th><td>{s.samples}</td><td>{num(s.avg)}</td><td>{num(s.time_weighted_avg)}</td>
      <td>{num(s.min)}</td><td>{num(s.max)}</td><td>{num(s.stddev)}</td><td>{num(s.median)}</td>
      <td>{num(s.p90)}</td><td>{num(s.p95)}</td><td>{num(s.observed_duration_s)}초</td></tr>;
  })}</tbody></table></div>;
}

export function ResourceAssessment({ report }: { report: Schemas["SessionReport"] }) {
  const assessment = report.resource_assessment;
  if (!assessment) return <p>새 분석 결과를 불러오려면 화면을 새로고침해 주세요.</p>;
  return <section className="resource-assessment">
    <AIPerformance key={report.session.id} report={report} />
    <div className="resource-heading"><strong>성능 자원 관측 요약</strong><span>
      실제 실행 {num(assessment.execution_duration_s)}초 · 수집 표본 {assessment.sample_count}개 · 수집원 {assessment.collectors.join(", ") || "없음"}</span></div>
    <StatsTable stats={report.perf} />
    <div className="resource-findings">{assessment.findings.map(f => <article key={f.metric} className={`resource-finding ${f.status}`}>
      <h3>{f.title}</h3><p>{f.evidence}</p><div>{f.recommendation}</div>
    </article>)}</div>
    <details><summary>계산 방식과 해석 범위</summary><ul>{assessment.notes.map((note, i) => <li key={i}>{note}</li>)}</ul></details>
    {report.per_run.length > 0 && <details><summary>회차별 통계 비교</summary>{report.per_run.map(r => <div key={r.run}>
      <h4>{r.run}회차</h4><StatsTable stats={r.stats} /></div>)}</details>}
    <div className="resource-issues"><strong>로그에서 확인된 이슈</strong>{report.issue_suggestions.map((s, i) => <p key={i}>{s}</p>)}</div>
  </section>;
}
