import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, type Session, type SessionEvent } from "./client";
import { applySessionEvent, keys, useSession, useSessionStream } from "./hooks";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const host = document.createElement("div");
let root = createRoot(host);
let qc: QueryClient;
let source: EventTarget & { close: ReturnType<typeof vi.fn> };
const snapshot = (state: Session["state"], percent: number) => ({
  id: "s1", state, progress: { current_run: 5, total_runs: 5, run_percent: percent },
  runs: Array.from({ length: state === "completed" ? 5 : 4 }, (_, i) => ({ run: i + 1 })),
} as Session);

function Screen() {
  const { data } = useSession("s1");
  useSessionStream("s1", data?.state);
  return <div>{data?.state}:{data?.progress.run_percent}:{data?.runs.length}</div>;
}

beforeEach(() => {
  vi.useFakeTimers();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("EventSource", class extends EventTarget {
    close = vi.fn();
    constructor() { super(); source = this; }
  });
});
afterEach(() => {
  act(() => root.unmount()); root = createRoot(host);
  qc.clear(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals();
});
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(20); });
const mount = async () => {
  await act(async () => { root.render(<QueryClientProvider client={qc}><Screen /></QueryClientProvider>); });
  await flush();
};

it("recovers a silently lost stream at run 5/5 and refreshes final results, then stops polling", async () => {
  const request = vi.spyOn(api, "session").mockResolvedValue(snapshot("running", 25));
  for (const key of [keys.perf("s1"), keys.issues("s1"), keys.events("s1"), keys.sessions]) qc.setQueryData(key, []);
  await mount();
  expect(host.textContent).toBe("running:25:4");
  request.mockResolvedValue(snapshot("completed", 100));
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  await flush();
  expect(host.textContent).toBe("completed:100:5");
  expect(source.close).toHaveBeenCalled();
  for (const key of [keys.perf("s1"), keys.issues("s1"), keys.events("s1"), keys.sessions]) {
    expect(qc.getQueryState(key)?.isInvalidated).toBe(true);
  }
  const calls = request.mock.calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
  expect(request).toHaveBeenCalledTimes(calls);
});

it.each(["open", "error"])("resynchronizes immediately on SSE %s", async event => {
  const request = vi.spyOn(api, "session").mockResolvedValue(snapshot("running", 25));
  await mount();
  request.mockResolvedValue(snapshot("running", 60));
  await act(async () => { source.dispatchEvent(new Event(event)); });
  await flush();
  expect(host.textContent).toBe("running:60:4");
});

it("does not let a delayed progress event overwrite a completed snapshot", () => {
  qc.setQueryData(keys.session("s1"), snapshot("completed", 100));
  applySessionEvent(qc, "s1", { seq: 0, type: "progress", at: "", data: { run_percent: 25 } } as SessionEvent);
  expect(qc.getQueryData<Session>(keys.session("s1"))?.progress.run_percent).toBe(100);
});
