/** v3 "테스트 설정" frame: app selection, app info, package search, presets, controls, progress. */
import { useState } from "react";
import { type PackageItem, type Session } from "../api/client";
import { TERMINAL, usePresets } from "../api/hooks";
import { AppSelectDialog, appLabel } from "./AppSelectDialog";
import { AppVersions } from "./AppVersions";
import { AppIcon } from "./AppIcon";
import type { Connection } from "./ConnectionWizard";
import { PresetPanel } from "./PresetPanel";
import { effectiveConfig, type CustomFields, type PresetChoice } from "./presetConfig";
import { Button, Entry, LabelFrame, Progressbar } from "./tk";

export type DeviceStatus = "checking" | "connected" | "lost";

export function TestSettings(props: {
  connection: Connection;
  deviceStatus: DeviceStatus;
  app: PackageItem | null;
  onApp: (p: PackageItem | null) => void;
  preset: PresetChoice;
  onPreset: (p: PresetChoice) => void;
  fields: CustomFields;
  onFields: (f: CustomFields) => void;
  session: Session | undefined;
  aiAdvisor: boolean;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  onReboot: () => void;
  onDisconnect: () => void;
  onShowPerf: () => void;
  onShowReport: () => void;
  onExportExcel: () => void;
  exporting: boolean;
  onToggleConsole: () => void;
  onLaunch: () => void;
  onRefresh: () => void;
  packageStatus: { text: string; color: string };
}) {
  const [dialog, setDialog] = useState<{ query: string } | null>(null);
  const [search, setSearch] = useState("");
  const presets = usePresets();
  const serial = props.connection.serial;

  const cfg = effectiveConfig(props.preset, presets.data, props.fields);

  const s = props.session;
  const running = !!s && !TERMINAL.has(s.state) && s.state !== "created";
  const finished = !!s && TERMINAL.has(s.state);
  const p = s?.progress;
  const overall = p && p.total_runs ? ((p.current_run - 1 + p.run_percent / 100) / p.total_runs) * 100 : 0;
  const progressText = !s
    ? "테스트 대기 중..."
    : s.state === "preparing"
      ? "테스트 준비 중..."
      : running && p
        ? `테스트 진행 중: ${p.current_run}/${p.total_runs}회차 (${p.run_percent}%)`
        : s.state === "completed" ? "테스트 완료!" : s.state === "failed" ? "테스트 실패" : s.state === "cancelled" ? "테스트 중지됨" : "테스트 대기 중...";

  const status = {
    checking: { text: "🔌 연결 확인 중...", color: "orange" },
    connected: { text: `✅ 연결됨 (${props.connection.wireless ? `무선 (${serial})` : "USB"})`, color: "green" },
    lost: { text: "⚠️ 연결 끊어짐", color: "red" },
  }[props.deviceStatus];

  const blocked = running
    ? null
    : props.deviceStatus !== "connected"
      ? "디바이스 연결을 확인하세요"
      : !props.app
        ? "테스트할 앱을 선택하세요"
        : !cfg?.valid
          ? "테스트 프리셋 설정값을 확인하세요"
          : null;

  return (
    <LabelFrame text="테스트 설정" style={{ padding: "6px 8px" }}>
      <div className="row" style={{ padding: "3px 0" }}>
        <span style={{ paddingLeft: 5 }}>테스트할 앱 선택:</span>
        {props.packageStatus.text && <span className={`c-${props.packageStatus.color}`}>{props.packageStatus.text}</span>}
        <Button sunken className="grow" style={{ maxWidth: 420 }} onClick={() => setDialog({ query: "" })} disabled={running}>
          {props.app ? appLabel(props.app) : "테스트할 앱을 선택하세요"}
        </Button>
        <Button onClick={props.onRefresh}>새로고침</Button>
        <span className="grow" />
        <span className={`c-${status.color}`} style={{ paddingRight: 5 }}>{status.text}</span>
      </div>

      <div className="row" style={{ padding: "3px 5px" }}>
        <AppIcon serial={serial} pkg={props.app?.name} />
        <div className="col app-identity-info">
          <span className="bold">{props.app ? props.app.display_name : "앱을 선택하면 정보가 표시됩니다"}</span>
          {props.app && <span className="small c-gray">{props.app.name}</span>}
          {props.app && <AppVersions serial={serial} pkg={props.app.name} />}
        </div>
      </div>

      <div className="row" style={{ padding: "3px 0" }}>
        <span style={{ paddingLeft: 5 }}>앱 검색:</span>
        <Entry
          className="grow"
          aria-label="앱 검색"
          placeholder="앱 이름 · 패키지명 · 초성"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) setDialog({ query: search });
          }}
          disabled={running}
        />
        <Button onClick={() => setDialog({ query: search })} disabled={running}>검색 &amp; 선택</Button>
        <Button onClick={props.onLaunch} disabled={!props.app}>앱 실행</Button>
      </div>

      <PresetPanel
        choice={props.preset}
        onChoice={props.onPreset}
        fields={props.fields}
        onFields={props.onFields}
        aiAdvisor={props.aiAdvisor}
      />

      <div className="row test-actions" style={{ padding: "6px 0 2px" }}>
        <Button onClick={props.onStart} disabled={running || props.busy || !!blocked} title={blocked ?? undefined}>
          {running ? "테스트 진행 중..." : "테스트 시작"}
        </Button>
        {blocked && <span className="small c-gray">{blocked}</span>}
        {running && <Button onClick={props.onStop} disabled={s?.state === "stopping"}>테스트 중지</Button>}
        <div className="col" style={{ width: 220, marginLeft: 20, gap: 2 }}>
          <span className="small" style={{ textAlign: "center" }}>{progressText}</span>
          <Progressbar value={finished && s?.state === "completed" ? 100 : overall} indeterminate={s?.state === "preparing"} />
        </div>
        <span className="grow" />
        <Button onClick={props.onReboot} disabled={running}>폰 재부팅</Button>
        {props.connection.wireless && <Button onClick={props.onDisconnect} disabled={running}>무선 연결 종료</Button>}
        <Button onClick={props.onShowReport} disabled={!finished}>HTML 보기</Button>
        <Button onClick={props.onExportExcel} disabled={!finished || props.exporting}>{props.exporting ? "저장 중..." : "엑셀 내보내기"}</Button>
        <Button onClick={props.onShowPerf} disabled={!s || s.state === "created"}>성능그래프 보기</Button>
        <Button onClick={props.onToggleConsole}>콘솔 로그</Button>
      </div>

      {dialog && (
        <AppSelectDialog
          serial={serial}
          initialQuery={dialog.query}
          current={props.app}
          onSelect={props.onApp}
          onClose={() => setDialog(null)}
        />
      )}
    </LabelFrame>
  );
}
