/** Small React equivalents of the ttk widgets v3 used, styled in styles.css (clam theme). */
import { useEffect, type ReactNode } from "react";

export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { sunken?: boolean }) {
  const { sunken, className, ...rest } = props;
  return <button type="button" {...rest} className={`tk-btn${sunken ? " sunken" : ""} ${className ?? ""}`} />;
}

export function Entry(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`tk-entry ${props.className ?? ""}`} />;
}

export function Radio(props: { checked: boolean; onChange: () => void; children: ReactNode; name: string }) {
  return (
    <label className="tk-radio">
      <input type="radio" name={props.name} checked={props.checked} onChange={props.onChange} />
      {props.children}
    </label>
  );
}

export function LabelFrame(props: { text: ReactNode; children: ReactNode; style?: React.CSSProperties; className?: string }) {
  return (
    <fieldset className={`tk-lf ${props.className ?? ""}`} style={props.style}>
      <legend>{props.text}</legend>
      {props.children}
    </fieldset>
  );
}

export function Progressbar({ value, indeterminate }: { value: number; indeterminate?: boolean }) {
  return (
    <div className={`tk-progress${indeterminate ? " indeterminate" : ""}`} role="progressbar" aria-valuenow={value}>
      <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Notebook<T extends string>(props: {
  tabs: { id: T; label: string }[];
  active: T;
  onSelect: (id: T) => void;
  extra?: ReactNode;
  children: ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div className="tk-notebook" style={props.style}>
      <div className="tk-tabs" role="tablist">
        {props.tabs.map((t) => (
          <div key={t.id} role="tab" className="tk-tab" aria-selected={props.active === t.id} onClick={() => props.onSelect(t.id)}>
            {t.label}
          </div>
        ))}
        <div className="grow" />
        {props.extra}
      </div>
      <div className="tk-tabpanel" role="tabpanel">{props.children}</div>
    </div>
  );
}

/** tk.Toplevel-like modal window with its own title bar. */
export function Toplevel(props: {
  title: string;
  width: number;
  height?: number;
  onClose?: () => void;
  opaque?: boolean;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!props.onClose) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && props.onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.onClose]);
  return (
    <div className={`tk-modal${props.opaque ? " opaque" : ""}`}>
      <div className="tk-toplevel" role="dialog" aria-label={props.title} style={{ width: props.width, height: props.height }}>
        <div className="tk-titlebar">
          <img src="/favicon.png" alt="" />
          <span>{props.title}</span>
          {props.onClose && <button aria-label="닫기" onClick={props.onClose}>×</button>}
        </div>
        <div className="tk-body col">{props.children}</div>
      </div>
    </div>
  );
}

export function MessageBox(props: { title: string; message: string; kind: "info" | "error"; onClose: () => void }) {
  return (
    <Toplevel title={props.title} width={320} onClose={props.onClose}>
      <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
        <span style={{ fontSize: 22 }}>{props.kind === "error" ? "❌" : "ℹ️"}</span>
        <div className="selectable" style={{ whiteSpace: "pre-wrap" }}>{props.message}</div>
      </div>
      <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
        <Button autoFocus onClick={props.onClose} style={{ minWidth: 80 }}>확인</Button>
      </div>
    </Toplevel>
  );
}
