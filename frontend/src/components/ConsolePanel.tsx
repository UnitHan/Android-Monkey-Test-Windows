/** v3 "콘솔 로그" side panel (black console), now fed by the API log store (/api/v1/logs). */
import { useEffect, useRef, useState } from "react";
import { api, type LogRecord } from "../api/client";
import { Button, LabelFrame } from "./tk";

const MAX_LINES = 3000;

function fmt(r: LogRecord): string {
  const t = new Date(r.at).toLocaleTimeString("en-GB", { hour12: false });
  const d = r.data && Object.keys(r.data).length ? ` ${JSON.stringify(r.data)}` : "";
  const ids = [r.request_id && `rid=${r.request_id}`, r.session_id && `sid=${r.session_id}`].filter(Boolean).join(" ");
  return `${t} - ${r.level} - [${r.source}] ${r.message}${ids ? ` (${ids})` : ""}${d}`;
}

export function ConsolePanel(props: { sessionId: string | null; onHide: () => void }) {
  const [lines, setLines] = useState<LogRecord[]>([]);
  const [sessionOnly, setSessionOnly] = useState(false);
  const [follow, setFollow] = useState(true);
  const cursor = useRef(0);
  const box = useRef<HTMLDivElement>(null);
  const sid = sessionOnly ? props.sessionId : null;

  useEffect(() => {
    let alive = true;
    cursor.current = 0;
    setLines([]);
    const poll = async () => {
      try {
        const res = await api.logs({ session_id: sid ?? undefined, level: "INFO", since_seq: cursor.current, limit: 1000 });
        if (!alive || res.items.length === 0) return;
        cursor.current = res.last_seq;
        // the UI's own polling requests are noise here; keep HTTP lines only when something went wrong
        const useful = res.items.filter((r) => r.source !== "http" || r.level !== "INFO");
        setLines((prev) => [...prev, ...useful].slice(-MAX_LINES));
      } catch {
        /* API not reachable yet: next poll retries; status is shown in the main window */
      }
    };
    void poll();
    const timer = setInterval(poll, 1500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [sid]);

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines, follow]);

  return (
    <div className="console">
      <LabelFrame text="콘솔 로그">
        <div className="row" style={{ marginBottom: 4, flexWrap: "wrap" }}>
          <Button onClick={() => setSessionOnly((v) => !v)} disabled={!props.sessionId}>
            {sessionOnly ? "전체 로그" : "현재 세션만"}
          </Button>
          <Button onClick={() => setLines([])}>지우기</Button>
          <Button onClick={() => { setFollow(true); box.current?.scrollTo(0, box.current.scrollHeight); }}>맨 아래로</Button>
          <span className="grow" />
          <Button onClick={props.onHide}>숨기기</Button>
        </div>
        <div
          ref={box}
          className="console-text"
          onScroll={(e) => {
            const el = e.currentTarget;
            setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 30);
          }}
        >
          {lines.length === 0 && <div className="INFO">INFO - 표시할 로그가 없습니다. 테스트를 실행하면 실시간 로그가 여기에 표시됩니다.</div>}
          {lines.map((r) => (
            <div key={r.seq} className={r.level}>{fmt(r)}</div>
          ))}
        </div>
      </LabelFrame>
    </div>
  );
}
