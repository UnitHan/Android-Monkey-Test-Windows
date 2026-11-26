# v3 (legacy) → v4 migration notes

v3 source: `legacy/` and git tag `legacy-v3.0`.

## Where things went

| v3 | v4 |
|---|---|
| `src/ui/*` (tkinter, ~7k lines) | `frontend/src/*` (React) |
| `src/core/monkey_runner.py` (3.3k lines, 63 methods) | `services/session_runner.py`, `services/run_executor.py`, `services/collectors.py`, `domain/*` |
| `src/core/adb_client.py` | `adapters/adb/runner.py` (process), `adapters/adb/parsers.py` (pure), `adapters/adb/device_ops.py` |
| `src/config.py` PRESETS + hard-coded per-preset branches | `domain/presets.py` (one table) |
| `config.calculate_precise_duration` | `domain/estimation.py` |
| `_calculate_adaptive_events` (270 lines × 5 presets) | `domain/adaptive.py::next_run_events` |
| `_read_logcat` | `domain/logcat_analyzer.py` + `services/collectors.collect_logcat` |
| `network_monitor.py`, `app_foreground_monitor.py`, `async_background_monitor` | `services/collectors.guard_app_state` |
| `report_generator.py`, `chart_generator*.py` (matplotlib) | `domain/report.py`, `adapters/report/html.py`, `adapters/report/excel.py` |
| `gemini_adaptive_controller.py`, `adaptive_tuner.py` | `adapters/ai/advisor.py` (optional, bounded) |
| `test_context.py` + callbacks + shared flags | `SessionLedger` + state machine + event log + SSE |
| `apps.json` | `backend/src/monkey_api/data/apps.json` |
| logs/*.log text files | structured API logs: `GET /api/v1/logs`, `data/logs/api.jsonl` |

## Behaviour changes (intentional)

- **Crash detection fixed**: v3 required the package name on the keyword line; `FATAL EXCEPTION: main`
  never contains it, so most Java crashes were missed. v4 reads the `Process:` line of the block.
- **Short crash/ANR blocks kept**: v3 dropped blocks with < 20 lines at run end; v4 flushes them.
- **Native crashes** detected from tombstone `>>> pkg <<<` lines (new issue kind `native_crash`).
- **logcat files** contain real newlines (v3 wrote a literal `\n`).
- **Time limit for every preset with a target** (v3 enforced it for Deep Test only).
- **Preset values unified** to what v3 actually executed (e.g. Deep throttle 150 ms, Extreme 180 ms,
  fixed seed 4850), not the unused `config.PRESETS` numbers.
- **Network guard** uses the configured adb (v3 called bare `adb`, ignoring the bundled path).
- **Gemini**: key sent in `x-goog-api-key` header (v3 put it in the URL), model configurable,
  suggestions clamped to the same bounds as the algorithm; works fully without a key.
- **Event counting** uses monkey's `// Sending event #N` / `Events injected:` (v3 counted every
  `:Sending` line, double-counting DOWN/UP pairs).
- **One active session per device** (409 `device_busy`).

## Dropped

- matplotlib/seaborn/pandas/numpy/scipy chart pipeline (charts are rendered in the browser).
- Play Store scraping (`app_info_fetcher.py`): fragile HTML scraping; display names come from the
  bundled catalog and installed version from `dumpsys package`. Can be re-added as an adapter.
- Custom font installation (web UI uses system fonts).
- PyInstaller spec. Packaging target is Tauri (see ARCHITECTURE.md §1).
