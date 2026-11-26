import { useRef } from "react";
import { ApiError } from "../api/client";
import { usePlayAuth } from "../api/playAuthHooks";
import { Button, LabelFrame, Toplevel } from "./tk";
import { GeminiSettings } from "./GeminiSettings";
import { DeploymentSettings } from "./DeploymentSettings";

export function GooglePlaySettings({ onClose }: { onClose: () => void }) {
  const { status, upload, connect, check, disconnect } = usePlayAuth();
  const file = useRef<HTMLInputElement>(null);
  const data = status.data;
  const pending = data?.phase === "pending";
  const busy = upload.isPending || connect.isPending || check.isPending || disconnect.isPending;
  const error = upload.error ?? connect.error ?? check.error ?? disconnect.error ?? status.error;
  const clearErrors = () => { upload.reset(); connect.reset(); check.reset(); disconnect.reset(); };
  return <Toplevel title="설정 · Google Play / Gemini" width={600} onClose={onClose}>
    <DeploymentSettings />
    <LabelFrame text="Google Play 계정 연결">
      <p>LG유플러스 앱 버전 조회 계정: <strong>datasvcqa@gmail.com</strong></p>
      <p className="small">최초 한 번 Google Cloud에서 만든 ‘데스크톱 앱’ 클라이언트 JSON을 등록합니다.</p>
      <div className="row">
        <Button disabled={busy || pending} onClick={() => file.current?.click()}>클라이언트 파일 등록</Button>
        <span>{data?.client_configured ? "등록됨" : "등록 필요"}</span>
        <input ref={file} type="file" accept=".json,application/json" aria-label="OAuth 클라이언트 JSON" hidden
          onChange={(e) => {
            const selected = e.target.files?.[0];
            e.target.value = "";
            if (selected) { clearErrors(); upload.mutate(selected); }
          }} />
      </div>
      <p className="small">파일을 변경하면 이전 인증은 해제됩니다. 기존 클라이언트가 없으면 Google Cloud에서 생성해야 합니다.</p>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <Button disabled={busy || pending || !data?.client_configured} onClick={() => { clearErrors(); connect.mutate(); }}>
          {data?.credentials_saved ? "Google 계정 다시 연결" : "Google 계정 연결"}
        </Button>
        <Button disabled={busy || pending || !data?.credentials_saved} onClick={() => { clearErrors(); check.mutate(); }}>연결 확인</Button>
        <Button disabled={busy || (!data?.credentials_saved && !pending)} onClick={() => { clearErrors(); disconnect.mutate(); }}>
          {pending ? "로그인 취소" : "이 PC에서 연결 해제"}
        </Button>
      </div>
      <p role="status">{status.isPending ? "연결 상태 확인 중..." : data?.message}</p>
      {data?.credentials_saved && <p className="small c-gray">인증 정보는 현재 Windows 계정에 묶어 암호화 보관합니다. 연결 확인으로 앱 조회 권한을 확인할 수 있습니다.</p>}
      {pending && <p className="small">브라우저에서 datasvcqa@gmail.com 계정을 선택해 주세요. 이 창을 닫아도 로그인은 계속됩니다.</p>}
      {error && <p role="alert" className="c-red selectable">
        {error instanceof ApiError ? `${error.detail} (요청 ID: ${error.requestId ?? "-"})` : error.message}
      </p>}
    </LabelFrame>
    <GeminiSettings />
    <p className="small c-gray">앱 아이콘과 설치 버전은 단말에서 가져오므로 Google 인증 없이도 표시됩니다.</p>
    <div className="row" style={{ justifyContent: "flex-end" }}><Button onClick={onClose}>닫기</Button></div>
  </Toplevel>;
}
