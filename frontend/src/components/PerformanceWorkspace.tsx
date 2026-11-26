import { useMemo, useState } from "react";
import type { Session } from "../api/client";
import { TERMINAL, usePerf } from "../api/hooks";
import { PerfChart } from "./PerfChart";

export function PerformanceWorkspace({ session }: { session: Session | undefined }) {
  const perf = usePerf(session?.id ?? null);
  const [minutes, setMinutes] = useState(0);
  const [run, setRun] = useState(0);
  const samples = perf.data ?? [];
  const visible = useMemo(() => {
    const end = samples.length ? Date.parse(samples[samples.length - 1].at) : 0;
    return samples.filter(s => (!run || s.run === run) && (!minutes || Date.parse(s.at) >= end - minutes * 60000));
  }, [samples, minutes, run]);
  if (!session) return <div className="dashboard-empty">메인 패널에서 테스트를 시작하거나 이전 결과를 선택해 주세요.</div>;
  const latest = samples[samples.length - 1];
  const live = !TERMINAL.has(session.state);
  return <section className="analytics-page">
    <header className="analytics-heading"><div><p className="eyebrow">PERFORMANCE MONITOR</p><h1>앱 성능 모니터</h1><p>{session.config.package}</p></div>
      <span className={`status-pill ${live ? "live" : ""}`}>{live ? "● 실시간 측정" : "저장된 결과"}</span></header>
    <div className="analytics-toolbar"><div className="range-options" aria-label="표시 시간 범위">
      {[0, 1, 5, 15].map(m => <button key={m} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{m ? `최근 ${m}분` : "전체"}</button>)}</div>
      <label>회차 <select value={run} onChange={e => setRun(Number(e.target.value))}><option value={0}>전체 회차</option>
        {Array.from({ length: session.config.repeats }, (_, i) => <option key={i} value={i + 1}>{i + 1}회차</option>)}</select></label>
      <span className="collector-badge">{latest?.source === "appkium" ? "Appkium 기기 수집기" : latest ? "ADB 수집" : "수집기 연결 중"}</span></div>
    <div className="metric-cards">
      <article><span>수집 표본</span><strong>{samples.length.toLocaleString()}<small> 개</small></strong><p>현재 범위 {visible.length.toLocaleString()}개</p></article>
      <article><span>진행 회차</span><strong>{session.progress.current_run}<small> / {session.config.repeats}</small></strong><p>{session.device?.model ?? session.config.device_serial}</p></article>
      <article><span>수집 소요 시간</span><strong>{latest?.sample_cost_ms?.toFixed(0) ?? "—"}<small> ms</small></strong><p>{latest?.at ? `최근 수신 ${new Date(latest.at).toLocaleTimeString()}` : "수신 대기"}</p></article>
      <article><span>앱 상태</span><strong>{latest?.running == null ? "—" : latest.running ? "실행 중" : "종료됨"}</strong><p>{latest?.foreground == null ? "" : latest.foreground ? "전경 화면" : "백그라운드"}</p></article>
    </div>
    {perf.error && <p role="alert" className="c-red">성능 데이터를 읽지 못했습니다: {perf.error.message}</p>}
    <div className="analytics-charts">
      <PerfChart samples={visible} metric="memory_mb" title="앱 메모리 · PSS" unit="MB" color="#2563eb" />
      <PerfChart samples={visible} metric="cpu_percent" title="앱 CPU · 코어 합산" unit="%" color="#8b5cf6" />
      <PerfChart samples={visible} metric="fps" title="화면 프레임 속도" unit="FPS" color="#059669" />
      <PerfChart samples={visible} metric="frame_time_max_ms" title="최대 프레임 시간" unit="ms" color="#ea580c" />
    </div>
    <p className="analytics-note">CPU는 코어 합산 값으로 100%를 넘을 수 있습니다. PSS는 기기 수집기에서 약 5초마다 갱신합니다.
      지원되지 않거나 아직 계산할 수 없는 값은 —로 표시합니다. 긴 기록은 극값을 보존해 화면에 축약합니다.</p>
  </section>;
}
