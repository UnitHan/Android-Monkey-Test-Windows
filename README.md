# Android Monkey Test Platform v4

Android Monkey 테스트 자동화 도구. REST API 백엔드(FastAPI)와 웹 UI(React)로 구성됩니다.
v3(Python/tkinter)는 [legacy/](legacy/)에 보관되어 있고 git 태그 `legacy-v3.0`으로도 남아 있습니다.

## 구성

```
backend/    FastAPI REST API (/api/v1), 세션 상태머신, ADB 어댑터, API 로그
frontend/   React + TanStack Query UI (빌드 결과를 백엔드가 서빙)
docs/       ARCHITECTURE.md (설계/계약/로깅/테스트 규칙), MIGRATION.md (v3 → v4)
assets/     앱 아이콘 (Tauri 패키징용)
legacy/     v3 소스 아카이브 (수정 금지)
```

## 요구 사항

- Python 3.12+ 와 [uv](https://docs.astral.sh/uv/) (`python -m pip install uv`)
- Node.js 20+ (UI 빌드 시)
- adb: Android SDK platform-tools 또는 PATH. 다른 위치면 `MONKEY_ADB_PATH` 지정

## 실행

```bash
# 1) UI 빌드 (최초 1회 / UI 변경 시)
cd frontend && npm install && npm run build

# 2) API + UI 서버
cd ../backend && python -m uv sync && python -m uv run monkey-api
# → http://127.0.0.1:8765  (API 문서: /docs)
```

UI 개발 시에는 `cd frontend && npm run dev` (5173 포트, /api 는 8765 로 프록시).

## 설정 (환경 변수, 접두사 `MONKEY_`, `backend/.env` 지원)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MONKEY_ADB_PATH` | SDK → PATH 자동 탐색 | adb 실행 파일 |
| `MONKEY_DATA_DIR` | `%LOCALAPPDATA%\MonkeyTest` | 세션 데이터, 리포트, API 로그(`logs/api.jsonl`) |
| `MONKEY_PORT` | `8765` | 서버 포트 |
| `MONKEY_GEMINI_API_KEY` | 없음 | 설정 시 적응형 이벤트 조정에 Gemini 조언 사용(범위 제한됨) |
| `MONKEY_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini 모델명 |

## 문제 추적

모든 응답에 `X-Request-ID`가 붙고, 오류는 `application/problem+json`으로 `request_id`를 포함합니다.
`GET /api/v1/logs?request_id=...` 또는 `?session_id=...` 로 해당 요청/세션의 HTTP, ADB 호출, 세션 이벤트
로그를 모두 볼 수 있습니다. UI의 "API 로그" 탭과 오류 메시지의 "로그 보기" 버튼이 같은 기능입니다.

## 개발

```bash
cd backend
python -m uv run pytest                       # 단위 + API 계약 테스트 (기기 불필요)
python -m uv run ruff check src tests && python -m uv run ruff format src tests
python -m uv run python scripts/export_openapi.py   # API 변경 시 계약 갱신 (리뷰 대상)

cd ../frontend
npm test            # vitest
npm run check:api   # openapi.json 과 TS 타입 동기화 확인
npm run typecheck
```
