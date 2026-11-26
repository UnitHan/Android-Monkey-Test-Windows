/** v3 "앱 검색 및 선택" dialog. */
import { useEffect, useRef, useState } from "react";
import type { PackageItem } from "../api/client";
import { usePackages } from "../api/hooks";
import { Button, Entry, LabelFrame, Toplevel } from "./tk";
import { SearchHighlight } from "./SearchHighlight";
import { AppIcon } from "./AppIcon";

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
  const [includeSystem, setIncludeSystem] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 200);
    return () => clearTimeout(t);
  }, [query]);
  const packages = usePackages(props.serial, debounced, includeSystem);
  const items = packages.data?.items ?? [];
  const pending = query !== debounced || packages.isFetching;
  const active = Math.max(0, Math.min(cursor, items.length - 1));
  useEffect(() => setCursor(0), [debounced, includeSystem]);
  useEffect(() => {
    list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ block: "nearest" });
  }, [active, packages.data]);

  const choose = (p: PackageItem | undefined) => {
    if (!p || pending) return;
    props.onSelect(p);
    props.onClose();
  };

  return (
    <Toplevel title="앱 검색 및 선택" width={640} height={600} onClose={props.onClose}>
      <div style={{ marginBottom: 6 }}>
        <div className="bold" style={{ fontSize: 15 }}>📱 설치된 앱 목록</div>
        <div className="c-gray small">
          {pending ? "검색 중..." : `${debounced.trim() ? "검색 결과" : "설치된 앱"} ${packages.data?.total ?? 0}개`}
        </div>
      </div>
      <LabelFrame text="🔍 검색">
        <Entry
          autoFocus
          aria-label="앱 이름·패키지·초성 검색"
          placeholder="예: 익시오, ㅇㅅㅇ, 블라인드, com.lguplus"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229) return;
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor(Math.min(Math.max(0, items.length - 1), active + 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor(Math.max(0, active - 1)); }
            if (e.key === "Enter") { e.preventDefault(); choose(items[active]); }
          }}
          style={{ width: "100%", fontSize: 14, height: 28 }}
        />
        <div className="c-gray small" style={{ marginTop: 4 }}>앱 이름·패키지·초성·한글 발음으로 검색합니다. ↑↓ 이동 · Enter 선택</div>
        <label className="small" style={{ display: "block", marginTop: 6 }}>
          <input type="checkbox" checked={includeSystem} onChange={(e) => setIncludeSystem(e.target.checked)} /> 실행 아이콘 없는 패키지도 포함
        </label>
      </LabelFrame>
      <LabelFrame text="📋 앱 목록" className="grow" style={{ display: "flex", flexDirection: "column", minHeight: 0, marginTop: 6 }}>
        <div ref={list} className="tk-listbox app-search-list grow" role="listbox" aria-label="검색된 앱" aria-busy={pending}
          tabIndex={0} style={{ minHeight: 160 }} onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor(Math.min(Math.max(0, items.length - 1), active + 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor(Math.max(0, active - 1)); }
            if (e.key === "Enter") { e.preventDefault(); choose(items[active]); }
          }}>
          {items.map((p, i) => (
            <div
              key={p.name}
              role="option"
              aria-selected={i === active}
              onClick={() => setCursor(i)}
              onDoubleClick={() => choose(p)}
            >
              <AppIcon serial={props.serial} pkg={p.name} size={40} lazy label={p.display_name} />
              <span className="app-search-label">
                <strong><SearchHighlight text={p.display_name} query={debounced} /></strong>
                <span className="app-search-package"><SearchHighlight text={p.name} query={debounced} /></span>
              </span>
            </div>
          ))}
          {!pending && !packages.error && items.length === 0 && <div>검색 결과가 없습니다. 앱 이름이나 초성으로 다시 검색해 보세요.</div>}
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
        <Button onClick={() => choose(items[active])} disabled={pending || !items[active]}>✅ 선택</Button>
        <Button onClick={props.onClose}>❌ 취소</Button>
      </div>
    </Toplevel>
  );
}
