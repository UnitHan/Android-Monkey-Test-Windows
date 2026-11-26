# Monkey Test Platform — Architecture

Status: accepted (2026-11-26). Supersedes the Python/tkinter tool preserved in Git tag `legacy-v3.0`.
Only the current application sources are kept in the working tree.

## 1. Goals

- Every capability exposed as a **versioned REST API** (`/api/v1`). UI is just one client.
- **Server is the single source of truth** for state. Clients never hold authoritative state.
- **Contract-first**: OpenAPI document (`backend/openapi.json`) is the contract. Tests fail on drift.
- **Observable by API**: every request, ADB call and session event is a structured log record,
  queryable through `/api/v1/logs`. Any failure can be traced from `request_id` → logs.
- Layered so the backend can later be re-implemented in Rust (axum/Tauri) against the same contract.

## 2. Layers

```
frontend (React)  ──HTTP/SSE──▶  api (FastAPI routers, schemas, error mapping)
                                   │
                                   ▼
                                services (use cases, orchestration, event bus)
                                   │
                    ┌──────────────┼───────────────┐
                    ▼              ▼               ▼
                 domain        adapters          core
           (pure logic,     (adb, storage,   (settings, logging,
            no I/O)          ai, reports)     errors)
```

Dependency rule: `api → services → domain`, `services → adapters → domain`. `domain` imports nothing
from other layers. `core` is importable by all.

| Layer | Package | Responsibility |
|---|---|---|
| api | `monkey_api.api` | HTTP routing, request/response schemas, problem+json errors, request logging middleware |
| services | `monkey_api.services` | `DeviceService`, `PackageService`, `SessionService` (commands), `SessionRunner` (execution), `EventBus` |
| domain | `monkey_api.domain` | models, presets, session state machine, monkey command builder, logcat analyzer, monkey output parser, estimation, adaptive tuning, analysis |
| adapters | `monkey_api.adapters` | `AdbRunner` (async subprocess), ADB output parsers, `SessionRepository` (JSON files), report writers (HTML/XLSX), tuning advisor (Gemini) |
| core | `monkey_api.core` | `Settings` (env), structured logging + log store, error hierarchy, ids/clock |

## 3. State management

### 3.1 Server side — session aggregate + event log

A test session is an aggregate with an explicit state machine:

```
created ──start──▶ preparing ──▶ running ──▶ completed
   │                  │            │  │
   │                  │            │  └─error──▶ failed
   │                  └──error─────┼──────────▶ failed
   └──cancel──▶ cancelled ◀─stop── stopping ◀──stop── running
```

- Transitions are defined once in `domain/state_machine.py`. Illegal transition → `409 Conflict`.
- Every state change / progress / issue is a **SessionEvent** `{seq, type, at, data}` appended to the
  session's event log (`events.jsonl`). Snapshot (`session.json`) is updated from events.
- One active session per device serial (`409 device_busy`).
- Mutations happen only through `SessionService` commands; runner tasks report via the event bus.
  No shared mutable flags between threads (legacy `test_running`, `logcat_active`, ...).

### 3.2 Client side — server state vs UI state

- Server state (devices, sessions, results): fetched with TanStack Query; updates pushed by SSE
  `GET /api/v1/sessions/{id}/events/stream?after_seq=N` (resumable by `seq`).
- UI-only state (selected tab, filters, form drafts): local component state / small Zustand store.
- No duplicated copies of server data in a global store.
- While a session is nonterminal, its authoritative snapshot is re-fetched every five seconds,
  including while the window is in the background. SSE connection open/error also triggers reconciliation.
- Completion learned from either SSE or a snapshot refresh invalidates final performance, issues,
  event history and the session list. A terminal snapshot cannot be overwritten by delayed progress events.

## 4. API contract

Base path `/api/v1`. JSON only. Errors use RFC 9457 `application/problem+json`:

```json
{"type": "about:blank", "title": "Conflict", "status": 409, "code": "device_busy",
 "detail": "Device R3CN... already runs session s_...", "request_id": "r_..."}
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + adb availability |
| GET | `/devices` | list connected devices |
| GET | `/devices/{serial}` | device info (model, android, api level, connection type) |
| POST | `/devices/connect` | wireless connect `{host, port}` |
| POST | `/devices/pair` | wireless pair `{host, port, code}` |
| POST | `/devices/{serial}/disconnect` | wireless disconnect |
| GET | `/devices/{serial}/packages?query=&third_party=` | installed packages (+ display names) |
| GET | `/devices/{serial}/packages/{package}` | version info |
| GET | `/play/packages/{package}` | Google Play production release metadata for configured LG Uplus apps |
| GET | `/devices/{serial}/packages/{package}/icon` | installed APK icon rendered as PNG, with local cache |
| GET | `/play/auth` | local OAuth setup and connection status (no secrets) |
| POST | `/play/auth/client` | register a Google desktop OAuth client JSON locally |
| POST | `/play/auth/connect` / `/play/auth/check` | start browser login / verify app access |
| DELETE | `/play/auth` | cancel pending login and remove local OAuth credentials |
| GET | `/presets` | test presets |
| GET | `/settings/ai` | AI configuration status/model/encrypted-store path, never the key |
| PUT / DELETE | `/settings/ai` | local-only encrypted key registration / deletion; applies to subsequent calls |
| GET | `/settings/deployment` | bundled credentials availability and local restoration status |
| POST | `/settings/deployment/unlock` | restore password-encrypted installer credentials into DPAPI; preserve existing values |
| POST | `/estimates` | estimated duration for a config |
| GET | `/sessions` | list sessions |
| POST | `/sessions` | create session (state `created`) |
| GET | `/sessions/{id}` | session snapshot |
| GET | `/sessions/{id}/timing` | deadline policy, timing breakdown, segment seeds/budgets and extension history |
| POST | `/sessions/{id}/start` | start (202) |
| POST | `/sessions/{id}/stop` | stop / cancel (202) |
| DELETE | `/sessions/{id}` | delete finished session |
| GET | `/sessions/{id}/events?after_seq=` | event log page |
| GET | `/sessions/{id}/events/stream` | SSE live events |
| GET | `/sessions/{id}/report` | result summary (JSON) |
| GET | `/sessions/{id}/performance-analysis/preview` | allowlisted numerical evidence and hash, no Gemini call |
| POST | `/sessions/{id}/performance-analysis` | consented Gemini interpretation with evidence hash, cache and validation |
| GET | `/sessions/{id}/report.html` / `report.xlsx` | rendered report files |
| POST | `/sessions/{id}/exports/xlsx` | save workbook to configured desktop export directory; return saved path |
| GET | `/logs?level=&source=&session_id=&request_id=&since_seq=&limit=` | API logs |

Every response carries `X-Request-ID` (echoed if client sent one).

## 5. Logging (API logs)

- One structured record per event: `{seq, at, level, source, message, request_id, session_id, data}`.
- Sources: `http` (each request: method, path, status, duration_ms), `adb` (args, exit_code,
  duration_ms, stderr head), `session` (lifecycle, issues), `app`.
- Sinks: in-memory ring buffer (served by `/logs`) + `data/logs/api.jsonl`.
- Context (`request_id`, `session_id`) propagates through `contextvars` into background tasks.
- Secrets (API keys) are never logged; ADB args are logged as lists.

Performance collection uses the bundled AppkiumPerf protocol 1 dex agent through one ADB stream,
with stdin heartbeats, per-run cleanup, bounded reconnect attempts, and an observable ADB fallback.
Standalone Java source is in `backend/device_tools/perf_agent/src`; rebuild with
`backend/scripts/build_perf_agent.py` without the original desktop project.
`PerfSample.source` identifies the collector; optional FPS/frame/memory/CPU fields preserve `null`
when unavailable. `cpu_percent` retains the legacy core-sum convention; `cpu_total_percent` is
normalized across all cores. Collector state changes are persisted as session `collector` events.

## 6. Testing rules

- **Contract tests**: every API test validates the response body against the OpenAPI schema for
  that path/method/status (`tests/contract.py`). Snapshot test fails if `openapi.json` drifts.
- **Log-driven diagnostics**: the test client records every `X-Request-ID`; on test failure the
  matching `/api/v1/logs` records are printed in the failure report.
- Tests assert on logs too (e.g. a failed ADB call produces an `adb` error record with exit code).
- ADB is replaced by `FakeAdb` (scripted responses, fixture files from real devices) — no device needed.
- Domain functions (parsers, analyzer, state machine, estimation) have plain unit tests.

## 7. Coding rules

- Files ≤ 400 lines, functions ≤ 50 lines; one reason to change per module.
- No `shell=True`, no `except Exception: pass`, no imports inside functions.
- Errors are typed (`AdbError`, `DeviceNotFound`, `InvalidTransition`, ...) and mapped to HTTP once.
- Presets and tuning constants are data (`domain/presets.py`), not `if preset == ...` chains.
- Tooling: uv, ruff (lint+format), pytest, pyright (basic).

## 8. Release isolation and credentials

`scripts/build_installer.py` copies sources into `dist/release-work/<version>` before changing versions.
The worker only operates inside this snapshot; Rust outputs go to `dist/release-target` outside the
development watcher paths. Original version/contract files are hashed before and after the build.
This prevents release version changes from restarting a running Tauri development window.

Local Google OAuth and Gemini settings use Windows DPAPI CurrentUser. Installer distribution uses
a separate password-derived AES-256-GCM bundle with scrypt and a random salt. The destination restores
the payload under its own Windows account protection and does not overwrite existing settings.
The deployment password is stored separately from the installer with a restricted Windows ACL.

Git contains sources, tests, contracts, fonts and the device helper JARs. Credentials, `.env` secrets,
deployment bundles/passwords, installed runtimes and installer artifacts are excluded. Publishing
source code and distributing an internally configured installer are separate operations.

The build verifies the frozen backend with development tools removed from PATH and an isolated
temporary data directory. It checks bundled resources, exact credential restoration, encrypted-key
persistence after restart, and HTML/XLSX output. This does not replace clean Windows VM testing.
