import { useMemo, useRef, useState } from "react";
import type { PerfSample } from "../api/client";

const W = 600, H = 200, PAD = { l: 44, r: 12, t: 12, b: 28 };

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((c) => c >= v) ?? v;
}

/** Single-series line chart (one measure per chart: never a dual axis). Crosshair + tooltip, table view. */
export function PerfChart(props: {
  samples: PerfSample[];
  metric: "memory_mb" | "cpu_percent";
  title: string;
  unit: string;
  color: string;
  fixedMax?: number;
}) {
  const { samples, metric } = props;
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  const values = samples.map((s) => s[metric] ?? null);
  const max = props.fixedMax ?? niceMax(Math.max(0, ...values.map((v) => v ?? 0)) * 1.1);
  const n = samples.length;
  const x = (i: number) => PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - PAD.l - PAD.r));
  const y = (v: number) => PAD.t + (1 - v / max) * (H - PAD.t - PAD.b);

  const path = useMemo(() => {
    let d = "", pen = false;
    values.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  }, [samples, max]);

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const box = svgRef.current?.getBoundingClientRect();
    if (!box || n === 0) return;
    const px = ((e.clientX - box.left) / box.width) * W;
    const i = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  const latest = [...values].reverse().find((v) => v != null);
  const ticks = [0, max / 2, max];
  const hv = hover != null ? values[hover] : null;

  return (
    <figure className="chart" style={{ margin: 0 }}>
      <figcaption className="row">
        <b>{props.title}</b>
        <span className="muted small">현재 {latest != null ? `${latest.toFixed(1)} ${props.unit}` : "-"}</span>
        <button className="small" style={{ marginLeft: "auto" }} onClick={() => setTable((t) => !t)} aria-pressed={table}>
          {table ? "차트" : "표"}
        </button>
      </figcaption>
      {table ? (
        <div className="scroll" style={{ maxHeight: 220 }}>
          <table>
            <thead><tr><th>시각</th><th>회차</th><th>{props.title}</th></tr></thead>
            <tbody>
              {samples.slice(-300).map((s, i) => (
                <tr key={i}><td>{new Date(s.at).toLocaleTimeString()}</td><td>{s.run}</td><td>{s[metric] ?? "-"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : n === 0 ? (
        <p className="muted small">아직 데이터가 없습니다.</p>
      ) : (
        <>
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${props.title} 추이, 최신 ${latest ?? "-"} ${props.unit}`}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
                <text x={PAD.l - 6} y={y(t) + 5} textAnchor="end" fontSize="15" fill="var(--ink-2)">
                  {Math.round(t)}
                </text>
              </g>
            ))}
            <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} stroke="var(--axis)" strokeWidth={1} />
            <text x={PAD.l} y={H - 8} fontSize="15" fill="var(--ink-2)">{new Date(samples[0].at).toLocaleTimeString()}</text>
            <text x={W - PAD.r} y={H - 8} fontSize="15" fill="var(--ink-2)" textAnchor="end">
              {new Date(samples[n - 1].at).toLocaleTimeString()}
            </text>
            <path d={path} fill="none" stroke={props.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {hover != null && (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={y(0)} stroke="var(--axis)" strokeWidth={1} />
                {hv != null && <circle cx={x(hover)} cy={y(hv)} r={4} fill={props.color} stroke="var(--surface)" strokeWidth={2} />}
              </g>
            )}
          </svg>
          {hover != null && (
            <div className="tooltip" style={{ left: `${(x(hover) / W) * 100}%`, top: 24, transform: "translateX(-50%)" }}>
              <b>{hv != null ? `${hv.toFixed(1)} ${props.unit}` : "-"}</b>{" "}
              <span className="muted">
                {new Date(samples[hover].at).toLocaleTimeString()} · {samples[hover].run}회차
              </span>
            </div>
          )}
        </>
      )}
    </figure>
  );
}
