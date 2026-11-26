import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Schemas } from "../api/client";
import { Button, Toplevel } from "./tk";

const labels = { normal: "관측 범위 정상", attention: "주의", abnormal: "이상 징후", inconclusive: "판단 보류" };
type Analysis = Schemas["PerformanceAnalysis"];

export function AIResult({ result }: { result: Analysis }) {
  const c = result.conclusion;
  return <div className="ai-performance-result">
    <strong className={`ai-verdict ${c.verdict}`}>{labels[c.verdict]}</strong>
    <p>{c.summary}</p>
    <div className="resource-findings">{([['memory', '메모리'], ['cpu', 'CPU'], ['stability', '안정성']] as const).map(([key, label]) =>
      <article className="resource-finding" key={key}><h3>{label} · {labels[c[key].verdict]}</h3><p>{c[key].reason}</p></article>)}</div>
    <strong>권고사항</strong><ul>{c.recommendations.map((s, i) => <li key={i}>{s}</li>)}</ul>
    <details><summary>판정의 한계와 검증 조건</summary><ul>{[...c.limitations, ...(result.guardrails ?? [])].map((s, i) => <li key={i}>{s}</li>)}</ul></details>
    <p className="small c-gray">{result.model} · {new Date(result.created_at).toLocaleString()} · 관측 범위의 AI 해석이며 출시 합격 판정은 아닙니다.</p>
  </div>;
}

function AnalysisDialog({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [consent, setConsent] = useState(false);
  const qc = useQueryClient();
  const preview = useQuery({ queryKey: ["performance-preview", sessionId], queryFn: () => api.performancePreview(sessionId), staleTime: 0 });
  useEffect(() => setConsent(false), [preview.data?.input_hash]);
  const analyze = useMutation({
    mutationFn: (hash: string) => api.analyzePerformance(sessionId, hash),
    onError: error => {
      if (error instanceof ApiError && error.status === 409) {
        setConsent(false);
        void preview.refetch();
      }
    },
    onSuccess: async () => {
      await Promise.all([qc.invalidateQueries({ queryKey: ["report", sessionId] }), qc.invalidateQueries({ queryKey: ["html-report", sessionId] })]);
      onClose();
    },
  });
  return <Toplevel title="Gemini 성능 분석 · 전송 내용 확인" width={760} height={650} onClose={analyze.isPending ? undefined : onClose}>
    <p>성능 통계·회차별 변화·크래시/ANR 건수를 Gemini에 전송합니다. 원본 로그, 앱 패키지명, 기기 식별번호와 계정 정보는 포함하지 않습니다.</p>
    <p className="small c-gray">모델: {preview.data?.model ?? "확인 중"} · 회사에서 승인한 API 프로젝트를 사용하세요.</p>
    {preview.isLoading && <p role="status">전송할 통계를 준비하는 중...</p>}
    {preview.error && <p role="alert">{preview.error.message}</p>}
    {preview.data && <>
      {!preview.data.configured && <p role="alert">상단 설정 메뉴에서 Gemini API 키를 등록해 주세요.</p>}
      <pre className="ai-preview" tabIndex={0} aria-label="Gemini 전송 통계">{JSON.stringify(preview.data.evidence, null, 2)}</pre>
      <label><input type="checkbox" checked={consent} disabled={analyze.isPending} onChange={e => setConsent(e.target.checked)} /> 위 통계를 Gemini에 전송하여 분석하는 데 동의합니다.</label>
    </>}
    {analyze.error && <p role="alert">{analyze.error.message} 기존 통계는 계속 사용할 수 있습니다.</p>}
    {analyze.isPending && <p role="status">Gemini가 통계와 관측 근거를 분석하고 있습니다...</p>}
    <div className="row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
      <Button disabled={analyze.isPending} onClick={onClose}>취소</Button>
      <Button disabled={!consent || !preview.data?.configured || preview.isFetching || analyze.isPending}
        onClick={() => preview.data && analyze.mutate(preview.data.input_hash)}>동의하고 분석</Button>
    </div>
  </Toplevel>;
}

export function AIPerformance({ report }: { report: Schemas["SessionReport"] }) {
  const [open, setOpen] = useState(false);
  return <section className="ai-performance">
    <div className="resource-heading"><strong>Gemini 성능 판정</strong>
      <Button onClick={() => setOpen(true)}>{report.ai_performance ? "분석 내용 확인 / 재요청" : "AI 성능 분석"}</Button></div>
    {report.ai_performance ? <AIResult result={report.ai_performance} />
      : <p className="small c-gray">통계와 관측 근거로 정상 여부를 해석합니다. 버튼을 눌러 전송 내용을 확인한 뒤 분석을 실행하세요.</p>}
    {open && <AnalysisDialog sessionId={report.session.id} onClose={() => setOpen(false)} />}
  </section>;
}
