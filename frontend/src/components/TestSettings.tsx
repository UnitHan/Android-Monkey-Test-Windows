/** v3 "테스트 설정" frame: app selection, app info, package search, presets, controls, progress. */
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type PackageItem, type Preset, type Session } from "../api/client";
import { TERMINAL, usePresets } from "../api/hooks";
import { AppSelectDialog, appLabel } from "./AppSelectDialog";
import type { Connection } from "./ConnectionWizard";
import { Button, Entry, LabelFrame, Progressbar, Radio } from "./tk";

export type PresetChoice = "smoke" | "quick" | "standard" | "deep" | "extreme" | "custom" | "reproduce";
export type CustomFields = { events: string; repeats: string; throttle: string; seed: string };
export type DeviceStatus = "checking" | "connected" | "lost";

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null) return "-";
  const s = Math.round(totalSeconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `약 ${h}시간 ${m}분` : `약 ${m}분`;
}

function presetLabel(p: Preset, totalS: number | undefined): string {
  const seed = p.seed_mode === "fixed" ? `Seed ${p.fixed_seed}` : "Random Seed";
  return `${p.name} - ${p.events}개 이벤트 x ${p.repeats}회 반복 (Throttle: ${p.throttle_ms}ms, ${seed}) → ${formatDuration(totalS)}`;
}

export function effectiveConfig(choice: PresetChoice, presets: Preset[] | undefined, f: CustomFields) {
  const p = presets?.find((x) => x.id === choice);
  if (!p) return null;
  const editable = choice === "custom" || choice === "reproduce";
  const num = (v: string) => (/^\d+$/.test(v.trim()) ? Number(v) : NaN);
  return {
    preset: p,
    editable,
    events: editable ? num(f.events) : p.events,
    repeats: editable ? num(f.repeats) : p.repeats,
    throttle_ms: editable ? num(f.throttle) : p.throttle_ms,
    seed: choice === "reproduce" ? num(f.seed) : null,
    target_minutes_per_run: p.target_minutes_per_run ?? null,
  };
}

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
  onToggleConsole: () => void;
  onLaunch: () => void;
  onRefresh: () => void;
  packageStatus: { text: string; color: string };
}) {
  const [dialog, setDialog] = useState<{ query: string } | null>(null);
  const [search, setSearch] = useState("");
  const presets = usePresets();
  const serial = props.connection.serial;

  const estimates = useQueries({
    queries: (presets.data ?? []).map((p) => ({
      queryKey: ["estimate", p.id],
      queryFn: () =>
        api.estimate({ events: p.events, repeats: p.repeats, throttle_ms: p.throttle_ms, target_minutes_per_run: p.target_minutes_per_run ?? null }),
      staleTime: Infinity,
    })),
  });
  const estOf = (id: string) => estimates[(presets.data ?? []).findIndex((p) => p.id === id)]?.data?.total_s;

  const cfg = effectiveConfig(props.preset, presets.data, props.fields);
  const valid = !!cfg && cfg.events > 0 && cfg.repeats > 0 && cfg.throttle_ms >= 0 && (props.preset !== "reproduce" || (cfg.seed ?? NaN) >= 0);
  const customEstimate = useQuery({
    queryKey: ["estimate", "custom", cfg?.events, cfg?.repeats, cfg?.throttle_ms],
    queryFn: () => api.estimate({ events: cfg!.events, repeats: cfg!.repeats, throttle_ms: cfg!.throttle_ms }),
    enabled: !!cfg?.editable && valid,
    staleTime: Infinity,
  });
  const estimateText = !cfg
    ? "예상 소요 시간: -"
    : cfg.editable
      ? valid ? `예상 소요 시간: ${formatDuration(customEstimate.data?.total_s)}` : "예상 소요 시간: 유효하지 않은 입력"
      : `예상 소요 시간: ${formatDuration(estOf(props.preset))}`;

  const version = useQuery({
    queryKey: ["version", serial, props.app?.name],
    queryFn: () => api.packageVersion(serial, props.app!.name),
    enabled: !!props.app,
  });

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

  const f = props.fields;
  const setF = (k: keyof CustomFields) => (e: React.ChangeEvent<HTMLInputElement>) => props.onFields({ ...f, [k]: e.target.value });
  const radio = (id: PresetChoice, full = false) => {
    const preset = presets.data?.find((x) => x.id === id);
    if (!preset) return null;
    return (
      <div className={full ? "full" : undefined}>
        <Radio name="preset" checked={props.preset === id} onChange={() => props.onPreset(id)}>
          {presetLabel(preset, estOf(id))}
        </Radio>
      </div>
    );
  };

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
        <span style={{ fontSize: 28, lineHeight: 1 }}>📱</span>
        <div className="col">
          <span className="bold">{props.app ? props.app.display_name : "앱을 선택하면 정보가 표시됩니다"}</span>
          {props.app && <span className="small c-gray">{props.app.name}</span>}
          {version.data && (
            <span className="small c-blue">
              📱 설치된 버전: {version.data.version_name ?? "-"} ({version.data.version_code ?? "-"})
            </span>
          )}
        </div>
      </div>

      <div className="row" style={{ padding: "3px 0" }}>
        <span style={{ paddingLeft: 5 }}>패키지명 검색:</span>
        <Entry
          className="grow"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setDialog({ query: search })}
          disabled={running}
        />
        <Button onClick={() => setDialog({ query: search })} disabled={running}>검색 &amp; 선택</Button>
        <Button onClick={props.onLaunch} disabled={!props.app}>앱 실행</Button>
      </div>

      <LabelFrame text="테스트 프리셋" style={{ margin: "6px 0" }}>
        <div className="preset-grid">
          <div className="full c-gray small" style={{ marginBottom: 3 }}>빠른 검증: Smoke/Quick  |  심화 테스트: Standard/Deep/Extreme</div>
          {radio("smoke")}
          {radio("quick")}
          {radio("standard")}
          {radio("deep")}
          {radio("extreme", true)}
          <div className="full row" style={{ gap: 50, marginTop: 2 }}>
            <Radio name="preset" checked={props.preset === "custom"} onChange={() => props.onPreset("custom")}>사용자 지정 (Random Seed)</Radio>
            <Radio name="preset" checked={props.preset === "reproduce"} onChange={() => props.onPreset("reproduce")}>재현테스트</Radio>
          </div>
          <div className="full col" style={{ paddingLeft: 15, gap: 3, marginTop: 2 }}>
            <div className="row">
              <span>이벤트 수:</span>
              <Entry style={{ width: 70, marginRight: 18 }} value={cfg?.editable ? f.events : String(cfg?.events ?? "")} onChange={setF("events")} disabled={!cfg?.editable} />
              <span>반복 횟수:</span>
              <Entry style={{ width: 70, marginRight: 18 }} value={cfg?.editable ? f.repeats : String(cfg?.repeats ?? "")} onChange={setF("repeats")} disabled={!cfg?.editable} />
              <span>Throttle(ms):</span>
              <Entry style={{ width: 70 }} value={cfg?.editable ? f.throttle : String(cfg?.throttle_ms ?? "")} onChange={setF("throttle")} disabled={!cfg?.editable} />
            </div>
            <div className="row">
              <span style={{ marginRight: 8 }}>※ 재현테스트용 Seed 값 입력:</span>
              <span>Seed:</span>
              <Entry style={{ width: 70, marginRight: 18 }} value={f.seed} onChange={setF("seed")} disabled={props.preset !== "reproduce"} />
              <span className="c-blue">{estimateText}</span>
            </div>
          </div>
          <img
            className={`gemini-logo${props.aiAdvisor ? "" : " off"}`}
            src="/gemini_logo.png"
            alt="Gemini"
            title={props.aiAdvisor ? "Gemini AI 적응형 조정 사용 중" : "Gemini AI 비활성 (MONKEY_GEMINI_API_KEY 미설정) - 기본 알고리즘 사용"}
          />
        </div>
      </LabelFrame>

      <div className="row" style={{ padding: "6px 0 2px" }}>
        <Button onClick={props.onStart} disabled={running || props.busy || !props.app || !valid || props.deviceStatus !== "connected"}>
          {running ? "테스트 진행 중..." : "테스트 시작"}
        </Button>
        {running && <Button onClick={props.onStop} disabled={s?.state === "stopping"}>테스트 중지</Button>}
        <div className="col" style={{ width: 220, marginLeft: 20, gap: 2 }}>
          <span className="small" style={{ textAlign: "center" }}>{progressText}</span>
          <Progressbar value={finished && s?.state === "completed" ? 100 : overall} indeterminate={s?.state === "preparing"} />
        </div>
        <span className="grow" />
        <Button onClick={props.onReboot} disabled={running}>폰 재부팅</Button>
        {props.connection.wireless && <Button onClick={props.onDisconnect} disabled={running}>무선 연결 종료</Button>}
        <Button onClick={() => s && window.open(api.reportUrl(s.id, "html"), "_blank")} disabled={!finished}>HTML 보기</Button>
        <Button onClick={() => s && window.open(api.reportUrl(s.id, "xlsx"), "_blank")} disabled={!finished}>엑셀 내보내기</Button>
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
