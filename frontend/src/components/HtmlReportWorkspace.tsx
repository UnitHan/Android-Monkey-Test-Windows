import { useQuery } from "@tanstack/react-query";
import { api, toApiError, type Session } from "../api/client";
import scrollStyles from "../scrollShadows.css?inline";

export function HtmlReportWorkspace({ session }: { session: Session | undefined }) {
  const report = useQuery({
    queryKey: ["html-report", session?.id, session?.state], enabled: !!session,
    queryFn: async () => {
      const response = await fetch(api.reportUrl(session!.id, "html"), { cache: "no-store" });
      if (!response.ok) throw await toApiError(response);
      return response.text();
    },
  });
  if (!session) return <div className="dashboard-empty">메인 패널에서 테스트 결과를 선택해 주세요.</div>;
  if (report.isLoading) return <div className="dashboard-empty" role="status">보고서를 불러오는 중...</div>;
  if (report.error) return <div className="dashboard-empty" role="alert">보고서를 열지 못했습니다: {report.error.message}
    <button className="tk-btn" onClick={() => void report.refetch()}>다시 시도</button></div>;
  const html = (report.data ?? "")
    .replace("<head>", '<head><base href="about:srcdoc">')
    .replace("</head>", `<style>${scrollStyles}</style></head>`);
  return <div className="html-report-view">
    <div className="html-report-toolbar"><button className="tk-btn" disabled={report.isFetching}
      onClick={() => void report.refetch()}>{report.isFetching ? "갱신 중..." : "보고서 새로고침"}</button></div>
    <iframe className="html-report-frame" title="Monkey 테스트 HTML 보고서" sandbox="" srcDoc={html} />
  </div>;
}
