import { expect, it, vi } from "vitest";
import { scheduleIcon } from "./iconRequests";

it("limits concurrent icon requests and cancels queued requests without sending them", async () => {
  const finish: Array<() => void> = [];
  const load = vi.fn(() => new Promise<void>(resolve => finish.push(resolve)));
  const first = scheduleIcon(load, new AbortController().signal);
  const second = scheduleIcon(load, new AbortController().signal);
  const controller = new AbortController();
  const cancelled = scheduleIcon(load, controller.signal).catch(error => error);
  await Promise.resolve();
  expect(load).toHaveBeenCalledTimes(2);
  controller.abort();
  expect((await cancelled).name).toBe("AbortError");
  finish.forEach(resolve => resolve());
  await Promise.all([first, second]);
  expect(load).toHaveBeenCalledTimes(2);
});
