import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import type { Session } from "../api/client";
import { HtmlReportWorkspace } from "./HtmlReportWorkspace";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("renders HTML inside a sandboxed report tab without opening a popup", async () => {
  const host = document.createElement("div");
  const root = createRoot(host);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("<html><head></head><body>Test report</body></html>"));
  const popup = vi.spyOn(window, "open");
  const session = { id: "s_test", state: "completed" } as Session;
  try {
    await act(async () => { root.render(<QueryClientProvider client={qc}><HtmlReportWorkspace session={session} /></QueryClientProvider>); });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 25)); });
    const frame = host.querySelector("iframe")!;
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(frame.srcdoc).toContain("Test report");
    expect(frame.srcdoc).toContain('<base href="about:srcdoc">');
    expect(fetcher).toHaveBeenCalled();
    expect(popup).not.toHaveBeenCalled();
  } finally { act(() => root.unmount()); qc.clear(); vi.restoreAllMocks(); }
});
