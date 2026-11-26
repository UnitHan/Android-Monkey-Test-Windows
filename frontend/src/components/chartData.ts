import type { PerfSample } from "../api/client";

export type Metric = "memory_mb" | "cpu_percent" | "fps" | "frame_time_max_ms";
export function stats(samples: PerfSample[], metric: Metric) {
  const values = samples.map(s => s[metric]).filter((v): v is number => v != null && Number.isFinite(v));
  const sorted = [...values].sort((a, b) => a - b);
  return { latest: samples.at(-1)?.[metric] ?? undefined, mean: values.length ? values.reduce((a, b) => a + b, 0) / values.length : undefined,
    peak: sorted.at(-1), p95: sorted.length ? sorted[Math.ceil(sorted.length * .95) - 1] : undefined };
}

/** Keep extrema, missing points and run boundaries when drawing long sessions. */
export function chartSamples(samples: PerfSample[], metric: Metric, limit = 1200): PerfSample[] {
  if (samples.length <= limit) return samples;
  const bucket = Math.ceil(samples.length / (limit / 4));
  const indices = new Set<number>([0, samples.length - 1]);
  for (let start = 0; start < samples.length; start += bucket) {
    let lo = start, hi = start;
    for (let i = start; i < Math.min(start + bucket, samples.length); i++) {
      const v = samples[i][metric];
      if (v == null || samples[i].run !== samples[Math.max(0, i - 1)].run) { indices.add(i); continue; }
      if (v < (samples[lo][metric] ?? Infinity)) lo = i;
      if (v > (samples[hi][metric] ?? -Infinity)) hi = i;
    }
    indices.add(lo); indices.add(hi);
  }
  return [...indices].sort((a, b) => a - b).map(i => samples[i]);
}
