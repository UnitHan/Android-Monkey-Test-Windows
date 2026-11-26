import { useMemo, useState } from "react";
import type { PerfSample } from "../api/client";
import { chartSamples, stats, type Metric } from "./chartData";

const W = 900, H = 250, L = 56, R = 20, T = 18, B = 38;
const value = (v: number | undefined | null) => v == null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
const time = (s: string) => new Date(s).toLocaleTimeString("ko-KR", { hour12: false });

export function PerfChart(props: {
  samples: PerfSample[]; metric: Metric; title: string; unit: string; color: string; fixedMax?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const samples = useMemo(() => chartSamples(props.samples, props.metric), [props.samples, props.metric]);
  const summary = useMemo(() => stats(props.samples, props.metric), [props.samples, props.metric]);
  const peak = summary.peak ?? 0;
  const max = Math.max(props.fixedMax ?? 1, Math.ceil(peak * 1.15 / 5) * 5);
  const first = samples.length ? Date.parse(samples[0].at) : 0;
  const span = Math.max(1, samples.length ? Date.parse(samples[samples.length - 1].at) - first : 1);
  const x = (s: PerfSample) => L + (Date.parse(s.at) - first) / span * (W - L - R);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  let drawing = false, previous: PerfSample | undefined;
  const path = samples.map(s => {
    const v = s[props.metric];
    if (v == null) { drawing = false; previous = s; return ""; }
    if (previous && (previous.run !== s.run || Date.parse(s.at) - Date.parse(previous.at) > 15000)) drawing = false;
    const part = `${drawing ? "L" : "M"}${x(s).toFixed(1)},${y(v).toFixed(1)}`;
    drawing = true; previous = s; return part;
  }).join(" ");
  const point = hover == null ? undefined : samples[Math.min(hover, samples.length - 1)];
  return <figure className="metric-chart">
    <figcaption><div><span className="chart-dot" style={{ background: props.color }} /><strong>{props.title}</strong>
      <span className="metric-unit">{props.unit}</span></div>
      <button className="chart-toggle" onClick={() => setTable(!table)} aria-pressed={table}>{table ? "그래프" : "데이터"}</button></figcaption>
    <div className="chart-statistics"><b>{value(summary.latest)} <small>{props.unit}</small></b>
      <span>평균 <strong>{value(summary.mean)}</strong></span><span>최대 <strong>{value(summary.peak)}</strong></span>
      <span>P95 <strong>{value(summary.p95)}</strong></span></div>
    {!samples.length ? <div className="chart-empty">측정 데이터 대기 중</div> : table ? <div className="chart-table">
      <table><thead><tr><th>시각</th><th>회차</th><th>{props.title} ({props.unit})</th></tr></thead>
        <tbody>{props.samples.slice(-300).map((s, i) => <tr key={i}><td>{time(s.at)}</td><td>{s.run}</td><td>{value(s[props.metric])}</td></tr>)}</tbody></table>
      <p>최근 300개 표본 · 전체 값은 엑셀 보고서에서 확인하세요.</p></div> : <>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} aria-label={`${props.title}, 최대 ${value(summary.peak)} ${props.unit}`}
        onPointerLeave={() => setHover(null)} onKeyDown={e => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
            e.preventDefault(); setHover(i => Math.max(0, Math.min(samples.length - 1, (i ?? samples.length - 1) + (e.key === "ArrowLeft" ? -1 : 1))));
          }
        }} onPointerMove={e => {
          const box = e.currentTarget.getBoundingClientRect();
          const target = first + Math.max(0, Math.min(1, ((e.clientX - box.left) / box.width * W - L) / (W - L - R))) * span;
          let best = 0;
          for (let i = 1; i < samples.length; i++) if (Math.abs(Date.parse(samples[i].at) - target) < Math.abs(Date.parse(samples[best].at) - target)) best = i;
          setHover(best);
        }}>
        {[0, .25, .5, .75, 1].map(t => <g key={t}><line x1={L} x2={W - R} y1={y(t * max)} y2={y(t * max)} stroke="#e9eef5" />
          <text x={L - 10} y={y(t * max) + 5} textAnchor="end" fill="#718096" fontSize="17">{value(t * max)}</text></g>)}
        {[0, .25, .5, .75, 1].map(t => <text key={t} x={L + t * (W - L - R)} y={H - 10} textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"} fill="#718096" fontSize="15">
          {time(new Date(first + t * span).toISOString())}</text>)}
        {samples.filter((s, i) => i > 0 && s.run !== samples[i - 1].run).map(s => <g key={s.at}>
          <line x1={x(s)} x2={x(s)} y1={T} y2={H - B} stroke="#b9c6d8" strokeDasharray="4 4" />
          <text x={x(s) + 4} y={T + 10} fill="#718096" fontSize="11">{s.run}회차</text></g>)}
        <path d={path} stroke={props.color} strokeWidth="2" fill="none" strokeLinejoin="round" />
        {point && <g><line x1={x(point)} x2={x(point)} y1={T} y2={H - B} stroke="#97a6bb" strokeDasharray="3 3" />
          {point[props.metric] != null && <circle cx={x(point)} cy={y(point[props.metric]!)} r="4" fill={props.color} stroke="white" strokeWidth="2" />}</g>}
      </svg>
      <div className="chart-hover">{point ? `${time(point.at)} · ${point.run}회차 · ${value(point[props.metric])} ${props.unit}` : "마우스를 올리거나 ← → 키로 시점별 값을 확인하세요."}</div>
    </>}
  </figure>;
}
