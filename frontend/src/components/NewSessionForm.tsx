import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useCreateAndStart, usePackages, usePresets } from "../api/hooks";
import { ErrorNote, formatDuration, type ShowLogs } from "./common";

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function NewSessionForm(props: { serial: string | null; onStarted: (id: string) => void; onShowLogs: ShowLogs }) {
  const [query, setQuery] = useState("");
  const [includeSystem, setIncludeSystem] = useState(false);
  const [pkg, setPkg] = useState<string | null>(null);
  const [presetId, setPresetId] = useState("standard");
  const [events, setEvents] = useState("");
  const [repeats, setRepeats] = useState("");
  const [throttle, setThrottle] = useState("");
  const [seed, setSeed] = useState("");

  const packages = usePackages(props.serial, useDebounced(query), includeSystem);
  const presets = usePresets();
  const preset = presets.data?.find((p) => p.id === presetId);
  const start = useCreateAndStart();

  const config = useMemo(() => {
    if (!preset) return null;
    return {
      events: Number(events) || preset.events,
      repeats: Number(repeats) || preset.repeats,
      throttle_ms: throttle === "" ? preset.throttle_ms : Number(throttle),
      target_minutes_per_run: preset.target_minutes_per_run ?? null,
    };
  }, [preset, events, repeats, throttle]);
  const estimate = useQuery({
    queryKey: ["estimate", config],
    queryFn: () => api.estimate(config!),
    enabled: !!config,
    staleTime: Infinity,
  });

  const needsSeed = preset?.seed_mode === "manual";
  const canStart = !!props.serial && !!pkg && !!preset && (!needsSeed || seed !== "") && !start.isPending;

  const submit = () => {
    if (!props.serial || !pkg || !config) return;
    start.mutate(
      {
        device_serial: props.serial,
        package: pkg,
        preset_id: presetId,
        overrides: {
          events: events ? Number(events) : null,
          repeats: repeats ? Number(repeats) : null,
          throttle_ms: throttle !== "" ? Number(throttle) : null,
          seed: seed ? Number(seed) : null,
        },
      },
      { onSuccess: (s) => props.onStarted(s.id) },
    );
  };

  return (
    <section className="card">
      <h2>새 테스트</h2>
      {!props.serial && <p className="muted small">먼저 디바이스를 선택하세요.</p>}
      <div className="row">
        <input className="grow" placeholder="앱 이름 / 패키지 검색" value={query} onChange={(e) => setQuery(e.target.value)} disabled={!props.serial} />
        <label className="small row" style={{ gap: 4 }}>
          <input type="checkbox" checked={includeSystem} onChange={(e) => setIncludeSystem(e.target.checked)} /> 시스템
        </label>
      </div>
      <ErrorNote error={packages.error} onShowLogs={props.onShowLogs} />
      <ul className="list" style={{ marginTop: 8, maxHeight: 200 }}>
        {packages.data?.items.slice(0, 200).map((p) => (
          <li key={p.name}>
            <button aria-pressed={pkg === p.name} onClick={() => setPkg(p.name)}>
              <span>{p.display_name}</span>
              <span className="muted small mono">{p.name}</span>
            </button>
          </li>
        ))}
        {packages.data && packages.data.total === 0 && <li className="muted small">결과 없음</li>}
      </ul>

      <div className="form" style={{ marginTop: 10 }}>
        <label htmlFor="preset">프리셋</label>
        <select id="preset" value={presetId} onChange={(e) => setPresetId(e.target.value)}>
          {presets.data?.map((p) => (
            <option key={p.id} value={p.id}>{p.name} — {p.description}</option>
          ))}
        </select>
        <label htmlFor="events">이벤트</label>
        <input id="events" inputMode="numeric" placeholder={String(preset?.events ?? "")} value={events} onChange={(e) => setEvents(e.target.value)} />
        <label htmlFor="repeats">반복</label>
        <input id="repeats" inputMode="numeric" placeholder={String(preset?.repeats ?? "")} value={repeats} onChange={(e) => setRepeats(e.target.value)} />
        <label htmlFor="throttle">Throttle(ms)</label>
        <input id="throttle" inputMode="numeric" placeholder={String(preset?.throttle_ms ?? "")} value={throttle} onChange={(e) => setThrottle(e.target.value)} />
        <label htmlFor="seed">Seed</label>
        <input
          id="seed"
          inputMode="numeric"
          placeholder={needsSeed ? "필수" : preset?.seed_mode === "fixed" ? String(preset.fixed_seed) : "회차마다 랜덤"}
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
        />
      </div>
      <p className="small muted">
        예상 소요 {formatDuration(estimate.data?.total_s)}
        {preset?.target_minutes_per_run ? ` · 회차당 ${preset.target_minutes_per_run}분 목표(적응형)` : ""}
      </p>
      <button className="primary" disabled={!canStart} onClick={submit}>
        {start.isPending ? "시작 중…" : "테스트 시작"}
      </button>
      <ErrorNote error={start.error} onShowLogs={props.onShowLogs} />
    </section>
  );
}
