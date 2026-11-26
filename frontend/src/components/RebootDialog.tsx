import { useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import { Button, Toplevel } from "./tk";

export function RebootDialog({ serial, onClose, onDone }: {
  serial: string; onClose: () => void; onDone: () => void;
}) {
  const sending = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reboot = async () => {
    if (sending.current) return;
    sending.current = true; setPending(true); setError(null);
    try {
      await api.reboot(serial);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "재부팅 명령을 보내지 못했습니다. 연결을 확인해 주세요.");
    } finally {
      sending.current = false; setPending(false);
    }
  };
  return <Toplevel title="폰 재부팅" width={430} onClose={pending ? undefined : onClose}>
    <p style={{ fontSize: 16, fontWeight: 500 }}>연결된 폰을 재부팅하시겠습니까?</p>
    <p className="c-gray">재부팅 중에는 단말 연결이 잠시 해제됩니다.</p>
    {error && <p role="alert" className="c-red">{error}</p>}
    {pending && <p role="status">재부팅 명령을 보내고 있습니다...</p>}
    <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
      <Button autoFocus disabled={pending} onClick={onClose}>취소</Button>
      <Button disabled={pending} onClick={() => void reboot()}>{pending ? "처리 중..." : "재부팅"}</Button>
    </div>
  </Toplevel>;
}
