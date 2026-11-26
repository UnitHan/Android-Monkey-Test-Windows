import { describe, expect, it } from "vitest";
import type { PlayPackage } from "../api/client";
import { releaseComparison } from "./playVersions";

function data(codes: string[], state = "RELEASE_LIFECYCLE_STATE_PUBLISHED"): PlayPackage {
  return {
    package: "com.lguplus.aicallagent", source: "google_play_developer_api", track: "production",
    checked_at: "2026-11-26T00:00:00Z",
    releases: [{ release_name: "Any label", lifecycle_state: state, version_codes: codes }],
  };
}

describe("Play release comparison", () => {
  it("compares numeric codes, not strings or release names", () => {
    expect(releaseComparison(data(["100"]), "99")).toBe("더 높은 출시 버전 코드 있음");
    expect(releaseComparison(data(["99"]), "100")).toBe("설치 버전 코드가 조회된 출시 버전보다 높음");
  });
  it("does not equate an installed code match with latest when higher codes exist", () => {
    expect(releaseComparison(data(["99", "100"]), "99")).toBe("더 높은 출시 버전 코드 있음");
    expect(releaseComparison(data(["99", "100"]), "100")).toBe("출시 버전 코드와 일치");
  });
  it.each(["RELEASE_LIFECYCLE_STATE_IN_REVIEW", "RELEASE_LIFECYCLE_STATE_APPROVED_NOT_PUBLISHED", "FUTURE_STATE"])(
    "excludes unpublished or unknown lifecycle %s", (state) => {
      expect(releaseComparison(data(["999"], state), "1")).toBe("출시된 버전 코드 없음");
    },
  );
  it("handles missing data without recommending an update", () => {
    expect(releaseComparison(data([]), "99")).toBe("출시된 버전 코드 없음");
    expect(releaseComparison(data(["100"]), null)).toBe("설치 버전 코드 확인 필요");
    expect(releaseComparison(data(["100"]), "unknown")).toBe("설치 버전 코드 확인 필요");
  });
  it("does not lose precision on large version codes", () => {
    expect(releaseComparison(data(["9007199254740993"]), "9007199254740992")).toBe("더 높은 출시 버전 코드 있음");
  });
});
