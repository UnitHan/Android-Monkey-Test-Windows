/** v3 "테스트 프리셋" frame: preset radios + a clearer settings box for 사용자 지정 / 재현테스트. */
import { useQueries, useQuery } from "@tanstack/react-query";
import { api, type Preset } from "../api/client";
import { usePresets } from "../api/hooks";
import {
  LIMITS, effectiveConfig, estimateInput, fieldsFromPreset, formatDuration, formatRunTime, presetLabel,
  type CustomFields, type FieldKey, type PresetChoice,
} from "./presetConfig";
import { Entry, LabelFrame, Radio } from "./tk";

const PRESET_ORDER: { id: PresetChoice; full?: boolean }[] = [
  { id: "smoke" }, { id: "standard" }, { id: "deep" }, { id: "extreme" },
];

function NumField(props: {
  id: FieldKey; label: string; unit: string; value: string; onChange: (v: string) => void;
  disabled: boolean; error?: string; hint: string; step?: number; width?: number;
}) {
  const lim = LIMITS[props.id];
  return (
    <span className="row" style={{ gap: 4 }}>
      <label htmlFor={`f-${props.id}`} className={props.disabled ? "c-gray" : undefined}>{props.label}</label>
      <Entry
        id={`f-${props.id}`}
        type="number"
        inputMode="decimal"
        min={lim.min}
        max={lim.max}
        step={props.step ?? 1}
        style={{ width: props.width ?? 72, ...(props.error ? { borderColor: "var(--tk-red)" } : {}) }}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        disabled={props.disabled}
        title={`${props.hint} (${lim.min.toLocaleString()} ~ ${lim.max.toLocaleString()} ${props.unit})`}
        aria-invalid={!!props.error}
      />
      <span className={props.disabled ? "c-gray" : undefined}>{props.unit}</span>
    </span>
  );
}

export function PresetPanel(props: {
  choice: PresetChoice;
  onChoice: (c: PresetChoice) => void;
  fields: CustomFields;
  onFields: (f: CustomFields) => void;
  aiAdvisor: boolean;
}) {
  const presets = usePresets();
  const list = presets.data ?? [];
  const totals = useQueries({
    queries: list.map((p) => ({
      queryKey: ["estimate", "preset", p.id, p.events, p.repeats, p.throttle_ms, p.target_minutes_per_run],
      queryFn: () => api.estimate({
        events: p.target_minutes_per_run != null ? null : p.events, repeats: p.repeats,
        throttle_ms: p.throttle_ms, target_minutes_per_run: p.target_minutes_per_run ?? null,
      }),
      staleTime: Infinity,
    })),
  });
  const totalOf = (id: string) => totals[list.findIndex((p) => p.id === id)]?.data?.total_s;

  const cfg = effectiveConfig(props.choice, list, props.fields);
  const estimate = useQuery({
    queryKey: ["estimate", "config", cfg && estimateInput(cfg)],
    queryFn: () => api.estimate(estimateInput(cfg!)),
    enabled: !!cfg?.valid,
    staleTime: Infinity,
  });
  const est = cfg?.valid ? estimate.data : undefined;

  const f = props.fields;
  const chooseReproduce = () => {
    const rp = list.find((x) => x.id === "reproduce");
    if (rp) props.onFields({ ...fieldsFromPreset(rp, f), mode: "events", seedMode: "fixed", seed: f.seed });
    props.onChoice("reproduce");
  };
  const set = (k: keyof CustomFields) => (v: string) => props.onFields({ ...f, [k]: v });
  const editable = !!cfg?.editable;
  const reproduce = props.choice === "reproduce";
  const timeMode = cfg?.mode === "time";

  // shown value: user input when editable, else the preset; derived field shows the server estimate
  const shown = {
    minutes: editable && timeMode ? f.minutes : est ? String(Math.round((est.per_run_s / 60) * 10) / 10) : cfg?.minutes != null ? String(cfg.minutes) : "",
    events: editable && !timeMode ? f.events : est ? String(est.per_run_events) : String(cfg?.events ?? ""),
    repeats: editable ? f.repeats : String(cfg?.repeats ?? ""),
    throttle: editable ? f.throttle : String(cfg?.throttle_ms ?? ""),
    seed: editable ? f.seed : cfg?.seed != null ? String(cfg.seed) : "",
  };
  const boxTitle = !cfg ? "설정값" : reproduce ? "재현테스트 설정" : editable ? "사용자 지정 설정" : `${cfg.preset.name} 설정값 (읽기 전용 · ${cfg.mode === "time" ? "시간 기준" : "이벤트 기준"})`;
  const seedRandom = !reproduce && (editable ? f.seedMode === "random" : cfg?.seed == null);

  const summary = !cfg
    ? ""
    : !cfg.valid
      ? ""
      : est
        ? `회차당 ${formatRunTime(est.per_run_s)} · 약 ${est.per_run_events.toLocaleString()} 이벤트 x ${cfg.repeats}회 → 예상 소요 시간: ${formatDuration(est.total_s)} (준비 ${formatRunTime(est.overhead_s)} 포함${est.buffer_s ? `, 오차 여유 ${formatRunTime(est.buffer_s)}` : ""})`
        : "예상 소요 시간 계산 중...";

  return (
    <LabelFrame text="테스트 프리셋" style={{ margin: "6px 0" }}>
      <div className="preset-grid">
        <div className="full c-gray small" style={{ marginBottom: 3 }}>
          빠른 검증: Smoke  |  심화 테스트: Standard/Deep/Extreme  |  총 테스트 시간 기준이며 준비·정리 시간은 별도입니다
        </div>
        {PRESET_ORDER.map(({ id, full }) => {
          const p = list.find((x) => x.id === id);
          return p ? (
            <div key={id} className={full ? "full" : undefined} title={`회차당 약 ${p.events.toLocaleString()} 이벤트`}>
              <Radio name="preset" checked={props.choice === id} onChange={() => props.onChoice(id)}>{presetLabel(p, totalOf(id))}</Radio>
            </div>
          ) : null;
        })}
        <div className="full row" style={{ gap: 50, marginTop: 2 }}>
          <Radio name="preset" checked={props.choice === "custom"} onChange={() => props.onChoice("custom")}>사용자 지정</Radio>
          <Radio name="preset" checked={reproduce} onChange={chooseReproduce}>재현테스트 (지정 Seed로 이슈 재현)</Radio>
        </div>
      </div>

      <LabelFrame text={boxTitle} style={{ marginTop: 6, position: "relative" }}>
        {editable && !reproduce && (
          <div className="row" style={{ gap: 18, marginBottom: 4, flexWrap: "wrap" }}>
            <span>실행 기준:</span>
            <label className="tk-radio">
              <input type="radio" name="mode" checked={timeMode} onChange={() => props.onFields({ ...f, mode: "time" })} />
              시간 기준 (회차당 시간 고정)
            </label>
            <label className="tk-radio">
              <input type="radio" name="mode" checked={!timeMode} onChange={() => props.onFields({ ...f, mode: "events" })} />
              이벤트 기준 (이벤트 수 고정)
            </label>
            <label className="row small" style={{ marginLeft: "auto" }}>
              프리셋 값 불러오기:
              <select
                className="tk-entry"
                style={{ height: 22, padding: 0 }}
                value=""
                onChange={(e) => {
                  const p = list.find((x) => x.id === e.target.value);
                  if (p) props.onFields(fieldsFromPreset(p as Preset, f));
                }}
              >
                <option value="">선택...</option>
                {list.filter((p) => p.id !== "custom").map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          </div>
        )}
        <div className="row" style={{ gap: 16, flexWrap: "wrap", paddingRight: 110 }}>
          <NumField id="minutes" label="회차당 시간" unit="분" step={0.5} value={shown.minutes} onChange={set("minutes")}
            disabled={!editable || !timeMode} error={cfg?.errors.minutes} hint="회차마다 monkey를 실행할 시간" width={60} />
          <NumField id="events" label="이벤트 수" unit="개/회" value={shown.events} onChange={set("events")}
            disabled={!editable || timeMode} error={cfg?.errors.events} hint="회차마다 실행할 이벤트 수" width={80} />
          <NumField id="repeats" label="반복" unit="회" value={shown.repeats} onChange={set("repeats")}
            disabled={!editable} error={cfg?.errors.repeats} hint="회차 수 (회차마다 앱 재시작)" width={52} />
          <NumField id="throttle" label="Throttle" unit="ms" value={shown.throttle} onChange={set("throttle")}
            disabled={!editable} error={cfg?.errors.throttle} hint="이벤트 사이 대기 시간" width={64} />
          <span className="row" style={{ gap: 4 }}>
            <label htmlFor="f-seed" className={editable ? undefined : "c-gray"}>Seed</label>
            <select
              className="tk-entry"
              style={{ height: 24, padding: 0 }}
              aria-label="Seed 방식"
              value={seedRandom ? "random" : "fixed"}
              disabled={!editable || reproduce}
              onChange={(e) => props.onFields({ ...f, seedMode: e.target.value as "random" | "fixed" })}
            >
              <option value="random">회차마다 랜덤</option>
              <option value="fixed">고정</option>
            </select>
            {!seedRandom && (
              <Entry
                id="f-seed" type="number" inputMode="numeric" min={0}
                style={{ width: 72, ...(cfg?.errors.seed ? { borderColor: "var(--tk-red)" } : {}) }}
                value={shown.seed} onChange={(e) => set("seed")(e.target.value)} disabled={!editable}
                title="같은 Seed + 같은 설정이면 같은 이벤트 순서가 재현됩니다" aria-invalid={!!cfg?.errors.seed}
              />
            )}
          </span>
        </div>
        {summary && (
          <div className="c-blue" style={{ marginTop: 4 }}>
            {summary}
            {reproduce && <span className="small c-gray">  · 재현할 회차의 Seed는 결과 상세 탭에서 확인하세요</span>}
          </div>
        )}
        {cfg && !cfg.valid && (
          <ul className="c-red small" style={{ margin: "2px 0 0", paddingLeft: 18 }}>
            {Object.values(cfg.errors).map((e) => <li key={e}>{e}</li>)}
          </ul>
        )}
        <img
          className={`gemini-logo${props.aiAdvisor ? "" : " off"}`}
          src="/gemini_logo.png"
          alt="Gemini"
          title={props.aiAdvisor ? "Gemini 키 설정됨 · 다음 회차 이벤트 수 추천 (연결 성공 여부와 별개)"
            : "상단 설정 메뉴에서 Gemini API 키를 등록하세요"}
        />
      </LabelFrame>
    </LabelFrame>
  );
}
