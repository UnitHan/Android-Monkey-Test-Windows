import type { Session } from "../api/client";

export function ResultsWorkspace({ session, history, onSelect }: {
  session: Session | undefined; history: Session[]; onSelect: (id: string) => void;
}) {
  const runs = session?.runs ?? [];
  const events = runs.reduce((n, r) => n + r.events_sent, 0);
  const elapsed = runs.reduce((n, r) => n + (r.execution_duration_s ?? r.duration_s), 0);
  const target = session?.config.target_minutes_per_run;
  const maxTime = Math.max(1, ...runs.flatMap(r => [r.execution_duration_s ?? r.duration_s, r.target_duration_s ?? 0]));
  const maxEvents = Math.max(1, ...runs.map(r => r.events_sent));
  return <section className="analytics-page">
    <header className="analytics-heading"><div><p className="eyebrow">TEST RESULTS</p><h1>테스트 결과 분석</h1><p>{session?.config.package ?? "분석할 세션을 선택해 주세요."}</p></div>
      <select className="session-picker" value={session?.id ?? ""} onChange={e => onSelect(e.target.value)} aria-label="분석할 테스트 결과">
        {!session && <option value="">테스트 선택</option>}{history.map(s => <option key={s.id} value={s.id}>{new Date(s.created_at).toLocaleString()} · {s.config.package}</option>)}</select></header>
    <div className="metric-cards">
      <article><span>누적 이벤트</span><strong>{events.toLocaleString()}</strong><p>완료된 회차 기준</p></article>
      <article><span>실행 시간 / 목표</span><strong>{(elapsed / 60).toFixed(1)}<small> / {target ? (target * (session?.config.repeats ?? 0)).toFixed(0) : "—"}분</small></strong><p>준비·정리 시간 제외</p></article>
      <article><span>Crash / ANR</span><strong>{(session?.issue_counts.crash ?? 0) + (session?.issue_counts.native_crash ?? 0)}<small> / {session?.issue_counts.anr ?? 0}</small></strong><p>네이티브 크래시 포함</p></article>
      <article><span>완료 회차</span><strong>{runs.length}<small> / {session?.config.repeats ?? 0}</small></strong><p>{session?.state ?? "세션 없음"}</p></article>
    </div>
    {!runs.length ? <div className="dashboard-empty">회차가 끝나면 시간 준수와 이벤트 분포를 표시합니다.</div> : <>
      <div className="analytics-charts">
        <section className="result-card"><h2>목표 대비 실행 시간</h2><p>회색: 목표 · 파랑: 실제 실행</p>
          {runs.map(r => <div className="run-bar-row" key={r.run}><b>{r.run}회차</b><div className="run-bar-track">
            <span className="target-bar" style={{ width: `${(r.target_duration_s ?? 0) / maxTime * 100}%` }} />
            <span className="actual-bar" style={{ width: `${(r.execution_duration_s ?? r.duration_s) / maxTime * 100}%` }} /></div>
            <span>{(r.execution_duration_s ?? r.duration_s).toFixed(2)}초</span></div>)}</section>
        <section className="result-card"><h2>회차별 이벤트 주입량</h2><p>괄호는 이벤트 소진 후 추가 실행 횟수</p>
          {runs.map(r => <div className="run-bar-row" key={r.run}><b>{r.run}회차</b><div className="run-bar-track">
            <span className="actual-bar event-bar" style={{ width: `${r.events_sent / maxEvents * 100}%` }} /></div>
            <span>{r.events_sent.toLocaleString()} (+{Math.max(0, r.segments.length - 1)})</span></div>)}</section>
      </div>
      <section className="result-card"><h2>회차별 품질 지표</h2><div className="chart-table"><table><thead><tr><th>회차</th><th>Crash</th><th>ANR</th><th>1,000 이벤트당 이슈</th><th>메모리 최대</th><th>CPU 최대</th><th>종료 사유</th></tr></thead>
        <tbody>{runs.map(r => <tr key={r.run}><td>{r.run}</td><td>{r.crashes}</td><td>{r.anrs}</td><td>{r.events_sent ? ((r.crashes + r.anrs) * 1000 / r.events_sent).toFixed(2) : "—"}</td>
          <td>{r.mem_peak_mb?.toFixed(1) ?? "—"} MB</td><td>{r.cpu_peak_percent?.toFixed(1) ?? "—"}%</td><td>{r.end_reason}</td></tr>)}</tbody></table></div></section>
    </>}
  </section>;
}
