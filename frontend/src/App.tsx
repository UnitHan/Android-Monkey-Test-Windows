import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, type PackageItem, type SessionCreate } from "./api/client";
import {
  TERMINAL, useCreateAndStart, useDevices, useHealth, usePackages, usePresets, useSession, useSessionStream,
  useSessions, useStopSession,
} from "./api/hooks";
import { ConnectionWizard, type Connection } from "./components/ConnectionWizard";
import { ConsolePanel } from "./components/ConsolePanel";
import { PerfGraphDialog } from "./components/PerfGraphDialog";
import { ReportNotebook } from "./components/ReportNotebook";
import {
  TestSettings, effectiveConfig, type CustomFields, type DeviceStatus, type PresetChoice,
} from "./components/TestSettings";
import { MessageBox, Progressbar, Toplevel } from "./components/tk";

type Msg = { title: string; message: string; kind: "info" | "error" };

const errMsg = (e: unknown) =>
  e instanceof ApiError ? `${e.detail}\n\n(${e.code}, request_id: ${e.requestId ?? "-"})` : String(e);

/** UI-only state lives here; server state lives in TanStack Query (api/hooks.ts). */
export function App() {
  const qc = useQueryClient();
  const [connection, setConnection] = useState<Connection | null>(null);
  const [app, setApp] = useState<PackageItem | null>(null);
  const [preset, setPreset] = useState<PresetChoice>("quick");
  const [fields, setFields] = useState<CustomFields>({ events: "3000", repeats: "5", throttle: "200", seed: "1000" });
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [perfOpen, setPerfOpen] = useState(false);
  const [msg, setMsg] = useState<Msg | null>(null);

  const health = useHealth();
  const devices = useDevices();
  const presets = usePresets();
  const sessions = useSessions();
  const packages = usePackages(connection?.serial ?? null, "", false);
  const session = useSession(sessionId);
  const s = session.data;
  useSessionStream(sessionId, s?.state);
  const start = useCreateAndStart();
  const stop = useStopSession();

  // completion message box (v3 showed one when a test finished)
  const prevState = useRef<string | undefined>(undefined);
  useEffect(() => {
    const before = prevState.current;
    prevState.current = s?.state;
    if (!s || !before || TERMINAL.has(before) || !TERMINAL.has(s.state)) return;
    const crashes = s.issue_counts.crash + s.issue_counts.native_crash;
    if (s.state === "completed") {
      setMsg({ title: "테스트 완료", kind: "info", message: `테스트가 성공적으로 완료되었습니다.\n\n테스트 완료: ${crashes}회 크래시, ${s.issue_counts.anr}회 ANR` });
    } else if (s.state === "failed") {
      setMsg({ title: "테스트 실패", kind: "error", message: `테스트가 실패했습니다.\n\n${s.error ?? ""}` });
    }
  }, [s]);

  if (!health.data) {
    return (
      <Toplevel title="Monkey 테스트 자동화" width={320} opaque>
        <div style={{ textAlign: "center", padding: "12px 0" }}>테스트 서버 시작 중...</div>
        <Progressbar value={0} indeterminate />
      </Toplevel>
    );
  }
  if (!connection) return <ConnectionWizard onConnected={setConnection} />;

  const device = devices.data?.find((d) => d.serial === connection.serial);
  const deviceStatus: DeviceStatus = devices.isLoading ? "checking" : device?.state === "device" ? "connected" : "lost";
  const packageStatus = packages.isFetching
    ? { text: "🔄 패키지 목록 새로고침 중...", color: "blue" }
    : packages.error
      ? { text: "패키지 목록 조회 실패", color: "red" }
      : { text: packages.data ? `${packages.data.total}개 앱` : "", color: "gray" };
  const presetName = presets.data?.find((p) => p.id === s?.config.preset_id)?.name ?? s?.config.preset_id ?? "";

  const onStart = () => {
    const cfg = effectiveConfig(preset, presets.data, fields);
    if (!cfg || !app) return;
    const body: SessionCreate = {
      device_serial: connection.serial,
      package: app.name,
      preset_id: preset,
      overrides: cfg.editable
        ? { events: cfg.events, repeats: cfg.repeats, throttle_ms: cfg.throttle_ms, seed: cfg.seed }
        : null,
    };
    start.mutate(body, {
      onSuccess: (created) => setSessionId(created.id),
      onError: (e) => setMsg({ title: "테스트 오류", kind: "error", message: `테스트 시작 중 오류가 발생했습니다:\n${errMsg(e)}` }),
    });
  };

  const action = (title: string, fn: () => Promise<unknown>, ok?: string) =>
    fn().then(
      () => ok && setMsg({ title, kind: "info", message: ok }),
      (e) => setMsg({ title, kind: "error", message: errMsg(e) }),
    );

  return (
    <div className="app-shell">
      <div className="main-content">
        <TestSettings
          connection={connection}
          deviceStatus={deviceStatus}
          app={app}
          onApp={setApp}
          preset={preset}
          onPreset={setPreset}
          fields={fields}
          onFields={setFields}
          session={s}
          aiAdvisor={!!health.data?.ai_advisor}
          busy={start.isPending}
          packageStatus={packageStatus}
          onStart={onStart}
          onStop={() => s && stop.mutate(s.id, { onError: (e) => setMsg({ title: "테스트 중지", kind: "error", message: errMsg(e) }) })}
          onReboot={() =>
            window.confirm("폰을 재부팅하시겠습니까?") &&
            action("폰 재부팅", () => api.reboot(connection.serial), "재부팅 명령을 전송했습니다.")
          }
          onDisconnect={() =>
            window.confirm("무선 연결을 종료하시겠습니까?") &&
            action("무선 연결 종료", () => api.disconnect(connection.serial)).then(() => setConnection(null))
          }
          onLaunch={() => app && action("앱 실행", () => api.launch(connection.serial, app.name))}
          onRefresh={() => void qc.invalidateQueries({ queryKey: ["packages"] })}
          onShowPerf={() => setPerfOpen(true)}
          onToggleConsole={() => setConsoleOpen((v) => !v)}
        />
        <ReportNotebook session={s} presetName={presetName} history={sessions.data ?? []} onPickHistory={setSessionId} />
      </div>
      {consoleOpen && <ConsolePanel sessionId={sessionId} onHide={() => setConsoleOpen(false)} />}
      {perfOpen && s && <PerfGraphDialog session={s} onClose={() => setPerfOpen(false)} />}
      {msg && <MessageBox {...msg} onClose={() => setMsg(null)} />}
    </div>
  );
}
