import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { keys } from "../api/hooks";
import { ErrorNote } from "./common";

export type LogFilter = { level: string; source: string; session_id: string; request_id: string };

const LEVEL_CLASS: Record<string, string> = { ERROR: "bad", WARNING: "warn", INFO: "", DEBUG: "" };

/** API log explorer: every HTTP request, ADB call and session event, filterable by request/session id. */
export function LogsView({ filter, onChange }: { filter: LogFilter; onChange: (f: LogFilter) => void }) {
  const q = { ...filter, limit: 500 };
  const logs = useQuery({ queryKey: keys.logs(q), queryFn: () => api.logs(q), refetchInterval: 3_000 });
  const set = (k: keyof LogFilter) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...filter, [k]: e.target.value });

  return (
    <section className="card">
      <h2>API 로그</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <select aria-label="레벨" value={filter.level} onChange={set("level")}>
          <option value="">모든 레벨</option>
          {["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => <option key={l} value={l}>{l}+</option>)}
        </select>
        <select aria-label="소스" value={filter.source} onChange={set("source")}>
          <option value="">모든 소스</option>
          {["http", "adb", "session", "app"].map((s) => <option key={s}>{s}</option>)}
        </select>
        <input aria-label="session_id" placeholder="session_id" value={filter.session_id} onChange={set("session_id")} />
        <input aria-label="request_id" placeholder="request_id" value={filter.request_id} onChange={set("request_id")} />
        <button onClick={() => onChange({ level: "", source: "", session_id: "", request_id: "" })}>초기화</button>
      </div>
      <ErrorNote error={logs.error} />
      <div className="scroll">
        <table className="mono">
          <thead><tr><th>#</th><th>시각</th><th>레벨</th><th>소스</th><th>메시지</th><th>request</th><th>session</th><th>data</th></tr></thead>
          <tbody>
            {[...(logs.data?.items ?? [])].reverse().map((r) => (
              <tr key={r.seq}>
                <td>{r.seq}</td>
                <td>{new Date(r.at).toLocaleTimeString()}</td>
                <td><span className={`badge ${LEVEL_CLASS[r.level]}`}>{r.level}</span></td>
                <td>{r.source}</td>
                <td style={{ whiteSpace: "normal", minWidth: 220 }}>{r.message}</td>
                <td>{r.request_id && <button className="small" onClick={() => onChange({ ...filter, request_id: r.request_id! })}>{r.request_id}</button>}</td>
                <td>{r.session_id && <button className="small" onClick={() => onChange({ ...filter, session_id: r.session_id! })}>{r.session_id}</button>}</td>
                <td style={{ whiteSpace: "pre-wrap", maxWidth: 480 }}>{Object.keys(r.data).length ? JSON.stringify(r.data) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
