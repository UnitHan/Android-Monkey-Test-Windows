import { expect, it } from "vitest";
import { highlightRange } from "./SearchHighlight";

it("highlights literal and initial matches without inventing phonetic character ranges", () => {
  expect(highlightRange("모바일매니저", "모")).toEqual([0, 1]);
  expect(highlightRange("카카오톡", "ㅋㅋ")).toEqual([0, 2]);
  expect(highlightRange("U+tv모바일", "ㅁㅂㅇ")).toEqual([4, 7]);
  expect(highlightRange("📱 카카오톡", "ㅋ ㅋ")).toEqual([3, 5]);
  expect(highlightRange("blind", "블")).toBeNull();
  expect(highlightRange("com.lguplus.remocon", "REMOCON")).toEqual([12, 19]);
});
