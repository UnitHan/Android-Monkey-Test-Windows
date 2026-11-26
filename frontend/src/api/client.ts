/** Typed REST client for /api/v1. Every failure becomes an ApiError carrying the server request_id,
 *  so the UI can link straight to the matching API logs. */
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Device = Schemas["Device"];
export type DeviceInfo = Schemas["DeviceInfo"];
export type PackageItem = Schemas["PackageItem"];
export type Preset = Schemas["Preset"];
export type Session = Schemas["Session"];
export type SessionEvent = Schemas["SessionEvent"];
export type Issue = Schemas["Issue"];
export type PerfSample = Schemas["PerfSample"];
export type Progress = Schemas["Progress"];
export type LogRecord = Schemas["LogRecordOut"];
export type Problem = Schemas["Problem"];
export type Estimate = Schemas["Estimate"];
export type SessionCreate = Schemas["SessionCreateIn"];

export const API_BASE = `${import.meta.env.VITE_API_ORIGIN ?? ""}/api/v1`;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly detail: string,
    readonly requestId: string | null,
    readonly problem?: Problem,
  ) {
    super(`${code}: ${detail}`);
  }
}

export async function toApiError(resp: Response): Promise<ApiError> {
  const rid = resp.headers.get("x-request-id");
  const type = resp.headers.get("content-type") ?? "";
  if (type.includes("json")) {
    const body = (await resp.json()) as Partial<Problem>;
    return new ApiError(
      resp.status,
      body.code ?? `http_${resp.status}`,
      body.detail ?? resp.statusText,
      body.request_id ?? rid,
      body as Problem,
    );
  }
  return new ApiError(resp.status, `http_${resp.status}`, (await resp.text()) || resp.statusText, rid);
}

type Query = Record<string, string | number | boolean | null | undefined>;

function url(path: string, query?: Query): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  const s = qs.toString();
  return `${API_BASE}${path}${s ? `?${s}` : ""}`;
}

export async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(url(path, opts.query), {
      method,
      headers: opts.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch (e) {
    throw new ApiError(0, "network_error", e instanceof Error ? e.message : String(e), null);
  }
  if (!resp.ok) throw await toApiError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

const enc = encodeURIComponent;

export const api = {
  health: () => request<Schemas["Health"]>("GET", "/health"),
  presets: () => request<Schemas["PresetList"]>("GET", "/presets").then((r) => r.items),
  estimate: (body: Schemas["EstimateIn"]) => request<Estimate>("POST", "/estimates", { body }),
  devices: () => request<Schemas["DeviceList"]>("GET", "/devices").then((r) => r.items),
  device: (serial: string) => request<DeviceInfo>("GET", `/devices/${enc(serial)}`),
  connect: (host: string, port: number) => request<Schemas["ConnectOut"]>("POST", "/devices/connect", { body: { host, port } }),
  pair: (host: string, port: number, code: string) =>
    request<Schemas["PairOut"]>("POST", "/devices/pair", { body: { host, port, code } }),
  disconnect: (serial: string) => request<void>("POST", `/devices/${enc(serial)}/disconnect`),
  tcpip: (serial: string, port: number) =>
    request<Schemas["AcceptedOut"]>("POST", `/devices/${enc(serial)}/tcpip`, { body: { port } }),
  reboot: (serial: string) => request<Schemas["AcceptedOut"]>("POST", `/devices/${enc(serial)}/reboot`),
  launch: (serial: string, pkg: string) => request<void>("POST", `/devices/${enc(serial)}/packages/${enc(pkg)}/launch`),
  packageVersion: (serial: string, pkg: string) =>
    request<Schemas["PackageVersion"]>("GET", `/devices/${enc(serial)}/packages/${enc(pkg)}`),
  packages: (serial: string, query?: string, includeSystem = false) =>
    request<Schemas["PackageList"]>("GET", `/devices/${enc(serial)}/packages`, {
      query: { query, include_system: includeSystem },
    }),
  sessions: () => request<Schemas["SessionList"]>("GET", "/sessions").then((r) => r.items),
  session: (id: string) => request<Session>("GET", `/sessions/${enc(id)}`),
  createSession: (body: SessionCreate) => request<Session>("POST", "/sessions", { body }),
  startSession: (id: string) => request<Session>("POST", `/sessions/${enc(id)}/start`),
  stopSession: (id: string) => request<Session>("POST", `/sessions/${enc(id)}/stop`),
  deleteSession: (id: string) => request<void>("DELETE", `/sessions/${enc(id)}`),
  events: (id: string, afterSeq = 0) =>
    request<Schemas["EventList"]>("GET", `/sessions/${enc(id)}/events`, { query: { after_seq: afterSeq } }),
  issues: (id: string) => request<Schemas["IssueList"]>("GET", `/sessions/${enc(id)}/issues`).then((r) => r.items),
  perf: (id: string) => request<Schemas["PerfList"]>("GET", `/sessions/${enc(id)}/perf`).then((r) => r.items),
  logs: (q: { level?: string; source?: string; session_id?: string; request_id?: string; since_seq?: number; limit?: number }) =>
    request<Schemas["LogList"]>("GET", "/logs", { query: q }),
  report: (id: string) => request<Schemas["SessionReport"]>("GET", `/sessions/${enc(id)}/report`),
  reportUrl: (id: string, kind: "html" | "xlsx") => `${API_BASE}/sessions/${enc(id)}/report.${kind}`,
  logcatUrl: (id: string, run: number) => `${API_BASE}/sessions/${enc(id)}/logcat/${run}`,
  streamUrl: (id: string) => `${API_BASE}/sessions/${enc(id)}/events/stream`,
};
