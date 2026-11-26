import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { api, type Schemas } from "../api/client";
import { GeminiSettings } from "./GeminiSettings";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("uses a password field, clears the draft after encrypted save and supports deletion", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const initial: Schemas["AiSettingsOut"] = {
    configured: false, enabled: false, model: "test-model", config_file: "gemini.enc.json",
    restart_required: false, usage: "next_run_event_suggestion",
  };
  vi.spyOn(api, "aiSettings").mockResolvedValue(initial);
  vi.spyOn(api, "saveAiSettings").mockResolvedValue({ ...initial, configured: true });
  vi.spyOn(api, "deleteAiSettings").mockResolvedValue(initial);
  try {
    await act(async () => {
      root.render(<QueryClientProvider client={qc}><GeminiSettings /></QueryClientProvider>);
      await new Promise((r) => setTimeout(r, 20));
    });
    const input = host.querySelector("input")!;
    expect(input.type).toBe("password");
    const button = (label: string) => [...host.querySelectorAll("button")].find((b) => b.textContent === label)!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "synthetic-secret");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => { button("암호화 저장").click(); await new Promise((r) => setTimeout(r, 20)); });
    expect(api.saveAiSettings).toHaveBeenCalledWith({ api_key: "synthetic-secret", model: "test-model" });
    expect(input.value).toBe("");
    expect(host.textContent).not.toContain("synthetic-secret");
    await act(async () => { button("키 삭제").click(); await new Promise((r) => setTimeout(r, 20)); });
    expect(api.deleteAiSettings).toHaveBeenCalledOnce();
  } finally {
    act(() => root.unmount()); qc.clear(); host.remove(); vi.restoreAllMocks();
  }
});
