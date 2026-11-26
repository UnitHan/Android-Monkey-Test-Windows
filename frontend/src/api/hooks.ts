/** Server state lives in TanStack Query only. SSE events patch / invalidate the cache;
 *  no component keeps its own copy of server data. */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { ApiError, api, type PerfSample, type Progress, type Session, type SessionCreate, type SessionEvent } from "./client";
import { scheduleIcon } from "./iconRequests";

export const keys = {
  health: ["health"] as const,
  presets: ["presets"] as const,
  devices: ["devices"] as const,
  device: (s: string) => ["device", s] as const,
  packages: (s: string, q: string, sys: boolean) => ["packages", s, q, sys] as const,
  version: (s: string, p: string) => ["version", s, p] as const,
  play: (p: string) => ["play", p] as const,
  icon: (s: string, p: string) => ["icon", s, p] as const,
  playAuth: ["playAuth"] as const,
  sessions: ["sessions"] as const,
  session: (id: string) => ["session", id] as const,
  issues: (id: string) => ["issues", id] as const,
  perf: (id: string) => ["perf", id] as const,
  events: (id: string) => ["events", id] as const,
  logs: (q: object) => ["logs", q] as const,
};

export const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const PERF_WINDOW = 20000; // covers an 8-hour preset at the default 2-second interval

export async function refreshAppInfo(qc: QueryClient, serial: string, pkg?: string): Promise<void> {
  await Promise.all([
    // Refetch normally afterwards so any network failure is reported through the package query.
    api.packages(serial, "", false, true).catch(() => null)
      .then(() => qc.invalidateQueries({ queryKey: ["packages", serial] })),
    ...(pkg ? [
      qc.invalidateQueries({ queryKey: keys.version(serial, pkg) }),
      qc.invalidateQueries({ queryKey: keys.play(pkg) }),
      qc.invalidateQueries({ queryKey: keys.icon(serial, pkg) }),
    ] : []),
  ]);
}

export const usePackageVersion = (serial: string, pkg?: string) => useQuery({
  queryKey: keys.version(serial, pkg ?? ""),
  queryFn: () => api.packageVersion(serial, pkg!),
  enabled: !!serial && !!pkg,
  retry: false,
});

export const usePlayPackage = (pkg?: string) => useQuery({
  queryKey: keys.play(pkg ?? ""),
  queryFn: () => api.playPackage(pkg!),
  enabled: !!pkg,
  staleTime: 60_000,
  retry: false,
});

export const useAppIcon = (serial: string, pkg?: string, enabled = true) => useQuery({
  queryKey: keys.icon(serial, pkg ?? ""),
  queryFn: ({ signal }) => scheduleIcon(() => api.appIcon(serial, pkg!, signal), signal),
  enabled: enabled && !!serial && !!pkg,
  staleTime: 60_000,
  retry: (count, error) => count < 2 && error instanceof ApiError && (error.status === 0 || error.status >= 500),
  retryDelay: attempt => Math.min(1000 * 2 ** attempt, 4000),
});

/** Retries forever: in the desktop shell the backend may still be starting when the window opens. */
export const useHealth = () =>
  useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 10_000, retry: true, retryDelay: 500 });
export const usePresets = () => useQuery({ queryKey: keys.presets, queryFn: api.presets, staleTime: 30000, refetchInterval: 30000 });
export const useDevices = () => useQuery({ queryKey: keys.devices, queryFn: api.devices, refetchInterval: 5_000 });
export const useDevice = (serial: string | null) =>
  useQuery({ queryKey: keys.device(serial ?? ""), queryFn: () => api.device(serial!), enabled: !!serial });
export const usePackages = (serial: string | null, query: string, includeSystem: boolean) =>
  useQuery({
    queryKey: keys.packages(serial ?? "", query, includeSystem),
    queryFn: () => api.packages(serial!, query, includeSystem),
    enabled: !!serial,
    staleTime: 30_000,
    refetchOnMount: "always",
  });
export const useSessions = () => useQuery({ queryKey: keys.sessions, queryFn: api.sessions, refetchInterval: 15_000 });
export const useSession = (id: string | null) =>
  useQuery({
    queryKey: keys.session(id ?? ""), queryFn: () => api.session(id!), enabled: !!id,
    // SSE can disconnect silently. The authoritative snapshot also recovers missed completion.
    refetchInterval: query => TERMINAL.has(query.state.data?.state ?? "") ? false : 5_000,
    refetchIntervalInBackground: true,
  });
export const useIssues = (id: string | null) =>
  useQuery({ queryKey: keys.issues(id ?? ""), queryFn: () => api.issues(id!), enabled: !!id });
export const usePerf = (id: string | null) =>
  useQuery({ queryKey: keys.perf(id ?? ""), queryFn: () => api.perf(id!), enabled: !!id });
export const useEvents = (id: string | null) =>
  useQuery({ queryKey: keys.events(id ?? ""), queryFn: () => api.events(id!).then((r) => r.items), enabled: !!id });

/** Apply one SSE event to the query cache. Pure w.r.t. inputs; unit tested. */
export function applySessionEvent(qc: QueryClient, id: string, ev: SessionEvent): void {
  if (ev.type === "progress") {
    qc.setQueryData<Session>(keys.session(id), (s) =>
      s && !TERMINAL.has(s.state) ? { ...s, progress: ev.data as unknown as Progress } : s);
    return;
  }
  if (ev.type === "perf") {
    qc.setQueryData<PerfSample[]>(keys.perf(id), (list) => [...(list ?? []), ev.data as unknown as PerfSample].slice(-PERF_WINDOW));
    return;
  }
  qc.setQueryData<SessionEvent[]>(keys.events(id), (list) =>
    list && !list.some((e) => e.seq === ev.seq) ? [...list, ev] : list,
  );
  void qc.invalidateQueries({ queryKey: keys.session(id) });
  if (ev.type === "issue") void qc.invalidateQueries({ queryKey: keys.issues(id) });
  if (ev.type === "state_changed") {
    void qc.invalidateQueries({ queryKey: keys.sessions });
    void qc.invalidateQueries({ queryKey: keys.perf(id) });
  }
}

/** Live updates for one session via SSE. EventSource resumes with Last-Event-ID automatically. */
export function useSessionStream(id: string | null, state: string | undefined): void {
  const qc = useQueryClient();
  const live = !!id && !!state && !TERMINAL.has(state);
  useEffect(() => {
    if (!id || !state || !TERMINAL.has(state)) return;
    // Completion may arrive through snapshot recovery rather than state_changed SSE.
    for (const key of [keys.sessions, keys.perf(id), keys.issues(id), keys.events(id)]) {
      void qc.invalidateQueries({ queryKey: key });
    }
  }, [id, state, qc]);
  useEffect(() => {
    if (!live || !id) return;
    const source = new EventSource(api.streamUrl(id));
    const reconcile = () => {
      for (const key of [keys.session(id), keys.perf(id), keys.issues(id), keys.events(id)]) {
        void qc.invalidateQueries({ queryKey: key });
      }
    };
    source.addEventListener("open", reconcile);
    source.addEventListener("error", reconcile);
    const handler = (msg: MessageEvent<string>) => applySessionEvent(qc, id, JSON.parse(msg.data) as SessionEvent);
    const types = ["state_changed", "progress", "perf", "run_started", "run_finished", "run_extended",
      "segment_started", "segment_finished", "issue", "guard", "report_ready"];
    types.forEach((t) => source.addEventListener(t, handler as EventListener));
    return () => source.close();
  }, [id, live, qc]);
}

function useInvalidateSessions() {
  const qc = useQueryClient();
  return (s?: Session) => {
    void qc.invalidateQueries({ queryKey: keys.sessions });
    if (s) qc.setQueryData(keys.session(s.id), s);
  };
}

export function useCreateAndStart() {
  const done = useInvalidateSessions();
  return useMutation({
    mutationFn: async (body: SessionCreate) => api.startSession((await api.createSession(body)).id),
    onSuccess: done,
  });
}

export function useStopSession() {
  const done = useInvalidateSessions();
  return useMutation({ mutationFn: api.stopSession, onSuccess: done });
}

export function useDeleteSession() {
  const done = useInvalidateSessions();
  return useMutation({ mutationFn: api.deleteSession, onSuccess: () => done() });
}

export function useConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { host: string; port: number; code?: string }): Promise<string> =>
      v.code ? (await api.pair(v.host, v.port, v.code)).message : (await api.connect(v.host, v.port)).serial,
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.devices }),
  });
}
