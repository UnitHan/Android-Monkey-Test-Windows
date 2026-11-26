import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { api, type PerfSample, type Session, type SessionEvent } from "./client";
import { applySessionEvent, keys, refreshAppInfo } from "./hooks";

it("refreshes selected device packages, installed version and Play metadata together", async () => {
  const qc = new QueryClient();
  const refresh = vi.spyOn(api, "packages").mockResolvedValue({items: [], total: 0});
  const selected = [keys.packages("s1", "", false), keys.version("s1", "app"), keys.play("app"), keys.icon("s1", "app")];
  const other = keys.version("s2", "app");
  for (const key of [...selected, other]) qc.setQueryData(key, {});
  await refreshAppInfo(qc, "s1", "app");
  expect(refresh).toHaveBeenCalledWith("s1", "", false, true);
  refresh.mockRestore();
  for (const key of selected) expect(qc.getQueryState(key)?.isInvalidated).toBe(true);
  expect(qc.getQueryState(other)?.isInvalidated).toBe(false);
});

const ev = (seq: number, type: string, data: Record<string, unknown> = {}): SessionEvent => ({
  seq, type, at: "2026-11-26T00:00:00Z", data,
});

describe("applySessionEvent (SSE -> query cache)", () => {
  it("patches progress into the session snapshot without refetch", () => {
    const qc = new QueryClient();
    qc.setQueryData(keys.session("s1"), { id: "s1", progress: { run_percent: 0 } } as unknown as Session);
    applySessionEvent(qc, "s1", ev(0, "progress", { run_percent: 42, current_run: 1 }));
    expect(qc.getQueryData<Session>(keys.session("s1"))?.progress.run_percent).toBe(42);
  });

  it("appends perf samples", () => {
    const qc = new QueryClient();
    applySessionEvent(qc, "s1", ev(0, "perf", { at: "x", run: 1, memory_mb: 10, cpu_percent: 1 }));
    applySessionEvent(qc, "s1", ev(0, "perf", { at: "y", run: 1, memory_mb: 11, cpu_percent: 2 }));
    expect(qc.getQueryData<PerfSample[]>(keys.perf("s1"))?.map((p) => p.memory_mb)).toEqual([10, 11]);
  });

  it("dedupes persisted events by seq and invalidates the snapshot", async () => {
    const qc = new QueryClient();
    qc.setQueryData(keys.events("s1"), [ev(1, "state_changed")]);
    qc.setQueryData(keys.session("s1"), { id: "s1" } as unknown as Session);
    applySessionEvent(qc, "s1", ev(1, "state_changed"));
    applySessionEvent(qc, "s1", ev(2, "run_finished"));
    expect(qc.getQueryData<SessionEvent[]>(keys.events("s1"))?.map((e) => e.seq)).toEqual([1, 2]);
    expect(qc.getQueryState(keys.session("s1"))?.isInvalidated).toBe(true);
  });
});
