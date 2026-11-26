import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { api, type Session } from "../api/client";
import { keys } from "../api/hooks";
import { DeleteHistoryDialog } from "./DeleteHistoryDialog";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

it("requires confirmation and clears only the deleted session's history and cached results", async () => {
  const host = document.createElement("div"), root = createRoot(host);
  const qc = new QueryClient();
  const session = { id: "s_delete", state: "completed", created_at: "2026-11-26T00:00:00Z",
    config: { package: "com.example.test" } } as Session;
  const other = { ...session, id: "s_keep" };
  qc.setQueryData(keys.sessions, [session, other]);
  qc.setQueryData(["report", session.id], { result: "old" });
  qc.setQueryData(["report", other.id], { result: "keep" });
  const close = vi.fn(), done = vi.fn();
  let finish!: () => void;
  const remove = vi.spyOn(api, "deleteSession").mockImplementation(() => new Promise<void>(resolve => { finish = resolve; }));
  try {
    await act(async () => root.render(<QueryClientProvider client={qc}>
      <DeleteHistoryDialog session={session} onClose={close} onDeleted={done} />
    </QueryClientProvider>));
    const button = (label: string) => [...host.querySelectorAll("button")].find(b => b.textContent === label)!;
    act(() => button("취소").click());
    expect(remove).not.toHaveBeenCalled();
    await act(async () => { const confirm = button("완전 삭제"); confirm.click(); confirm.click(); });
    expect(remove).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledWith("s_delete");
    expect(button("취소").disabled).toBe(true);
    await act(async () => finish());
    expect(done).toHaveBeenCalledWith("s_delete");
    expect(qc.getQueryData(keys.sessions)).toEqual([other]);
    expect(qc.getQueryData(["report", session.id])).toBeUndefined();
    expect(qc.getQueryData(["report", other.id])).toEqual({ result: "keep" });
  } finally { act(() => root.unmount()); qc.clear(); vi.restoreAllMocks(); }
});
