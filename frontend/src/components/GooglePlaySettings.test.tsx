import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { api, type Schemas } from "../api/client";
import { keys } from "../api/hooks";
import { GooglePlaySettings } from "./GooglePlaySettings";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("opens login from settings and exposes cancellation without requiring a connected phone", async () => {
  const host = document.createElement("div");
  const root = createRoot(host);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const initial: Schemas["PlayAuthStatus"] = {
    client_configured: true, credentials_saved: false, phase: "idle", message: "연결 필요",
  };
  qc.setQueryData(keys.playAuth, initial);
  vi.spyOn(api, "playAuthStatus").mockResolvedValue(initial);
  vi.spyOn(api, "connectPlay").mockResolvedValue({ ...initial, phase: "pending", message: "브라우저에서 로그인" });
  vi.spyOn(api, "disconnectPlay").mockResolvedValue(initial);
  try {
    await act(async () => {
      root.render(<QueryClientProvider client={qc}><GooglePlaySettings onClose={() => {}} /></QueryClientProvider>);
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    const button = (name: string) => [...host.querySelectorAll("button")].find((b) => b.textContent === name)!;
    await act(async () => { button("Google 계정 연결").click(); await new Promise((r) => setTimeout(r, 20)); });
    expect(api.connectPlay).toHaveBeenCalledOnce();
    expect(button("로그인 취소").disabled).toBe(false);
    await act(async () => { button("로그인 취소").click(); await new Promise((r) => setTimeout(r, 20)); });
    expect(api.disconnectPlay).toHaveBeenCalledOnce();
  } finally {
    act(() => root.unmount()); qc.clear(); vi.restoreAllMocks();
  }
});
