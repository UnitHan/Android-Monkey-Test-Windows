/** Keep connection/session UI state intact when browser reload shortcuts are pressed. */
export function installReloadGuard(target: Window = window): () => void {
  const onKey = (event: KeyboardEvent) => {
    const reload = event.key === "F5" || event.code === "F5"
      || ((event.ctrlKey || event.metaKey) && (event.code === "KeyR" || event.key.toLowerCase() === "r"));
    if (!reload) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  target.addEventListener("keydown", onKey, true);
  return () => target.removeEventListener("keydown", onKey, true);
}
