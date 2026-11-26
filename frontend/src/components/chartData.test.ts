import { expect, it } from "vitest";
import type { PerfSample } from "../api/client";
import { chartSamples, stats } from "./chartData";

const sample = (n: number, value: number | null): PerfSample => ({
  at: new Date(n * 1000).toISOString(), run: 1, memory_mb: value, cpu_percent: null,
  source: "appkium", cpu_total_percent: null, cpu_cores: 8, rss_mb: null, fps: null, jank_count: null,
  frame_time_max_ms: null, threads: null, running: true, foreground: true, battery_temp_c: null,
  device_cpu_percent: null, sample_cost_ms: null,
});

it("keeps resource spikes when reducing an eight-hour chart", () => {
  const samples = Array.from({ length: 14400 }, (_, i) => sample(i, i === 7777 ? 999 : 10));
  const chart = chartSamples(samples, "memory_mb");
  expect(chart.length).toBeLessThan(1200);
  expect(chart.some(s => s.memory_mb === 999)).toBe(true);
  expect(chart[0]).toBe(samples[0]);
  expect(chart.at(-1)).toBe(samples.at(-1));
});

it("does not turn missing values into zero in averages or percentiles", () => {
  const result = stats([sample(0, null), sample(1, 10), sample(2, 30)], "memory_mb");
  expect(result.mean).toBe(20);
  expect(result.p95).toBe(30);
  expect(stats([sample(0, null)], "memory_mb").peak).toBeUndefined();
  expect(stats([sample(0, 10), sample(1, null)], "memory_mb").latest).toBeUndefined();
});
