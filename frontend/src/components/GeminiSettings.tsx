import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { Button, LabelFrame } from "./tk";

export function GeminiSettings() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["ai-settings"], queryFn: api.aiSettings });
  const [key, setKey] = useState("");
  const [message, setMessage] = useState("");
  const save = useMutation({ mutationFn: api.saveAiSettings, onSuccess: (data) => {
    setKey(""); setMessage("암호화 저장 완료. 바로 사용할 수 있습니다.");
    qc.setQueryData(["ai-settings"], data); void qc.invalidateQueries({ queryKey: ["health"] });
    void qc.invalidateQueries({ queryKey: ["performance-preview"] });
  } });
  const remove = useMutation({ mutationFn: api.deleteAiSettings, onSuccess: (data) => {
    setKey(""); setMessage("이 PC에 저장한 Gemini 키를 삭제했습니다.");
    qc.setQueryData(["ai-settings"], data); void qc.invalidateQueries({ queryKey: ["health"] });
    void qc.invalidateQueries({ queryKey: ["performance-preview"] });
  } });
  const busy = save.isPending || remove.isPending;
  const error = save.error ?? remove.error ?? status.error;
  return <LabelFrame text="Gemini API 설정">
    <p>{status.data?.configured ? "API 키 등록됨" : "API 키 등록 필요"} · {status.data?.model ?? "Gemini"}</p>
    <div className="row" style={{ flexWrap: "wrap" }}>
      <input type="password" aria-label="Gemini API 키" autoComplete="off" spellCheck={false}
        style={{ flex: 1, minWidth: 180 }} value={key} placeholder="새 API 키 입력" maxLength={512}
        onChange={(e) => { setKey(e.target.value); setMessage(""); }} />
      <Button disabled={busy || !key.trim()} onClick={() => {
        save.reset(); remove.reset(); save.mutate({ api_key: key.trim(), model: status.data?.model ?? "gemini-3.5-flash-lite" });
      }}>암호화 저장</Button>
      <Button disabled={busy || !status.data?.configured} onClick={() => {
        save.reset(); remove.reset(); remove.mutate();
      }}>키 삭제</Button>
    </div>
    <p className="small c-gray">현재 Windows 계정으로만 열 수 있도록 암호화합니다. 저장 시 Gemini를 호출하지 않습니다.</p>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="c-red">{error.message}</p>}
  </LabelFrame>;
}
