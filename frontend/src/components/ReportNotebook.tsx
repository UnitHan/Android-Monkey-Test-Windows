/** v3 report notebook: 요약 / 결과 상세 / 이슈 요약 및 권고사항. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Issue, type Session } from "../api/client";
import { TERMINAL, useIssues } from "../api/hooks";
import { Notebook } from "./tk";

type Tab = "summary" | "detail" | "issues";

const pad = (n: number) => String(n).padStart(2, "0");
const ymdhm = (iso: string) => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const hm = (iso: string) => {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
function execTime(s: Session): string {
  if (!s.started_at) return "00분";
  const end = s.ended_at ? new Date(s.ended_at) : new Date();
  const sec = Math.max(0, Math.round((end.getTime() - new Date(s.started_at).getTime()) / 1000));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h ? `${pad(h)}시간 ${pad(m)}분` : `${pad(m)}분`;
}
function runTime(sec: number): string {
  const s = Math.round(sec), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}시간 ${m}분 ${r}초` : m ? `${m}분 ${r}초` : `${r}초`;
}

export function summaryText(s: Session, presetName: string): string {
  const crashes = s.issue_counts.crash + s.issue_counts.native_crash;
  const running = !TERMINAL.has(s.state);
  const result = running ? "테스트 진행 중..." : s.state === "failed" ? `테스트 실패 (${s.error ?? "-"})` : `${crashes}회 Crash, ${s.issue_counts.anr}회 ANR`;
  const period = s.started_at ? `${ymdhm(s.started_at)}${s.ended_at ? ` ~ ${hm(s.ended_at)}` : ""}` : "-";
  const device = s.device ? `${s.device.model} (Android ${s.device.android_version})` : s.config.device_serial;
  return `=== Monkey 테스트 요약 ===
• 테스트 대상: ${s.config.package}
• 테스트 도구: Android Monkey
• 테스트 기간: ${period}
• 테스트 설정: ${presetName} (${s.config.events} events x ${s.config.repeats}회)
• 총 이벤트 수: ${s.config.events * s.config.repeats}
• 디바이스: ${device}
• 연결 방식: ${s.device?.connection === "wifi" ? "Wi-Fi" : "USB"}
• 결과 요약: ${result}
• 수행 시간: ${execTime(s)}
`;
}

const mark = (n: number) => (n > 0 ? `❌ ${n}` : "✅ 0");
const BAD_END: Record<string, string> = { aborted: "중단", failed_to_start: "시작 실패", device_lost: "연결 끊김" };

export function ReportNotebook(props: {
  session: Session | undefined;
  presetName: string;
  history: Session[];
  onPickHistory: (id: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("summary");
  const [row, setRow] = useState<number | null>(null);
  const s = props.session;
  const issues = useIssues(s?.id ?? null);
  const report = useQuery({
    queryKey: ["report", s?.id, s?.state],
    queryFn: () => api.report(s!.id),
    enabled: !!s && TERMINAL.has(s.state),
  });
  const suggestions: string[] = report.data?.suggestions ?? [];

  const historySelect = props.history.length > 0 && (
    <label className="small row" style={{ paddingBottom: 2 }}>
      이전 결과:
      <select className="tk-entry" style={{ height: 22, padding: 0, maxWidth: 260 }} value={s?.id ?? ""} onChange={(e) => props.onPickHistory(e.target.value)}>
        {!s && <option value="">선택...</option>}
        {props.history.map((h) => (
          <option key={h.id} value={h.id}>{h.config.package} · {ymdhm(h.created_at)}</option>
        ))}
      </select>
    </label>
  );

  return (
    <Notebook
      style={{ flex: 1, minHeight: 0 }}
      tabs={[
        { id: "summary", label: "요약" },
        { id: "detail", label: "결과 상세" },
        { id: "issues", label: "이슈 요약 및 권고사항" },
      ]}
      active={tab}
      onSelect={setTab}
      extra={historySelect}
    >
      {tab === "summary" && <div className="tk-text">{s ? summaryText(s, props.presetName) : ""}</div>}
      {tab === "detail" && (
        <div className="tk-tree">
          <table>
            <thead>
              <tr>
                <th style={{ width: 50 }}>반복</th><th>실행 시간</th><th style={{ width: 60 }}>Seed</th><th>이벤트 수</th>
                <th style={{ width: 60 }}>Crash</th><th style={{ width: 60 }}>ANR</th><th style={{ width: 80 }}>Timeout</th>
                <th>메모리 피크</th><th style={{ width: 80 }}>CPU 피크</th>
              </tr>
            </thead>
            <tbody>
              {s?.runs.map((r) => (
                <tr key={r.run} aria-selected={row === r.run} onClick={() => setRow(r.run)}>
                  <td>{r.run}회차</td>
                  <td>{runTime(r.duration_s)}</td>
                  <td>{r.seed}</td>
                  <td>{r.events_sent.toLocaleString()}</td>
                  <td>{mark(r.crashes)}</td>
                  <td>{mark(r.anrs)}</td>
                  <td>{BAD_END[r.end_reason] ? `❌ ${BAD_END[r.end_reason]}` : "✅ 0"}</td>
                  <td>{r.mem_peak_mb != null ? `${Math.round(r.mem_peak_mb)}MB` : "N/A"}</td>
                  <td>{r.cpu_peak_percent != null ? `${Math.round(r.cpu_peak_percent)}%` : "N/A"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "issues" && (
        <div className="tk-text">
          {suggestions.map((x, i) => <div key={i}>• {x}</div>)}
          {s && !TERMINAL.has(s.state) && <div className="c-gray">테스트 완료 후 권고사항이 표시됩니다.</div>}
          {(issues.data?.length ?? 0) > 0 && <div className="bold" style={{ marginTop: 8 }}>감지된 이슈 ({issues.data!.length})</div>}
          {issues.data?.map((i: Issue) => (
            <details key={i.id} className="issue">
              <summary>[{i.run}회차] {i.kind === "anr" ? "ANR" : i.kind === "native_crash" ? "Native Crash" : "Crash"}: {i.summary}</summary>
              <pre>{i.lines.join("\n")}</pre>
            </details>
          ))}
        </div>
      )}
    </Notebook>
  );
}
