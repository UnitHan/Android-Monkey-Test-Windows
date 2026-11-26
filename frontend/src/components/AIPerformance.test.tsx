import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { api, type Schemas } from "../api/client";
import { AIPerformance } from "./AIPerformance";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("requires a preview and unchecked consent before any paid analysis request", async () => {
  const preview = vi.spyOn(api, "performancePreview").mockResolvedValue({ input_hash: "a".repeat(64), configured: true,
    model: "fake-model", evidence: { events_sent: 100 } } as Schemas["AnalysisPreview"]);
  const send = vi.spyOn(api, "analyzePerformance").mockRejectedValue(new Error("AI 응답 오류"));
  const report = { session: { id: "s_test" }, ai_performance: null } as Schemas["SessionReport"];
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    await act(async () => root.render(<QueryClientProvider client={qc}><AIPerformance report={report} /></QueryClientProvider>));
    expect(preview).not.toHaveBeenCalled(); expect(send).not.toHaveBeenCalled();
    await act(async () => (host.querySelector("button") as HTMLButtonElement).click());
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 25)); });
    expect(host.querySelector("pre")?.textContent).toContain('"events_sent": 100');
    const submit = [...host.querySelectorAll("button")].find(b => b.textContent === "동의하고 분석")!;
    expect(submit.disabled).toBe(true);
    expect((host.querySelector('input[type="checkbox"]') as HTMLInputElement).checked).toBe(false);
    expect(send).not.toHaveBeenCalled();
    await act(async () => (host.querySelector('input[type="checkbox"]') as HTMLInputElement).click());
    await act(async () => submit.click());
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 25)); });
    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith("s_test", "a".repeat(64));
    expect(host.textContent).toContain("기존 통계는 계속 사용할 수 있습니다");
  } finally { act(() => root.unmount()); host.remove(); qc.clear(); vi.restoreAllMocks(); }
});
