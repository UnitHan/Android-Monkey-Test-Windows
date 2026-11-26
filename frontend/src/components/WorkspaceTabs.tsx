import type { KeyboardEvent } from "react";
import { Button } from "./tk";

export type Workspace = "main" | "console" | "performance" | "results" | "report";
const TABS: { id: Workspace; label: string }[] = [
  { id: "main", label: "메인 패널" },
  { id: "console", label: "콘솔 로그" },
  { id: "performance", label: "성능 모니터" },
  { id: "results", label: "테스트 결과" },
  { id: "report", label: "HTML 보고서" },
];

export function WorkspaceTabs(props: {
  active: Workspace;
  onSelect: (tab: Workspace) => void;
  onSettings: () => void;
}) {
  const navigate = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const target = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1
      : event.key === "ArrowRight" ? (index + 1) % TABS.length
      : event.key === "ArrowLeft" ? (index + TABS.length - 1) % TABS.length : null;
    if (target === null) return;
    event.preventDefault();
    props.onSelect(TABS[target].id);
    document.getElementById(`workspace-tab-${TABS[target].id}`)?.focus();
  };

  return (
    <div className="workspace-toolbar">
      <div className="workspace-tabs" role="tablist" aria-label="작업 화면">
        {TABS.map((tab, index) => (
          <button key={tab.id} type="button" role="tab" className="workspace-tab"
            id={`workspace-tab-${tab.id}`} aria-controls={`workspace-${tab.id}`}
            aria-selected={props.active === tab.id} tabIndex={props.active === tab.id ? 0 : -1}
            onClick={() => props.onSelect(tab.id)} onKeyDown={(event) => navigate(event, index)}>
            {tab.label}
          </button>
        ))}
      </div>
      <Button onClick={props.onSettings}>설정</Button>
    </div>
  );
}
