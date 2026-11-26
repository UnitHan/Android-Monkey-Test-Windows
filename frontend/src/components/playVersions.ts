import type { PlayPackage } from "../api/client";

export function publishedReleases(data: PlayPackage) {
  return data.releases.filter((r) => r.lifecycle_state === "RELEASE_LIFECYCLE_STATE_PUBLISHED");
}

/** Release codes are metadata, not proof that this device is eligible for an update. */
export function releaseComparison(data: PlayPackage, installed: string | null | undefined): string {
  const codes = publishedReleases(data).flatMap((r) => r.version_codes).filter((c) => /^\d+$/.test(c)).map(BigInt);
  if (!codes.length) return "출시된 버전 코드 없음";
  if (!installed || !/^\d+$/.test(installed)) return "설치 버전 코드 확인 필요";
  const current = BigInt(installed);
  if (codes.some((c) => c > current)) return "더 높은 출시 버전 코드 있음";
  if (codes.includes(current)) return "출시 버전 코드와 일치";
  return "설치 버전 코드가 조회된 출시 버전보다 높음";
}
