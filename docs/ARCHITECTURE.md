# Monkey Test Platform — Architecture

Status: accepted (2026-11-26). Supersedes legacy Python/tkinter tool (`legacy/`, git tag `legacy-v3.0`).

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
| GET | `/presets` | test presets |
| POST | `/estimates` | estimated duration for a config |
| GET | `/sessions` | list sessions |
| POST | `/sessions` | create session (state `created`) |
| GET | `/sessions/{id}` | session snapshot |
| POST | `/sessions/{id}/start` | start (202) |
| POST | `/sessions/{id}/stop` | stop / cancel (202) |
| DELETE | `/sessions/{id}` | delete finished session |
| GET | `/sessions/{id}/events?after_seq=` | event log page |
| GET | `/sessions/{id}/events/stream` | SSE live events |
| GET | `/sessions/{id}/report` | result summary (JSON) |
| GET | `/sessions/{id}/report.html` / `report.xlsx` | rendered report files |
| GET | `/logs?level=&source=&session_id=&request_id=&since_seq=&limit=` | API logs |

Every response carries `X-Request-ID` (echoed if client sent one).

## 5. Logging (API logs)

- One structured record per event: `{seq, at, level, source, message, request_id, session_id, data}`.
- Sources: `http` (each request: method, path, status, duration_ms), `adb` (args, exit_code,
  duration_ms, stderr head), `session` (lifecycle, issues), `app`.
- Sinks: in-memory ring buffer (served by `/logs`) + `data/logs/api.jsonl`.
- Context (`request_id`, `session_id`) propagates through `contextvars` into background tasks.
- Secrets (API keys) are never logged; ADB args are logged as lists.

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
