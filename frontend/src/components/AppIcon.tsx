import { useEffect, useRef, useState } from "react";
import { useAppIcon } from "../api/hooks";

export function AppIcon({ serial, pkg, size = 48, lazy = false, label = "선택한 앱" }: {
  serial: string; pkg?: string; size?: number; lazy?: boolean; label?: string;
}) {
  const host = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(!lazy);
  useEffect(() => {
    if (!lazy || !host.current) return;
    if (typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), {
      root: null, rootMargin: "0px",
    });
    observer.observe(host.current);
    return () => observer.disconnect();
  }, [lazy]);
  const icon = useAppIcon(serial, pkg, visible);
  const [failed, setFailed] = useState<string | null>(null);
  const fingerprint = icon.data ? `${icon.data.fingerprint}:${icon.dataUpdatedAt}` : undefined;
  const show = !!icon.data && !icon.isError && failed !== fingerprint;
  return <span ref={host} style={{ width: size, height: size, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
    {show ? <img
      src={`data:image/png;base64,${icon.data!.data_base64}`} alt={`${label} 아이콘`} width={size} height={size}
      style={{ objectFit: "contain", borderRadius: 8 }} decoding="async"
      onError={() => setFailed(fingerprint ?? null)}
    /> : <span role="img" aria-label="기본 앱 아이콘" style={{ fontSize: Math.round(size * .58) }}
      title={icon.isFetching ? "단말에서 아이콘 가져오는 중..." : "아이콘을 가져올 수 없어 기본 아이콘을 표시합니다."}>📱</span>}
  </span>;
}
