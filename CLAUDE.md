# Project rules

Read docs/ARCHITECTURE.md before changing code. Summary of the binding rules:

## Architecture
- Backend layers: `api → services → domain`, `services → adapters`. `domain` has no I/O and imports no other layer.
- Every capability is a REST endpoint under `/api/v1`. The UI only talks to the API.
- Session state changes only through `SessionLedger` (via `SessionService` commands / `SessionRunner`).
  Legal transitions live in `domain/state_machine.py` only.
- Frontend: server state only in TanStack Query (+ SSE cache patching in `api/hooks.ts`); no global copies.
- `legacy/` is a read-only archive. Never import from it or edit it.

## Contract & logging
- `backend/openapi.json` is the contract. API change → `uv run python scripts/export_openapi.py`,
  then `npm run gen:api` in frontend; both diffs are part of the change.
- Errors are typed (`core/errors.py`) and become RFC 9457 problem+json in `api/errors.py` only.
- Use `core.logging.log(source, message, level, **data)` — never print or bare f-string logs.
  ADB calls are logged by `LoggingAdb`; HTTP by `RequestContextMiddleware`.
- Never log secrets (API keys).

## Code rules
- Files ≤ 400 lines, functions ≤ 50 lines.
- No `shell=True`; adb arguments are lists. No `except Exception: pass`. No imports inside functions.
- Presets/thresholds are data (`domain/presets.py`, constants), not `if preset == ...` chains.

## Tests
- API tests use the `api` fixture (ContractClient): every response is validated against the OpenAPI
  contract; failures print the API logs for the test's requests.
- ADB is faked with `tests/fakes.py::FakeAdb` (+ fixture files under `tests/fixtures/adb/`).
  New parsers need a fixture captured from a real device.
- Run before commit: `uv run pytest`, `uv run ruff check src tests`, `npm test`, `npm run typecheck`.
