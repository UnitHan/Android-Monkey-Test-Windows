import { ApiError } from "../api/client";
import type { LogFilter } from "./LogsView";

export type ShowLogs = (f: Partial<LogFilter>) => void;

/** Error display that always surfaces the server request_id and links to its API logs. */
export function ErrorNote({ error, onShowLogs }: { error: unknown; onShowLogs?: ShowLogs }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  return (
    <div className="error" role="alert">
      <div>{e ? `${e.detail}` : String(error)}</div>
      {e && (
        <div className="row small" style={{ marginTop: 4 }}>
          <span className="mono">{e.code} · HTTP {e.status}</span>
          {e.requestId && (
            <>
              <span className="mono">request_id {e.requestId}</span>
              {onShowLogs && (
                <button className="small" onClick={() => onShowLogs({ request_id: e.requestId! })}>
                  로그 보기
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const STATE_CLASS: Record<string, string> = {
  completed: "good", running: "warn", preparing: "warn", stopping: "warn", failed: "bad", cancelled: "",
  created: "", device: "good", offline: "bad", unauthorized: "bad",
};
const STATE_LABEL: Record<string, string> = {
  created: "생성됨", preparing: "준비 중", running: "실행 중", stopping: "중지 중",
  completed: "완료", failed: "실패", cancelled: "취소됨",
};

export function StateBadge({ state }: { state: string }) {
  return <span className={`badge ${STATE_CLASS[state] ?? ""}`}>{STATE_LABEL[state] ?? state}</span>;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}시간 ${m}분` : m ? `${m}분 ${r}초` : `${r}초`;
}

export const fmtTime = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : "-");
