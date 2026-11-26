import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { Button, LabelFrame } from "./tk";

export function DeploymentSettings() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["deployment-settings"], queryFn: api.deploymentStatus, retry: false });
  const [password, setPassword] = useState("");
  const unlock = useMutation({ mutationFn: api.unlockDeployment, gcTime: 0, onSuccess: () => {
    setPassword(""); void qc.invalidateQueries();
  } });
  if (!status.data?.available) return null;
  return <LabelFrame text="설치 패키지에 포함된 기존 설정">
    <p>Google 계정: <strong>{status.data.account}</strong> · Google 로그인과 Gemini 키 포함</p>
    {status.data.configured ? <p role="status">이 PC에 설정이 저장되어 있습니다. 기존 인증 정보를 유지합니다.</p> : <>
      <p className="small">최초 한 번 배포 암호를 입력하면 등록된 인증 정보를 복원합니다. Google 토큰이 만료·철회된 경우에만 다시 로그인합니다.</p>
      <div className="row">
        <input type="password" aria-label="배포 암호" autoComplete="off" value={password}
          style={{ flex: 1, minWidth: 150 }} maxLength={512} placeholder="배포 암호"
          onChange={(e) => setPassword(e.target.value)} disabled={unlock.isPending} />
        <Button disabled={!password || unlock.isPending} onClick={() => unlock.mutate(password)}>
          {unlock.isPending ? "복원 중..." : "기존 설정 복원"}
        </Button>
      </div>
    </>}
    {unlock.error && <p role="alert" className="c-red">{unlock.error.message}</p>}
  </LabelFrame>;
}
