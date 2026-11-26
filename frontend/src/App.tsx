import { useEffect, useState } from "react";
import { DevicePanel } from "./components/DevicePanel";
import { HealthBadge } from "./components/HealthBadge";
import { LogsView, type LogFilter } from "./components/LogsView";
import { NewSessionForm } from "./components/NewSessionForm";
import { SessionDetail } from "./components/SessionDetail";
import { SessionList } from "./components/SessionList";

type Tab = "test" | "logs";

function sessionFromHash(): string | null {
  const m = /^#\/sessions\/(s_[A-Za-z0-9_]+)$/.exec(window.location.hash);
  return m ? m[1] : null;
}

/** UI-only state lives here (selection, tab, log filter). Server state lives in TanStack Query. */
export function App() {
  const [tab, setTab] = useState<Tab>("test");
  const [serial, setSerial] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(() => sessionFromHash());

  useEffect(() => {
    const next = sessionId ? `#/sessions/${sessionId}` : "";
    if (window.location.hash !== next) history.replaceState(null, "", next || window.location.pathname);
  }, [sessionId]);
  const [logFilter, setLogFilter] = useState<LogFilter>({ level: "", source: "", session_id: "", request_id: "" });

  const showLogs = (f: Partial<LogFilter>) => {
    setLogFilter({ level: "", source: "", session_id: "", request_id: "", ...f });
    setTab("logs");
  };

  return (
    <>
      <header className="top">
        <h1>Monkey Test</h1>
        <HealthBadge />
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "test"} onClick={() => setTab("test")}>테스트</button>
          <button role="tab" aria-selected={tab === "logs"} onClick={() => setTab("logs")}>API 로그</button>
        </nav>
      </header>
      {tab === "test" ? (
        <main className="layout">
          <div className="col">
            <DevicePanel selected={serial} onSelect={setSerial} onShowLogs={showLogs} />
            <NewSessionForm serial={serial} onStarted={setSessionId} onShowLogs={showLogs} />
            <SessionList selectedId={sessionId} onSelect={setSessionId} />
          </div>
          <div className="col">
            {sessionId ? (
              <SessionDetail id={sessionId} onShowLogs={showLogs} onDeleted={() => setSessionId(null)} />
            ) : (
              <div className="card muted">디바이스와 앱을 선택해 테스트를 시작하거나, 세션을 선택하세요.</div>
            )}
          </div>
        </main>
      ) : (
        <main style={{ padding: 16, maxWidth: 1400, margin: "0 auto" }}>
          <LogsView filter={logFilter} onChange={setLogFilter} />
        </main>
      )}
    </>
  );
}
