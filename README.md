# Android Monkey Test Platform v4

Android Monkey 테스트 자동화 도구. REST API 백엔드(FastAPI)와 웹 UI(React)로 구성됩니다.
v3(Python/tkinter)는 [legacy/](legacy/)에 보관되어 있고 git 태그 `legacy-v3.0`으로도 남아 있습니다.

## 구성

```
backend/    FastAPI REST API (/api/v1), 세션 상태머신, ADB 어댑터, API 로그
frontend/   React + TanStack Query UI (v3 화면 구성/테마 계승), src-tauri/ 데스크톱 셸
docs/       ARCHITECTURE.md (설계/계약/로깅/테스트 규칙), MIGRATION.md (v3 → v4)
assets/     앱 아이콘 (Tauri 패키징용)
legacy/     v3 소스 아카이브 (수정 금지)
```

## 요구 사항

- Python 3.12+ (백엔드는 `backend/.venv` 가상환경에서 실행)
- Node.js 20+
- Rust (stable, MSVC) + WebView2 — Tauri 데스크톱 앱용
- adb: Android SDK platform-tools 또는 PATH. 다른 위치면 `MONKEY_ADB_PATH` 지정

## 실행 (데스크톱 앱)

```bash
cd frontend
npm install
npm run setup:backend   # backend/.venv 생성 + 백엔드 설치 (python -m venv + pip)
npm run tauri dev       # Vite + Tauri 창 실행, 백엔드는 셸이 .venv 의 python 으로 자동 기동/종료
```

- 백엔드가 이미 8765 포트에서 실행 중이면 셸은 그것을 재사용합니다.
- 백엔드 위치를 바꾸려면 `MONKEY_BACKEND_DIR` 를 지정합니다.

### 백엔드만 실행 (브라우저/API 개발)

```bash
cd backend
.venv\Scripts\activate          # PowerShell: .venv\Scripts\Activate.ps1
monkey-api                        # http://127.0.0.1:8765  (API 문서: /docs, 빌드된 UI도 서빙)
```

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
로그를 모두 볼 수 있습니다. 앱의 "콘솔 로그" 패널이 같은 로그를 실시간으로 보여 주고, 오류 메시지에는 `request_id`가 표시됩니다.

## 개발

```bash
cd backend && .venv\Scripts\activate
pytest                                   # 단위 + API 계약 테스트 (기기 불필요)
ruff check src tests && ruff format src tests
python scripts/export_openapi.py         # API 변경 시 계약 갱신 (리뷰 대상)

cd ../frontend
npm test            # vitest
npm run check:api   # openapi.json 과 TS 타입 동기화 확인
npm run typecheck
```
