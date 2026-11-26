import { ApiError } from "../api/client";
import { usePackageVersion, usePlayPackage } from "../api/hooks";
import { publishedReleases, releaseComparison } from "./playVersions";

function errorText(error: Error): string {
  return error instanceof ApiError
    ? `${error.detail}${error.requestId ? ` (요청 ID: ${error.requestId})` : ""}`
    : "버전 정보를 조회하지 못했습니다.";
}

export function AppVersions({ serial, pkg }: { serial: string; pkg: string }) {
  const installed = usePackageVersion(serial, pkg);
  const play = usePlayPackage(pkg);
  return <>
    <span className="small c-blue">
      {installed.isFetching ? "설치 버전 조회 중..." : installed.isError ? errorText(installed.error)
        : `📱 설치된 버전: ${installed.data?.version_name ?? "확인 불가"} (${installed.data?.version_code ?? "-"})`}
    </span>
    <span className={`small ${play.isError ? "c-gray" : "c-blue"}`}>
      {play.isFetching ? "Google Play 조회 중..." : play.isError ? `Google Play: ${errorText(play.error)}`
        : play.data ? `Google Play 정식 출시: ${releaseComparison(play.data, installed.isError || installed.isFetching ? null : installed.data?.version_code)}` : ""}
    </span>
    {play.data && !play.isError && !play.isFetching && <>
      {publishedReleases(play.data).map((r, i) => <span className="small" key={i}>
        출시 이름: {r.release_name || "미지정"} · 버전 코드: {r.version_codes.join(", ") || "없음"}
      </span>)}
      <span className="small c-gray">
        조회: {new Date(play.data.checked_at).toLocaleString()} · 단계 배포·중단된 출시가 포함될 수 있습니다.
        기기별 업데이트 제공 여부는 Play 스토어에서 확인하세요.
      </span>
    </>}
  </>;
}
