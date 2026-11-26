import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const resp = new Response(body === undefined ? null : JSON.stringify(body), { status, headers });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(resp);
}

afterEach(() => vi.restoreAllMocks());

describe("api client (problem+json contract)", () => {
  it("returns typed body on success and builds query strings", async () => {
    const spy = mockFetch(200, { items: [], total: 0 }, { "content-type": "application/json" });
    await api.packages("R3CN", "kakao", true);
    expect(spy.mock.calls[0][0]).toBe("/api/v1/devices/R3CN/packages?query=kakao&include_system=true");
  });

  it("maps problem+json to ApiError with request_id", async () => {
    mockFetch(
      409,
      { type: "about:blank", title: "Conflict", status: 409, code: "device_busy", detail: "busy", request_id: "r_1" },
      { "content-type": "application/problem+json", "x-request-id": "r_1" },
    );
    const err = await api.startSession("s_1").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect([err.status, err.code, err.detail, err.requestId]).toEqual([409, "device_busy", "busy", "r_1"]);
  });

  it("falls back to header request id for non-json errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("gateway down", { status: 502, headers: { "x-request-id": "r_9", "content-type": "text/plain" } }),
    );
    const err = await api.devices().catch((e) => e);
    expect([err.code, err.detail, err.requestId]).toEqual(["http_502", "gateway down", "r_9"]);
  });

  it("network failures become network_error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await api.health().catch((e) => e);
    expect([err.status, err.code]).toEqual([0, "network_error"]);
  });

  it("204 returns undefined", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.deleteSession("s_1")).resolves.toBeUndefined();
  });
});
