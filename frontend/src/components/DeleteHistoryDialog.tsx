import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api, type Session } from "../api/client";
import { keys, TERMINAL } from "../api/hooks";
import { Button, Toplevel } from "./tk";

export function DeleteHistoryDialog({ session, onClose, onDeleted }: {
  session: Session; onClose: () => void; onDeleted: (id: string) => void;
}) {
  const qc = useQueryClient();
  const sending = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = TERMINAL.has(session.state) || session.state === "created";
  const remove = async () => {
    if (sending.current || !allowed) return;
    sending.current = true; setPending(true); setError(null);
    try {
      await api.deleteSession(session.id);
      await qc.cancelQueries({ predicate: q => q.queryKey.includes(session.id) });
      qc.setQueryData<Session[]>(keys.sessions, old => old?.filter(s => s.id !== session.id));
      onDeleted(session.id);
      qc.removeQueries({ predicate: q => q.queryKey.includes(session.id) });
      void qc.invalidateQueries({ queryKey: keys.sessions });
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally { sending.current = false; setPending(false); }
  };
  return <Toplevel title="이전 결과 완전 삭제" width={510} onClose={pending ? undefined : onClose}>
    <p className="bold">선택한 테스트 기록을 완전히 삭제하시겠습니까?</p>
    <p style={{ overflowWrap: "anywhere" }}>{session.config.package}<br />
      {new Date(session.created_at).toLocaleString("ko-KR")}<br /><small>{session.id}</small></p>
    <p>테스트 결과, 회차별 로그, 성능 데이터, AI 분석 및 저장된 보고서를 삭제합니다. 복구할 수 없습니다.</p>
    <p className="small c-gray">앱에서 내보낸 기본 위치의 엑셀도 삭제됩니다. 다른 곳에 복사하거나 이름을 바꾼 파일은 남습니다.</p>
    {!allowed && <p role="alert">진행 중인 테스트는 삭제할 수 없습니다.</p>}
    {error && <p role="alert" className="c-red">{error}</p>}
    <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
      <Button autoFocus disabled={pending} onClick={onClose}>취소</Button>
      <Button className="c-red" disabled={pending || !allowed} onClick={() => void remove()}>{pending ? "삭제 중..." : "완전 삭제"}</Button>
    </div>
  </Toplevel>;
}
