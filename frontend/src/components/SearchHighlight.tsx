/** Presentation-only literal/initial highlights, adapted from Appkium SearchHighlight. */
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";

export function highlightRange(text: string, query: string): [number, number] | null {
  const q = query.trim();
  if (!q) return null;
  const at = text.toLowerCase().indexOf(q.toLowerCase());
  if (at >= 0) return [at, at + q.length];
  if (![...q].every((c) => CHO.includes(c) || /\s/.test(c))) return null;
  const initials = q.replace(/\s/g, "");
  const indexed: { at: number; value: string }[] = [];
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code >= 0xac00 && code <= 0xd7a3) indexed.push({ at: i, value: CHO[Math.floor((code - 0xac00) / 588)] });
    else if (CHO.includes(text[i])) indexed.push({ at: i, value: text[i] });
  }
  const hit = indexed.map((entry) => entry.value).join("").indexOf(initials);
  return hit >= 0 && initials ? [indexed[hit].at, indexed[hit + initials.length - 1].at + 1] : null;
}

export function SearchHighlight({ text, query }: { text: string; query: string }) {
  const range = highlightRange(text, query);
  if (!range) return <>{text}</>;
  return <>{text.slice(0, range[0])}<mark>{text.slice(...range)}</mark>{text.slice(range[1])}</>;
}
