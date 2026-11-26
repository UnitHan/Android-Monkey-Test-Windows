import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, type PackageItem, type SessionCreate } from "./api/client";
import {
  TERMINAL, useCreateAndStart, useDevices, useHealth, usePackages, usePresets, useSession, useSessionStream,
  useSessions, useStopSession, refreshAppInfo,
} from "./api/hooks";
import { ConnectionWizard, type Connection } from "./components/ConnectionWizard";
import { ConsolePanel } from "./components/ConsolePanel";
import { PerformanceWorkspace } from "./components/PerformanceWorkspace";
import { ResultsWorkspace } from "./components/ResultsWorkspace";
import { HtmlReportWorkspace } from "./components/HtmlReportWorkspace";
import { ReportNotebook } from "./components/ReportNotebook";
import {
  TestSettings, type DeviceStatus,
} from "./components/TestSettings";
import {
  DEFAULT_FIELDS, effectiveConfig, overridesFor, type CustomFields, type PresetChoice,
} from "./components/presetConfig";
import { Button, MessageBox, Progressbar, Toplevel } from "./components/tk";
import { GooglePlaySettings } from "./components/GooglePlaySettings";
import { RebootDialog } from "./components/RebootDialog";
import { usePlayAuthStatus } from "./api/playAuthHooks";
import { WorkspaceTabs, type Workspace } from "./components/WorkspaceTabs";

type Msg = { title: string; message: string; kind: "info" | "error" };

const errMsg = (e: unknown) =>
  e instanceof ApiError ? `${e.detail}\n\n(${e.code}, request_id: ${e.requestId ?? "-"})` : String(e);

/** UI-only state lives here; server state lives in TanStack Query (api/hooks.ts). */
export function App() {
  const qc = useQueryClient();
  const [connection, setConnection] = useState<Connection | null>(null);
  const [appName, setAppName] = useState<string | null>(null);
  const setApp = (item: PackageItem | null) => setAppName(item?.name ?? null);
  const [preset, setPreset] = useState<PresetChoice>("smoke");
  const [fields, setFields] = useState<CustomFields>(DEFAULT_FIELDS);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab] = useState<Workspace>("main");
  const selectWorkspace = (tab: Workspace) => {
    if (tab === "console") setConsoleOpen(true);
    setWorkspaceTab(tab);
  };
  const [exporting, setExporting] = useState(false);
  const [msg, setMsg] = useState<Msg | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [rebootTarget, setRebootTarget] = useState<string | null>(null);

  const health = useHealth();
  const deployment = useQuery({ queryKey: ["deployment-settings"], queryFn: api.deploymentStatus,
    enabled: !!health.data, retry: false });
  useEffect(() => {
    if (deployment.data?.available && !deployment.data.configured) setSettingsOpen(true);
  }, [deployment.data?.available, deployment.data?.configured]);
  usePlayAuthStatus(!!health.data);
  const devices = useDevices();
  const presets = usePresets();
  const sessions = useSessions();
  const packages = usePackages(connection?.serial ?? null, "", false);
  const app = appName ? packages.data?.items.find((item) => item.name === appName)
    ?? { name: appName, display_name: appName } : null;
  const session = useSession(sessionId);
  const s = session.data;
  useSessionStream(sessionId, s?.state);
  const exportExcel = async () => {
    if (!s || exporting) return;
    setExporting(true);
    try {
      const saved = await api.exportExcel(s.id);
      setMsg({ title: "엑셀 저장 완료", kind: "info", message: `엑셀 보고서를 저장했습니다.\n\n${saved.path}` });
    } catch (e) {
      setMsg({ title: "엑셀 저장 실패", kind: "error", message: errMsg(e) });
    } finally { setExporting(false); }
  };
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
  if (!connection) return <>
    <ConnectionWizard onConnected={setConnection} />
    {!settingsOpen && <Button style={{ position: "fixed", right: 12, top: 12, zIndex: 1000 }} onClick={() => setSettingsOpen(true)}>설정</Button>}
    {settingsOpen && <GooglePlaySettings onClose={() => setSettingsOpen(false)} />}
  </>;

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
    if (!cfg?.valid || !app) return;
    const body: SessionCreate = {
      device_serial: connection.serial,
      package: app.name,
      preset_id: preset,
      overrides: overridesFor(cfg),
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
      <WorkspaceTabs active={workspaceTab} onSelect={selectWorkspace} onSettings={() => setSettingsOpen(true)} />
      <div className="workspace-panel main-content" role="tabpanel" id="workspace-main"
        aria-labelledby="workspace-tab-main" hidden={workspaceTab !== "main"}>
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
          onReboot={() => setRebootTarget(connection.serial)}
          onDisconnect={() =>
            window.confirm("무선 연결을 종료하시겠습니까?") &&
            action("무선 연결 종료", () => api.disconnect(connection.serial)).then(() => setConnection(null))
          }
          onLaunch={() => app && action("앱 실행", () => api.launch(connection.serial, app.name))}
          onRefresh={() => void refreshAppInfo(qc, connection.serial, app?.name)}
          onShowPerf={() => selectWorkspace("performance")}
          onShowReport={() => selectWorkspace("report")}
          onExportExcel={() => void exportExcel()}
          exporting={exporting}
          onToggleConsole={() => selectWorkspace("console")}
        />
        <ReportNotebook session={s} presetName={presetName} history={sessions.data ?? []} onPickHistory={setSessionId}
          onDeleteHistory={id => { if (sessionId === id) setSessionId(null); }} />
      </div>
      <div className="workspace-panel console-workspace" role="tabpanel" id="workspace-console"
        aria-labelledby="workspace-tab-console" hidden={workspaceTab !== "console"}>
        {consoleOpen && <ConsolePanel sessionId={sessionId} active={workspaceTab === "console"}
          onBack={() => selectWorkspace("main")} />}
      </div>
      <div className="workspace-panel dashboard-workspace" role="tabpanel" id="workspace-performance" tabIndex={0}
        aria-labelledby="workspace-tab-performance" hidden={workspaceTab !== "performance"}>
        {workspaceTab === "performance" && <PerformanceWorkspace session={s} />}
      </div>
      <div className="workspace-panel dashboard-workspace" role="tabpanel" id="workspace-results" tabIndex={0}
        aria-labelledby="workspace-tab-results" hidden={workspaceTab !== "results"}>
        {workspaceTab === "results" && <ResultsWorkspace session={s} history={sessions.data ?? []} onSelect={setSessionId} />}
      </div>
      <div className="workspace-panel report-workspace" role="tabpanel" id="workspace-report"
        aria-labelledby="workspace-tab-report" hidden={workspaceTab !== "report"}>
        {workspaceTab === "report" && <HtmlReportWorkspace session={s} />}
      </div>
      {msg && <MessageBox {...msg} onClose={() => setMsg(null)} />}
      {rebootTarget && <RebootDialog serial={rebootTarget} onClose={() => setRebootTarget(null)} onDone={() => {
        setRebootTarget(null);
        setMsg({ title: "폰 재부팅", kind: "info", message: "재부팅 명령을 전송했습니다." });
      }} />}
      {settingsOpen && <GooglePlaySettings onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
