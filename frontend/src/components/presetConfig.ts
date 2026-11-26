/** Pure preset/custom-config logic for the 테스트 프리셋 panel (unit tested). */
import type { Preset, SessionCreate } from "../api/client";

export type PresetChoice = "smoke" | "standard" | "deep" | "extreme" | "custom" | "reproduce";
export type RunMode = "time" | "events";
export type SeedMode = "random" | "fixed";
export type CustomFields = {
  mode: RunMode;
  minutes: string;
  events: string;
  repeats: string;
  throttle: string;
  seedMode: SeedMode;
  seed: string;
};
export type FieldKey = "minutes" | "events" | "repeats" | "throttle" | "seed";

/** v3 defaults for 사용자 지정: 3000 events x 5, 200 ms, seed 1000. */
export const DEFAULT_FIELDS: CustomFields = {
  mode: "events", minutes: "5", events: "3000", repeats: "5", throttle: "200", seedMode: "random", seed: "1000",
};

export const LIMITS = {
  minutes: { min: 0.5, max: 240 },
  events: { min: 1, max: 1_000_000 },
  repeats: { min: 1, max: 100 },
  throttle: { min: 0, max: 10_000 },
  seed: { min: 0, max: 2_147_483_647 },
} as const;

export type EffectiveConfig = {
  preset: Preset;
  editable: boolean;
  mode: RunMode;
  minutes: number | null;
  events: number | null;
  repeats: number;
  throttle_ms: number;
  seed: number | null;
  errors: Partial<Record<FieldKey, string>>;
  valid: boolean;
};

const INT = /^\d+$/;
const DEC = /^\d+(\.\d+)?$/;

function parse(key: FieldKey, raw: string, label: string, decimal = false): [number, string | undefined] {
  const v = raw.trim();
  if (v === "") return [NaN, `${label}을(를) 입력하세요`];
  if (!(decimal ? DEC : INT).test(v)) return [NaN, `${label}은(는) ${decimal ? "숫자" : "0 이상의 정수"}로 입력하세요`];
  const n = Number(v);
  const { min, max } = LIMITS[key];
  if (n < min || n > max) return [n, `${label} 범위: ${min.toLocaleString()} ~ ${max.toLocaleString()}`];
  return [n, undefined];
}

export function effectiveConfig(choice: PresetChoice, presets: Preset[] | undefined, f: CustomFields): EffectiveConfig | null {
  const preset = presets?.find((x) => x.id === choice);
  if (!preset) return null;
  if (choice !== "custom" && choice !== "reproduce") {
    const timed = preset.target_minutes_per_run != null;
    return {
      preset, editable: false, mode: timed ? "time" : "events",
      minutes: preset.target_minutes_per_run ?? null, events: preset.events, repeats: preset.repeats,
      throttle_ms: preset.throttle_ms, seed: preset.seed_mode === "fixed" ? preset.fixed_seed ?? null : null,
      errors: {}, valid: true,
    };
  }
  const reproduce = choice === "reproduce";
  const mode: RunMode = reproduce ? "events" : f.mode;
  const errors: Partial<Record<FieldKey, string>> = {};
  const take = (key: FieldKey, raw: string, label: string, decimal = false) => {
    const [n, err] = parse(key, raw, label, decimal);
    if (err) errors[key] = err;
    return n;
  };
  const minutes = mode === "time" ? take("minutes", f.minutes, "회차당 시간", true) : null;
  const events = mode === "events" ? take("events", f.events, "이벤트 수") : null;
  const repeats = take("repeats", f.repeats, "반복 횟수");
  const throttle_ms = take("throttle", f.throttle, "Throttle");
  const fixedSeed = reproduce || f.seedMode === "fixed";
  const seed = fixedSeed ? take("seed", f.seed, "Seed") : null;
  return {
    preset, editable: true, mode, minutes, events, repeats, throttle_ms, seed,
    errors, valid: Object.keys(errors).length === 0,
  };
}

/** Fill the custom form from a preset (time-boxed presets keep their time rule). */
export function fieldsFromPreset(p: Preset, current: CustomFields): CustomFields {
  const timed = p.target_minutes_per_run != null;
  return {
    ...current,
    mode: timed ? "time" : "events",
    minutes: timed ? String(p.target_minutes_per_run) : current.minutes,
    events: String(p.events),
    repeats: String(p.repeats),
    throttle: String(p.throttle_ms),
    seedMode: p.seed_mode === "fixed" ? "fixed" : "random",
    seed: p.fixed_seed != null ? String(p.fixed_seed) : current.seed,
  };
}

export function overridesFor(cfg: EffectiveConfig): SessionCreate["overrides"] {
  if (!cfg.editable) return null;
  return {
    events: cfg.mode === "events" ? cfg.events : null,
    target_minutes_per_run: cfg.mode === "time" ? cfg.minutes : null,
    repeats: cfg.repeats,
    throttle_ms: cfg.throttle_ms,
    seed: cfg.seed,
  };
}

export function estimateInput(cfg: EffectiveConfig) {
  return {
    events: cfg.mode === "events" ? cfg.events : null,
    repeats: cfg.repeats,
    throttle_ms: cfg.throttle_ms,
    target_minutes_per_run: cfg.mode === "time" ? cfg.minutes : null,
  };
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "-";
  const s = Math.round(totalSeconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `약 ${h}시간 ${m}분` : m ? `약 ${m}분` : `약 ${s}초`;
}

export function formatRunTime(seconds: number): string {
  const s = Math.round(seconds), m = Math.floor(s / 60), r = s % 60;
  if (m >= 60) return `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ""}${r ? ` ${r}초` : ""}`;
  return m ? (r ? `${m}분 ${r}초` : `${m}분`) : `${r}초`;
}

export function presetLabel(p: Preset, totalS: number | undefined): string {
  const seed = p.seed_mode === "fixed" ? `Seed ${p.fixed_seed}` : "Random Seed";
  const shape = p.target_minutes_per_run != null
    ? `총 ${formatRunTime(p.target_minutes_per_run * p.repeats * 60)} · 회차당 ${p.target_minutes_per_run}분 x ${p.repeats}회`
    : `${p.events.toLocaleString()}개 이벤트 x ${p.repeats}회`;
  const estimate = p.target_minutes_per_run == null ? ` → ${formatDuration(totalS)}` : "";
  return `${p.name} - ${shape} (Throttle: ${p.throttle_ms}ms, ${seed})${estimate}`;
}
