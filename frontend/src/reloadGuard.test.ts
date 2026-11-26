import { expect, it } from "vitest";
import { installReloadGuard } from "./reloadGuard";

it("blocks reload keys in inputs and preserves ordinary editing and app shortcuts", () => {
  const remove = installReloadGuard();
  const input = document.createElement("input");
  document.body.append(input);
  const send = (init: KeyboardEventInit) => {
    const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
    input.dispatchEvent(event);
    return event.defaultPrevented;
  };
  try {
    expect(send({ key: "F5" })).toBe(true);
    expect(send({ key: "F5", ctrlKey: true })).toBe(true);
    expect(send({ key: "R", code: "KeyR", ctrlKey: true, shiftKey: true })).toBe(true);
    expect(send({ key: "ㄱ", code: "KeyR", ctrlKey: true })).toBe(true);
    expect(send({ key: "r", metaKey: true })).toBe(true);
    for (const init of [{ key: "r" }, { key: "c", ctrlKey: true }, { key: "Tab" }, { key: "Escape" }]) {
      expect(send(init)).toBe(false);
    }
    remove();
    expect(send({ key: "F5" })).toBe(false);
  } finally { remove(); input.remove(); }
});
