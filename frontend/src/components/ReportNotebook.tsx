/** v3 report notebook: 요약 / 결과 상세 / 이슈 요약 및 권고사항. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Issue, type Session } from "../api/client";
import { TERMINAL, useIssues } from "../api/hooks";
import { Button, Notebook } from "./tk";
import { DeleteHistoryDialog } from "./DeleteHistoryDialog";
import { ResourceAssessment } from "./ResourceAssessment";
import { AIResult } from "./AIPerformance";

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
• 실제 누적 이벤트 수: ${s.runs.reduce((total, run) => total + run.events_sent, 0)}
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
  onDeleteHistory: (id: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("summary");
  const [row, setRow] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null);
  const s = props.session;
  const issues = useIssues(s?.id ?? null);
  const report = useQuery({
    queryKey: ["report", s?.id, s?.state],
    queryFn: () => api.report(s!.id),
    enabled: !!s && TERMINAL.has(s.state),
  });

  const historySelect = props.history.length > 0 && (
    <div className="small row" style={{ paddingBottom: 2 }}>
      <label className="row">
      이전 결과:
      <select className="tk-entry" style={{ height: 22, padding: 0, maxWidth: 260 }} value={s?.id ?? ""} onChange={(e) => props.onPickHistory(e.target.value)}>
        {!s && <option value="">선택...</option>}
        {props.history.map((h) => (
          <option key={h.id} value={h.id}>{h.config.package} · {ymdhm(h.created_at)}</option>
        ))}
      </select>
      </label>
      <Button disabled={!s || (!TERMINAL.has(s.state) && s.state !== "created")} onClick={() => s && setDeleteTarget(s)}>
        기록 삭제
      </Button>
    </div>
  );

  return (
    <><Notebook
      style={{ flex: 1, minHeight: 220 }}
      tabs={[
        { id: "summary", label: "요약" },
        { id: "detail", label: "결과 상세" },
        { id: "issues", label: "이슈 요약 및 권고사항" },
      ]}
      active={tab}
      onSelect={setTab}
      extra={historySelect}
    >
      {tab === "summary" && <div className="tk-text" tabIndex={0} aria-label="테스트 요약">{s ? summaryText(s, props.presetName) : ""}
        {report.data?.ai_performance && <div style={{ whiteSpace: "normal" }}><h3>Gemini 성능 판정</h3><AIResult result={report.data.ai_performance} /></div>}
      </div>}
      {tab === "detail" && (
        <div className="tk-tree" tabIndex={0} aria-label="회차별 결과">
          <table>
            <thead>
              <tr>
                <th style={{ width: 50 }}>반복</th><th>실행 / 목표</th><th style={{ width: 60 }}>Seed</th><th>이벤트 수</th>
                <th>추가 실행</th><th style={{ width: 60 }}>Crash</th><th style={{ width: 60 }}>ANR</th><th>종료 사유</th>
                <th>메모리 피크</th><th style={{ width: 80 }}>CPU 피크</th>
              </tr>
            </thead>
            <tbody>
              {s?.runs.map((r) => (
                <tr key={r.run} aria-selected={row === r.run} onClick={() => setRow(r.run)}>
                  <td>{r.run}회차</td>
                  <td title={`준비 ${runTime(r.preparation_duration_s ?? 0)} · 정리 ${runTime(r.cleanup_duration_s ?? 0)} · 전체 ${runTime(r.duration_s)}`}>
                    {runTime(r.execution_duration_s ?? r.duration_s)} / {r.target_duration_s != null ? runTime(r.target_duration_s) : "이벤트 기준"}
                  </td>
                  <td title={r.segments.map((part) => `${part.segment}구간: Seed ${part.seed}, ${part.events_sent} 이벤트`).join("\n")}>{r.seed}</td>
                  <td>{r.events_sent.toLocaleString()}</td>
                  <td>{Math.max(0, r.segments.length - 1)}회</td>
                  <td>{mark(r.crashes)}</td>
                  <td>{mark(r.anrs)}</td>
                  <td>{BAD_END[r.end_reason] ? `❌ ${BAD_END[r.end_reason]}`
                    : r.end_reason === "time_limit" ? (r.target_duration_s != null ? "목표 시간 도달" : "안전 시간 제한")
                    : r.end_reason === "stopped" ? "사용자 중단" : "이벤트 완료"}</td>
                  <td>{r.mem_peak_mb != null ? `${Math.round(r.mem_peak_mb)}MB` : "N/A"}</td>
                  <td>{r.cpu_peak_percent != null ? `${Math.round(r.cpu_peak_percent)}%` : "N/A"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "issues" && (
        <div className="tk-text" tabIndex={0} aria-label="이슈 요약 및 권고사항 내용" style={{ whiteSpace: "normal" }}>
          {report.data && <ResourceAssessment report={report.data} />}
          {report.isFetching && <p role="status">통계와 관측 근거를 계산하는 중...</p>}
          {report.error && <p role="alert">분석 결과를 가져오지 못했습니다: {report.error.message}</p>}
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
      {deleteTarget && <DeleteHistoryDialog session={deleteTarget} onClose={() => setDeleteTarget(null)}
        onDeleted={id => { setDeleteTarget(null); props.onDeleteHistory(id); }} />}
    </>
  );
}
