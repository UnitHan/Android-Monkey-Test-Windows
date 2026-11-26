import { useHealth } from "../api/hooks";

export function HealthBadge() {
  const { data, error } = useHealth();
  if (error) return <span className="badge bad">API 연결 안 됨</span>;
  if (!data) return <span className="badge">확인 중…</span>;
  return (
    <span className={`badge ${data.adb.available ? "good" : "bad"}`} title={data.adb.path}>
      {data.adb.available ? `ADB ${data.adb.version?.replace("Android Debug Bridge version ", "") ?? ""}` : "ADB 없음"}
      <span className="muted">· API {data.version}</span>
    </span>
  );
}
