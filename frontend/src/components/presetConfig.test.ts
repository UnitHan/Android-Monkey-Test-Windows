import { describe, expect, it } from "vitest";
import type { Preset } from "../api/client";
import {
  DEFAULT_FIELDS, effectiveConfig, estimateInput, fieldsFromPreset, formatDuration, overridesFor, presetLabel,
} from "./presetConfig";

const mix = {
  touch: 25, motion: 20, trackball: 0, nav: 15, majornav: 10, syskeys: 5,
  appswitch: 3, anyevent: 22, pinchzoom: 0, rotation: 0,
};
const preset = (over: Partial<Preset>): Preset => ({
  id: "smoke", name: "Smoke Test", description: "", events: 4000, repeats: 5, throttle_ms: 250,
  target_minutes_per_run: 6, seed_mode: "random", fixed_seed: null, event_mix: mix, bugreport: false,
  adaptive_margin: 0.2, ...over,
});
const PRESETS: Preset[] = [
  preset({}),
  preset({ id: "deep", name: "Deep Test", events: 20000, repeats: 10, throttle_ms: 150, target_minutes_per_run: 18, seed_mode: "fixed", fixed_seed: 4850 }),
  preset({ id: "custom", name: "Custom", events: 3000, target_minutes_per_run: null, throttle_ms: 200 }),
  preset({ id: "reproduce", name: "재현테스트", events: 3000, throttle_ms: 300, target_minutes_per_run: null, seed_mode: "manual" }),
];

describe("presetConfig", () => {
  it("built-in presets are read-only, time-boxed and send no overrides", () => {
    const cfg = effectiveConfig("deep", PRESETS, DEFAULT_FIELDS)!;
    expect([cfg.editable, cfg.mode, cfg.minutes, cfg.seed, cfg.valid]).toEqual([false, "time", 18, 4850, true]);
    expect(overridesFor(cfg)).toBeNull();
    expect(estimateInput(cfg)).toEqual({ events: null, repeats: 10, throttle_ms: 150, target_minutes_per_run: 18 });
  });

  it("custom event mode uses v3 defaults and random seed", () => {
    const cfg = effectiveConfig("custom", PRESETS, DEFAULT_FIELDS)!;
    expect(cfg.valid).toBe(true);
    expect(overridesFor(cfg)).toEqual({ events: 3000, target_minutes_per_run: null, repeats: 5, throttle_ms: 200, seed: null });
  });

  it("custom time mode sends minutes, not events", () => {
    const cfg = effectiveConfig("custom", PRESETS, { ...DEFAULT_FIELDS, mode: "time", minutes: "2.5", seedMode: "fixed", seed: "77" })!;
    expect(overridesFor(cfg)).toEqual({ events: null, target_minutes_per_run: 2.5, repeats: 5, throttle_ms: 200, seed: 77 });
  });

  it("validates ranges and formats per field", () => {
    const cfg = effectiveConfig("custom", PRESETS, { ...DEFAULT_FIELDS, events: "0", repeats: "abc", throttle: "20000" })!;
    expect(cfg.valid).toBe(false);
    expect(Object.keys(cfg.errors).sort()).toEqual(["events", "repeats", "throttle"]);
  });

  it("reproduce forces event mode and requires a seed", () => {
    const noSeed = effectiveConfig("reproduce", PRESETS, { ...DEFAULT_FIELDS, mode: "time", seed: "" })!;
    expect([noSeed.mode, noSeed.valid, !!noSeed.errors.seed]).toEqual(["events", false, true]);
    const ok = effectiveConfig("reproduce", PRESETS, { ...DEFAULT_FIELDS, seed: "1234" })!;
    expect(overridesFor(ok)?.seed).toBe(1234);
  });

  it("fills the custom form from a preset", () => {
    const f = fieldsFromPreset(PRESETS[1], DEFAULT_FIELDS);
    expect(f).toMatchObject({ mode: "time", minutes: "18", repeats: "10", throttle: "150", seedMode: "fixed", seed: "4850" });
  });

  it("labels time-boxed presets by their time rule", () => {
    expect(presetLabel(PRESETS[0], 1865)).toBe("Smoke Test - 총 30분 · 회차당 6분 x 5회 (Throttle: 250ms, Random Seed)");
    expect(presetLabel(PRESETS[1], 10925)).toContain("총 3시간");
    expect(formatDuration(10920)).toBe("약 3시간 2분");
  });
});
