/** v3 "앱 검색 및 선택" dialog. */
import { useEffect, useState } from "react";
import type { PackageItem } from "../api/client";
import { usePackages } from "../api/hooks";
import { Button, Entry, LabelFrame, Toplevel } from "./tk";

export const appLabel = (p: PackageItem) => (p.display_name === p.name ? p.name : `${p.display_name} (${p.name})`);

export function AppSelectDialog(props: {
  serial: string;
  initialQuery?: string;
  current: PackageItem | null;
  onSelect: (p: PackageItem) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState(props.initialQuery ?? "");
  const [debounced, setDebounced] = useState(query);
  const [cursor, setCursor] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 200);
    return () => clearTimeout(t);
  }, [query]);
  const packages = usePackages(props.serial, debounced, false);
  const items = packages.data?.items ?? [];
  useEffect(() => setCursor(0), [debounced]);

  const choose = (p: PackageItem | undefined) => {
    if (!p) return;
    props.onSelect(p);
    props.onClose();
  };

  return (
    <Toplevel title="앱 검색 및 선택" width={560} height={560} onClose={props.onClose}>
      <div style={{ marginBottom: 6 }}>
        <div className="bold" style={{ fontSize: 15 }}>📱 설치된 앱 목록</div>
        <div className="c-gray small">
          {packages.isLoading ? "목록을 불러오는 중..." : `총 ${packages.data?.total ?? 0}개 앱`}
        </div>
      </div>
      <LabelFrame text="🔍 검색">
        <Entry
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setCursor((c) => Math.min(items.length - 1, c + 1));
            if (e.key === "ArrowUp") setCursor((c) => Math.max(0, c - 1));
            if (e.key === "Enter") choose(items[cursor]);
          }}
          style={{ width: "100%", fontSize: 14, height: 28 }}
        />
        <div className="c-gray small" style={{ marginTop: 2 }}>앱 이름이나 패키지명을 입력하여 검색하세요 (1글자부터 검색)</div>
      </LabelFrame>
      <LabelFrame text="📋 앱 목록" className="grow" style={{ display: "flex", flexDirection: "column", marginTop: 6 }}>
        <div className="tk-listbox grow" role="listbox" tabIndex={0} style={{ minHeight: 160 }}>
          {items.map((p, i) => (
            <div
              key={p.name}
              role="option"
              aria-selected={i === cursor}
              onClick={() => setCursor(i)}
              onDoubleClick={() => choose(p)}
            >
              {appLabel(p)}
            </div>
          ))}
          {!packages.isLoading && items.length === 0 && <div>검색 결과가 없습니다.</div>}
          {packages.error && <div className="c-red">오류 발생: {String(packages.error)}</div>}
        </div>
      </LabelFrame>
      {props.current && (
        <div className="row" style={{ marginTop: 6 }}>
          <span className="c-blue">현재 선택:</span>
          <span className="c-blue bold">{appLabel(props.current)}</span>
        </div>
      )}
      <div className="row" style={{ justifyContent: "center", marginTop: 8 }}>
        <Button onClick={() => choose(items[cursor])} disabled={!items[cursor]}>✅ 선택</Button>
        <Button onClick={props.onClose}>❌ 취소</Button>
      </div>
    </Toplevel>
  );
}
