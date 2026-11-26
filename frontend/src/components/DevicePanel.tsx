import { useState } from "react";
import { useConnect, useDevice, useDevices } from "../api/hooks";
import { ErrorNote, type ShowLogs } from "./common";

export function DevicePanel(props: { selected: string | null; onSelect: (s: string) => void; onShowLogs: ShowLogs }) {
  const devices = useDevices();
  const info = useDevice(props.selected);
  return (
    <section className="card">
      <h2>디바이스</h2>
      <ErrorNote error={devices.error} onShowLogs={props.onShowLogs} />
      <ul className="list">
        {devices.data?.map((d) => (
          <li key={d.serial}>
            <button
              aria-pressed={props.selected === d.serial}
              disabled={d.state !== "device"}
              onClick={() => props.onSelect(d.serial)}
            >
              <span>{d.model ?? d.serial} <span className="muted small mono">{d.serial}</span></span>
              <span className={`badge ${d.state === "device" ? "good" : "bad"}`}>
                {d.connection === "wifi" ? "Wi-Fi" : "USB"} · {d.state}
              </span>
            </button>
          </li>
        ))}
        {devices.data?.length === 0 && <li className="muted">연결된 디바이스가 없습니다.</li>}
      </ul>
      {info.data && (
        <p className="small muted" style={{ marginBottom: 0 }}>
          {info.data.model} · Android {info.data.android_version} (API {info.data.api_level})
        </p>
      )}
      <ErrorNote error={info.error} onShowLogs={props.onShowLogs} />
      <WirelessForm onShowLogs={props.onShowLogs} />
    </section>
  );
}

function WirelessForm({ onShowLogs }: { onShowLogs: ShowLogs }) {
  const [host, setHost] = useState("");
  const [port, setPort] = useState("5555");
  const [code, setCode] = useState("");
  const connect = useConnect();
  return (
    <details style={{ marginTop: 10 }}>
      <summary className="small">무선 연결 / 페어링</summary>
      <form
        className="row"
        style={{ marginTop: 8 }}
        onSubmit={(e) => {
          e.preventDefault();
          connect.mutate({ host, port: Number(port), code: code || undefined });
        }}
      >
        <input aria-label="IP" placeholder="192.168.0.10" value={host} onChange={(e) => setHost(e.target.value)} className="grow" />
        <input aria-label="포트" value={port} onChange={(e) => setPort(e.target.value)} style={{ width: 70 }} />
        <input aria-label="페어링 코드" placeholder="페어링 코드(선택)" value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 130 }} />
        <button type="submit" disabled={!host || connect.isPending}>{code ? "페어링" : "연결"}</button>
      </form>
      {connect.isSuccess && <p className="small" style={{ color: "var(--good)" }}>완료</p>}
      <ErrorNote error={connect.error} onShowLogs={onShowLogs} />
    </details>
  );
}
