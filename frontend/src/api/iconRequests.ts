/** Bound HTTP work as well as device extraction; discard requests whose rows were unmounted. */
type Job = { start: () => void; signal: AbortSignal; cancel: () => void };
const waiting: Job[] = [];
let active = 0;
const LIMIT = 2;

function drain() {
  while (active < LIMIT && waiting.length) {
    const job = waiting.shift()!;
    job.signal.removeEventListener("abort", job.cancel);
    if (job.signal.aborted) { job.cancel(); continue; }
    job.start();
  }
}

export function scheduleIcon<T>(load: () => Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const job: Job = {
      signal,
      cancel: () => {
        const index = waiting.indexOf(job);
        if (index >= 0) waiting.splice(index, 1);
        reject(new DOMException("Icon request cancelled", "AbortError"));
      },
      start: () => {
        active++;
        Promise.resolve().then(load).then(resolve, reject).finally(() => { active--; drain(); });
      },
    };
    if (signal.aborted) { job.cancel(); return; }
    waiting.push(job);
    signal.addEventListener("abort", job.cancel, { once: true });
    drain();
  });
}
