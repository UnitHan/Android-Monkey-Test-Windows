import { api } from "../api/client";
import {
  TERMINAL, useDeleteSession, useEvents, useIssues, usePerf, useSession, useSessionStream, useStopSession,
} from "../api/hooks";
import { ErrorNote, StateBadge, fmtTime, formatDuration, type ShowLogs } from "./common";
import { PerfChart } from "./PerfChart";

const END_LABEL: Record<string, string> = {
  completed: "완료", time_limit: "목표 시간 도달", aborted: "중단(monkey)", stopped: "사용자 중지",
  failed_to_start: "시작 실패", device_lost: "디바이스 끊김",
};

export function SessionDetail(props: { id: string; onShowLogs: ShowLogs; onDeleted: () => void }) {
  const session = useSession(props.id);
  const s = session.data;
  useSessionStream(props.id, s?.state);
  const issues = useIssues(props.id);
  const perf = usePerf(props.id);
  const events = useEvents(props.id);
  const stop = useStopSession();
  const del = useDeleteSession();

  if (session.error) return <ErrorNote error={session.error} onShowLogs={props.onShowLogs} />;
  if (!s) return <div className="card muted">불러오는 중…</div>;

  const active = !TERMINAL.has(s.state) && s.state !== "created";
  const p = s.progress;
  const crashes = s.issue_counts.crash + s.issue_counts.native_crash;

  return (
    <>
      <section className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>{s.config.package}</h2>
          <StateBadge state={s.state} />
          <span className="grow" />
          {active && <button className="danger" onClick={() => stop.mutate(s.id)} disabled={s.state === "stopping"}>중지</button>}
          {TERMINAL.has(s.state) && (
            <>
              <a href={api.reportUrl(s.id, "html")} target="_blank" rel="noreferrer">HTML 리포트</a>
              <a href={api.reportUrl(s.id, "xlsx")}>Excel</a>
              <button className="danger" onClick={() => del.mutate(s.id, { onSuccess: props.onDeleted })}>삭제</button>
            </>
          )}
          <button onClick={() => props.onShowLogs({ session_id: s.id })}>세션 로그</button>
        </div>
        <p className="small muted">
          {s.device ? `${s.device.model} (Android ${s.device.android_version})` : s.config.device_serial}
          {s.app_version?.version_name && ` · v${s.app_version.version_name}`} · 프리셋 {s.config.preset_id} ·{" "}
          {s.config.events.toLocaleString()} 이벤트 × {s.config.repeats}회 · throttle {s.config.throttle_ms}ms ·{" "}
          시작 {fmtTime(s.started_at)} · 예상 {formatDuration(s.estimated_total_s)}
        </p>
        {s.error && <div className="error">{s.error}</div>}
        <ErrorNote error={stop.error ?? del.error} onShowLogs={props.onShowLogs} />
        {active && (
          <div style={{ marginTop: 8 }}>
            <div className="row small">
              <span>{p.current_run}/{p.total_runs}회차</span>
              <span className="muted">이벤트 {p.events_sent.toLocaleString()}/{p.events_target.toLocaleString()} · {formatDuration(p.elapsed_s)}</span>
              <span className="grow" />
              <b>{p.run_percent}%</b>
            </div>
            <div className="progress" role="progressbar" aria-valuenow={p.run_percent} aria-valuemin={0} aria-valuemax={100}>
              <div style={{ width: `${p.run_percent}%` }} />
            </div>
          </div>
        )}
        <div className="kpis" style={{ marginTop: 12 }}>
          <div className="kpi"><span>완료 회차</span><b>{s.runs.length}/{s.config.repeats}</b></div>
          <div className="kpi"><span>Crash</span><b style={{ color: crashes ? "var(--bad)" : undefined }}>{crashes}</b></div>
          <div className="kpi"><span>ANR</span><b style={{ color: s.issue_counts.anr ? "var(--bad)" : undefined }}>{s.issue_counts.anr}</b></div>
          <div className="kpi"><span>총 이벤트</span><b>{s.runs.reduce((a, r) => a + r.events_sent, 0).toLocaleString()}</b></div>
        </div>
      </section>

      <section className="card">
        <h2>성능</h2>
        <div className="charts">
          <PerfChart samples={perf.data ?? []} metric="memory_mb" title="메모리 (PSS)" unit="MB" color="var(--s1)" />
          <PerfChart samples={perf.data ?? []} metric="cpu_percent" title="CPU" unit="%" color="var(--s2)" fixedMax={100} />
        </div>
      </section>

      <section className="card">
        <h2>회차 결과</h2>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>#</th><th>Seed</th><th>이벤트</th><th>시간</th><th>종료</th><th>Crash</th><th>ANR</th><th>Mem 최대</th><th>CPU 최대</th><th>logcat</th></tr>
            </thead>
            <tbody>
              {s.runs.map((r) => (
                <tr key={r.run}>
                  <td>{r.run}</td><td>{r.seed}</td><td>{r.events_sent.toLocaleString()}/{r.events_target.toLocaleString()}</td>
                  <td>{formatDuration(r.duration_s)}</td><td>{END_LABEL[r.end_reason] ?? r.end_reason}</td>
                  <td>{r.crashes}</td><td>{r.anrs}</td>
                  <td>{r.mem_peak_mb ?? "-"}</td><td>{r.cpu_peak_percent ?? "-"}</td>
                  <td><a href={api.logcatUrl(s.id, r.run)} target="_blank" rel="noreferrer">보기</a></td>
                </tr>
              ))}
              {s.runs.length === 0 && <tr><td colSpan={10} className="muted">아직 완료된 회차가 없습니다.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>이슈 ({issues.data?.length ?? 0})</h2>
        {issues.data?.map((i) => (
          <details key={i.id}>
            <summary><span className="badge bad">{i.kind}</span> {i.run}회차 · {i.summary}</summary>
            <pre>{i.lines.join("\n")}</pre>
          </details>
        ))}
        {issues.data?.length === 0 && <p className="muted small">감지된 이슈가 없습니다.</p>}
      </section>

      <section className="card">
        <h2>이벤트 로그</h2>
        <ul className="list mono" style={{ maxHeight: 240, overflowWrap: "anywhere" }}>
          {[...(events.data ?? [])].reverse().map((e) => (
            <li key={e.seq}>#{e.seq} {new Date(e.at).toLocaleTimeString()} <b>{e.type}</b> {JSON.stringify(e.data)}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
