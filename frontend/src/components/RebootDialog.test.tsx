import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { api } from "../api/client";
import { RebootDialog } from "./RebootDialog";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("uses an app modal, cancellation sends nothing, and repeated confirmation sends once", async () => {
  const host = document.createElement("div"); const root = createRoot(host);
  const close = vi.fn(), done = vi.fn();
  let complete!: (result: { message: string }) => void;
  vi.spyOn(api, "reboot").mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
  try {
    await act(async () => { root.render(<RebootDialog serial="TEST" onClose={close} onDone={done} />); });
    const button = (label: string) => [...host.querySelectorAll("button")].find((b) => b.textContent === label)!;
    act(() => button("취소").click());
    expect(close).toHaveBeenCalledOnce(); expect(api.reboot).not.toHaveBeenCalled();
    await act(async () => { const confirm = button("재부팅"); confirm.click(); confirm.click(); });
    expect(api.reboot).toHaveBeenCalledOnce(); expect(button("취소").disabled).toBe(true);
    await act(async () => { complete({ message: "accepted" }); });
    expect(done).toHaveBeenCalledOnce();
  } finally { act(() => root.unmount()); vi.restoreAllMocks(); }
});
