import { useSessions } from "../api/hooks";
import { StateBadge, fmtTime } from "./common";

export function SessionList(props: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { data } = useSessions();
  return (
    <section className="card">
      <h2>세션</h2>
      <ul className="list" style={{ maxHeight: 360 }}>
        {data?.map((s) => (
          <li key={s.id}>
            <button aria-pressed={props.selectedId === s.id} onClick={() => props.onSelect(s.id)}>
              <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                {s.config.package}
                <span className="muted small"> · {s.config.preset_id} · {fmtTime(s.created_at)}</span>
              </span>
              <StateBadge state={s.state} />
            </button>
          </li>
        ))}
        {data?.length === 0 && <li className="muted small">아직 세션이 없습니다.</li>}
      </ul>
    </section>
  );
}
