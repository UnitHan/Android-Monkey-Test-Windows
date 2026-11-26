import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { keys } from "../api/hooks";
import { AppIcon } from "./AppIcon";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const host = document.createElement("div");
let root = createRoot(host);
afterEach(() => { act(() => root.unmount()); root = createRoot(host); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("shows the selected cached icon and never reuses it for another app when extraction fails", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(keys.icon("device", "first"), {
    package: "first", mime_type: "image/png", data_base64: "first-icon", fingerprint: "first-key", cached: true,
  });
  vi.spyOn(api, "appIcon").mockRejectedValue(new Error("unsupported icon"));
  const render = (pkg: string) => <QueryClientProvider client={qc}><AppIcon serial="device" pkg={pkg} /></QueryClientProvider>;
  await act(async () => { root.render(render("first")); });
  expect(host.querySelector("img")?.getAttribute("src")).toBe("data:image/png;base64,first-icon");
  await act(async () => { root.render(render("second")); });
  expect(host.querySelector("img")).toBeNull();
  expect(host.querySelector('[aria-label="기본 앱 아이콘"]')).not.toBeNull();
  expect(api.appIcon).toHaveBeenCalledWith("device", "second", expect.any(AbortSignal));
  qc.clear();
});

it("loads list icons only after they enter the visible list and shares the selection cache", async () => {
  let notify: IntersectionObserverCallback = () => {};
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", class {
    constructor(callback: IntersectionObserverCallback) { notify = callback; }
    observe() {} disconnect = disconnect;
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const fetchIcon = vi.spyOn(api, "appIcon").mockResolvedValue({
    package: "app", mime_type: "image/png", data_base64: "icon", fingerprint: "key", cached: true,
  });
  await act(async () => root.render(<QueryClientProvider client={qc}>
    <AppIcon serial="device" pkg="app" size={40} lazy label="앱" />
  </QueryClientProvider>));
  expect(fetchIcon).not.toHaveBeenCalled();
  await act(async () => notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
  expect(fetchIcon).toHaveBeenCalledTimes(1);
  expect(host.querySelector("img")?.getAttribute("alt")).toBe("앱 아이콘");
  expect(host.querySelector("img")?.getAttribute("width")).toBe("40");
  await act(async () => root.render(<QueryClientProvider client={qc}><AppIcon serial="device" pkg="app" /></QueryClientProvider>));
  expect(fetchIcon).toHaveBeenCalledTimes(1);
  expect(disconnect).toHaveBeenCalled();
  qc.clear();
});
