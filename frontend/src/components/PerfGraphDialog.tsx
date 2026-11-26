/** v3 "성능 그래프 보기" window (1000x700): memory and CPU, one measure per chart. */
import type { Session } from "../api/client";
import { usePerf } from "../api/hooks";
import { PerfChart } from "./PerfChart";
import { Button, Toplevel } from "./tk";

export function PerfGraphDialog({ session, onClose }: { session: Session; onClose: () => void }) {
  const perf = usePerf(session.id);
  const samples = perf.data ?? [];
  return (
    <Toplevel title="성능 그래프 보기" width={1000} height={700} onClose={onClose}>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="bold" style={{ fontSize: 15 }}>{session.config.package} 성능 그래프</span>
        <span className="c-gray small">
          {samples.length}개 측정 · {session.runs.length}/{session.config.repeats}회차
        </span>
      </div>
      {samples.length === 0 ? (
        <div className="c-gray" style={{ textAlign: "center", marginTop: 80, whiteSpace: "pre-line" }}>
          {"표시할 성능 데이터가 없습니다.\n테스트를 실행하고 완료한 후 다시 시도해주세요."}
        </div>
      ) : (
        <div className="charts">
          <PerfChart samples={samples} metric="memory_mb" title="메모리 사용량" unit="MB" color="var(--s1)" />
          <PerfChart samples={samples} metric="cpu_percent" title="CPU 사용량" unit="%" color="var(--s2)" fixedMax={100} />
        </div>
      )}
      <span className="grow" />
      <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
        <Button onClick={onClose}>닫기</Button>
      </div>
    </Toplevel>
  );
}
