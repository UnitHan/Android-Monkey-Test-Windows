# 운영 및 개발 상세 가이드

Android Monkey 테스트 자동화 도구. REST API 백엔드(FastAPI)와 웹 UI(React)로 구성됩니다.
현재 실행·개발 코드는 `backend/`와 `frontend/`에 있습니다. 구버전 소스는 작업 폴더에서 제거했으며,
필요하면 Git 태그 `legacy-v3.0`에서 확인할 수 있습니다.

## 구성

```
backend/    FastAPI REST API (/api/v1), 세션 상태머신, ADB 어댑터, API 로그
frontend/   React + TanStack Query UI (v3 화면 구성/테마 계승), src-tauri/ 데스크톱 셸
docs/       설계/계약/로깅/테스트 규칙과 Google Play 연결 안내
assets/     앱 아이콘 원본 (패키징용 아이콘은 frontend/src-tauri/icons)
legacy/fonts/ 보존한 Noto Sans KR 원본 폰트 3종 (앱 사용본: frontend/public/fonts/)
```

## 설치 패키지 사용

Windows 10/11 x64용 설치 파일은 Python, ADB/aapt2, 성능 수집 JAR, Noto Sans KR 폰트,
WebView2 오프라인 설치 관리자를 포함합니다. 대상 PC에 Python·Node.js·Java·Android SDK를
별도로 설치하지 않습니다. Google 로그인·Gemini 사용에는 인터넷이 필요합니다.
USB 연결은 단말의 USB 디버깅 허용과 제조사 드라이버가 필요할 수 있으며 무선 ADB도 지원합니다.

설치 파일에는 빌드 PC에 등록된 **Google 클라이언트·OAuth 로그인 토큰·Gemini API 키와 모델**을
암호화한 설정 묶음이 포함됩니다. 새 PC에서 최초 실행하면 **설정 → 기존 설정 복원**에
배포 암호를 입력합니다. 기존 `datasvcqa@gmail.com` 인증과 Gemini 키를 그대로 복원하므로
클라이언트 JSON이나 API 키를 다시 입력할 필요가 없습니다. Google에서 토큰을 만료·철회한 경우에는
해당 계정으로 재로그인이 필요합니다. 이미 설정된 PC에서는 기존 값을 덮어쓰지 않습니다.

배포 암호는 빌드마다 자동 생성하며 `dist/private-release/<버전>/deployment-password.txt`에
현재 Windows 사용자와 SYSTEM만 접근하도록 저장합니다. 설치 EXE에는 암호를 넣지 않습니다.
암호 파일은 배포 담당자가 보관하고 설치 대상에게 별도로 전달합니다.

### 설치 파일 빌드 (개발 PC)

아래 개발 환경과 Android SDK Build Tools를 준비한 뒤 실행합니다.

```powershell
cd frontend
npm run installer
```

빌드는 `dist/release-work/<버전>/`의 소스 복사본에서 실행합니다. 복사본의 Python·npm·Cargo·Tauri 및
API 계약 버전만 함께 올리며, 실행 중인 개발 앱이 감시하는 원본 버전·소스·런타임은 수정하지 않습니다.
별도 Rust 출력/캐시는 `dist/release-target/`을 사용하고, 빌드 전후 원본 버전 파일 해시를 비교합니다.
직전 배포/시도 버전에서 패치 버전을 증가시키며 실패한 격리 빌드의 버전도 재사용하지 않습니다.
`tauri build` 직접 실행은 차단하여 버전 증가·런타임 포장을 빠뜨리지 않게 합니다.
결과는 `dist/installers/<버전>/`의 설치 EXE와 SHA-256 파일입니다.
Google 클라이언트·로그인·Gemini 키 중 하나라도 없으면 빈 설정으로 패키징하지 않고 빌드를 중단합니다.
`deployment.vault.json`에는 32바이트 salt, scrypt로 유도한 키, AES-256-GCM 인증 암호화를 사용합니다.
원본 인증 파일은 읽기만 하며, 설정 복원 검증도 별도 임시 사용자 폴더에서 수행합니다.
빌드 PC에는 개발 도구가 필요하며, 대상 PC에는 필요하지 않습니다.
최초 빌드는 NSIS/WebView2 도구 다운로드를 위해 인터넷이 필요합니다.

`scripts/verify_runtime.py`는 개발 도구를 제외한 PATH와 임시 사용자 폴더에서 독립 백엔드,
내장 ADB, 암호화 키 재시작 유지, HTML·엑셀 생성을 검증합니다. 클린 Windows VM 검증과는 별개입니다.

## 개발 환경 요구 사항

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
- F5, Ctrl+F5, Ctrl+R, Ctrl+Shift+R로 창 전체를 새로고침하지 않습니다. 연결·선택 상태를
  유지하며, 데이터 갱신은 화면의 **새로고침** 버튼을 사용합니다. Windows 데스크톱에서는
  HTML 보고서에 포커스가 있어도 같은 단축키를 차단합니다.

### 백엔드만 실행 (브라우저/API 개발)

```bash
cd backend
.venv\Scripts\activate          # PowerShell: .venv\Scripts\Activate.ps1
monkey-api                        # http://127.0.0.1:8765  (API 문서: /docs, 빌드된 UI도 서빙)
```

## 설정과 인증 정보 보관

**설정 → Gemini API 설정**에서 키를 등록·삭제합니다. 저장 즉시 이후 AI 요청에 적용합니다.
Google 클라이언트 설정·OAuth 토큰·Gemini 키는 `%LOCALAPPDATA%\MonkeyTest\credentials` 아래
Windows DPAPI CurrentUser 암호문으로 보관합니다. 저장마다 32바이트 난수 salt를 추가 entropy로
사용하며, 앱에 고정 암호화 키를 넣지 않습니다. salt 자체는 암호화 키가 아닙니다.
DPAPI 파일 자체를 다른 PC로 복사해서 사용할 수는 없습니다. 설치 파일의 배포 암호화 묶음으로
기존 설정을 복원하면 새 PC의 DPAPI로 다시 보호합니다.
[DPAPI 공식 설명](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)을 참고하세요.

기존 개발용 `.env`의 Gemini 키와 평문 OAuth JSON은 실제 백엔드 시작 시 암호화·복호화 검증 후
자동 이전합니다. 이전에 성공한 키는 `.env`에서 제거하며 이후 암호화 저장소를 우선합니다.
사용자가 다운로드한 원본 클라이언트 JSON은 앱 밖의 파일이므로 변경하지 않습니다.
일반 실행 옵션은 계속 프로젝트 루트 `.env` 또는 환경 변수로 설정할 수 있습니다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MONKEY_ADB_PATH` | 내장 도구 → SDK → PATH | adb 실행 파일 |
| `MONKEY_DATA_DIR` | `%LOCALAPPDATA%\MonkeyTest` | 세션 데이터, 리포트, API 로그(`logs/api.jsonl`) |
| `MONKEY_PORT` | `8765` | 서버 포트 |
| `MONKEY_GEMINI_API_KEY` | 없음 | 기존 개발 설정 최초 이전용. 이후 앱 설정 메뉴 사용 |
| `MONKEY_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini 모델명 |

`GET /api/v1/settings/ai`로 키 설정 여부·활성화 여부·모델·설정 파일 경로를 확인합니다.
`PUT /api/v1/settings/ai`는 `{api_key, model}`을 암호화 저장하고 `DELETE`는 등록된 키를 삭제합니다.
키 원문은 응답과 로그에 포함하지 않으며 로컬 주소·허용된 Origin에서만 변경할 수 있습니다.
`configured`는 키를 읽었다는 뜻이며 실제 Google 인증 성공을 의미하지 않습니다.
Gemini는 첫 회차 이후 이벤트 수 추천 및 사용자가 요청한 성능 분석에 사용하며, 오류 시 기본 계산을 사용합니다.
응답 대기는 최대 20초이고 중단 버튼으로 취소됩니다. 회차 내부 시간 제어는 Gemini와 독립적입니다.

## 시간 기준 테스트와 API

Smoke는 6분 × 5회 = 30분, Standard는 10분 × 6회 = 1시간,
Deep은 18분 × 10회 = 3시간, Extreme은 32분 × 15회 = 8시간입니다. Quick은 삭제했습니다.
화면의 프리셋 이름에는 총 테스트 시간을, 하단에는 준비 시간을 포함한 예상 소요 시간을 표시합니다.
앱 준비 후 하나의 monotonic 종료 시각을 설정합니다. 이벤트가 정상 소진되면 앱·로그 수집기를
재시작하지 않고 같은 회차에서 추가 Monkey 프로세스를 실행합니다. 실행 중인 Monkey의 이벤트
인자를 바꾸는 방식은 아닙니다. 추가 이벤트 수는 실측 속도 × 남은 시간 × 1.3과 이전 할당량+1 중
큰 값으로 정하며, Monkey 정수 범위로 제한합니다. 제한에 도달해도 필요하면 다시 추가 실행합니다.

추가 실행마다 Seed를 1 증가시키고 각 구간의 Seed·이벤트 할당량·실제 이벤트·시간·종료 사유를
기록합니다. 하나의 연속된 Monkey 난수열은 아니므로 전체 재현에는 각 구간 기록과 앱 상태가 필요합니다.
시간 기준 테스트에서 `adaptive=false`는 회차 사이 추천만 끄며 회차 내부 추가 실행은 유지합니다.
이벤트 기준 테스트와 재현테스트는 설정한 이벤트 수가 끝나면 종료합니다.

목표 시간은 Monkey 시작·추가 프로세스 전환을 포함한 회차 실행 경과 시간입니다.
앱 준비·최종 정리·회차 사이 AI 대기와 전체 종료 시간은 구분합니다. OS/ADB 정리 지연 때문에
전체 실행이 정확히 같은 밀리초에 끝나는 것은 아닙니다. 오류·연결 끊김·사용자 중단은 조기 종료
사유로 기록하며, 정상 완료로 숨기거나 시간만 채우기 위해 재시도하지 않습니다.

| API | 내용 |
|---|---|
| `POST /api/v1/sessions` | `overrides.target_minutes_per_run`으로 시간 기준 지정; `events`는 초기 예상치 |
| `GET /api/v1/sessions/{id}/timing` | 시간 정책·목표 시간·진행률·완료된 회차 실행 시간·추가 실행 내역 |
| `GET /api/v1/sessions/{id}` | 회차별 `execution_duration_s`, `preparation_duration_s`, `cleanup_duration_s`, `segments` |
| `GET /api/v1/sessions/{id}/events/stream` | 기존 SSE에 `run_extended`, `segment_started`, `segment_finished` 추가 |
| `POST /api/v1/sessions/{id}/stop` | 실행/추가 실행/AI 대기 중단 |

`Progress`에 목표·남은 시간·현재 구간·누적 할당 이벤트가 추가됩니다. `events_sent`는 구간별
출력을 합산하므로 추가 실행 때 초기화되지 않습니다. `events_target`은 초기 예상치를 유지합니다.
이전 저장 결과에 분리된 실행 시간이 없으면 관련 값은 `null`, `segments`는 빈 배열로 반환합니다.

회차 종료 시 PC의 ADB 연결만 닫지 않고, 실행별 고유 PID 파일로 추적한 단말 Monkey도 종료하고
종료 여부를 확인합니다. 정리에 실패하면 다음 회차를 실행하지 않고 실패를 기록합니다.
마감 시각은 종료 요청 기준이며, 단말 명령 전달·종료 확인 지연은 정리 시간에 포함됩니다.

앱 이탈은 Android `events` 로그의 Activity resume 이벤트로 감지합니다. 기존 5초 간격의
전경 폴링 대신 이벤트가 발생할 때 현재 화면을 확인하고 `am start`로 복귀시킵니다.
복귀용 별도 Monkey를 띄우지 않으며, 대기열은 최신 이벤트 1개로 제한합니다.
복귀 요청·확인 결과와 스트림 재연결 실패는 세션 `guard` 이벤트로 남깁니다.
네트워크 상태 점검과 성능 수집은 별도 주기 작업입니다. 예외 처리는 실패를 처리하는 수단이며
화면 이탈 감지를 대신하거나 자원 사용을 0으로 만들지는 않습니다.

Monkey의 `--monitor-native-crashes` 옵션은 사용하지 않습니다. 기존 단말 tombstone도 초기
검사하면서 파일마다 대기해 이벤트 주입을 늦추기 때문입니다. 대상 앱의 네이티브 크래시는
별도 logcat 분석기로 계속 수집합니다.

성능은 `backend/device_tools/perf_agent/src`에 이식한 protocol 1 기기 수집기를 기본으로 사용합니다.
AppkiumPerf 전체 프로젝트 없이 실행·재빌드할 수 있습니다. Java 소스 9개는 원본 그대로 보존했으며,
JDK와 Android SDK가 있으면 아래 명령으로 배포 JAR을 갱신합니다.

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/build_perf_agent.py --android-jar <SDK의_android.jar_경로> --build-tools <SDK_build-tools_버전_폴더>
```

출력은 `backend/src/monkey_api/data/appkium-android.jar`이며 `--output`으로 검증용 경로를 지정할 수 있습니다.
원본 prebuilt JAR를 `backend/src/monkey_api/data/appkium-android.jar`에 포함했습니다.
원본 Java 구현(`Main`, `Sampler`, `Frames`)과 Kotlin `AgentPerfMonitor`의 단위 변환을 기준으로
포팅했으며, APK 설치 없이 실행별 임시 경로에 전송합니다. stdin 생존 신호와 PID 정리로 종료하고,
3회 연결 실패 시 상태를 기록한 후 기존 ADB 수집으로 전환합니다. CPU 합산 값은 기존 의미를
유지하고, 기기 전체 용량 기준 CPU 값은 별도 `cpu_total_percent` 필드에 저장합니다.
PSS는 약 5초마다 갱신되며 미지원 값은 `null`입니다. 성능 표본의 수집원은 `source`로 확인합니다.

성능 모니터·테스트 결과·HTML 보고서는 상단 전체 화면 탭에서 확인합니다. HTML은 팝업 대신
격리된 iframe으로 표시합니다. 보고서는 한글 상태·환경 카드와 자원 통계로 구성하며, 그래프는
외부 스크립트 없이 표시되는 SVG이므로 저장한 HTML에서도 인터넷 연결 없이 볼 수 있습니다.
긴 패키지명은 줄바꿈하며, 수집 공백·회차 경계를 그래프로 연결하지 않습니다.
보고서 탭의 새로고침으로 최신 수집 결과를 갱신합니다. 엑셀 내보내기는 `POST /api/v1/sessions/{id}/exports/xlsx`를 호출해
`다운로드/MonkeyTest`에 저장하고 저장 경로나 오류를 표시합니다. `MONKEY_EXPORT_DIR`로 폴더를
변경할 수 있으며, 기존 GET xlsx 다운로드 API도 유지합니다.

이슈 요약의 자원 평가는 최대값만으로 최적화·누수를 요구하지 않습니다. 보고서 API는 전체·회차별
평균, 시간 가중 평균, 최소·최대, 모집단 표준편차, P50/P90/P95와 유효 관측 구간을 제공합니다.
P90/P95는 유효 표본의 올림 순위이며, 시간 가중 평균은 같은 회차·같은 수집원의 인접 값을 선형
보간합니다. 결측과 10초 초과 공백은 연결하지 않습니다. 표본 30개·관측 60초·실행 대비 80%는
자료 충분성 참고 조건이며 앱의 합격 기준이 아닙니다. CPU 참고선 80%는 코어 합산이 아닌
기기 전체 용량 대비 값에만 적용하고 P90과 연속 30초 관측을 함께 확인합니다.
앱별 메모리 예산·기준 버전이 없으므로 사용량만으로 누수를 판정하지 않습니다. 자료가 없으면
정상 판정 대신 판단 보류를 표시합니다. 동일 통계는 HTML 및 엑셀의 Resource Statistics 시트에도
포함됩니다. 이 평가는 코드로 계산하며 Gemini에 자동으로 전송하지 않습니다.
**이슈 요약 및 권고사항 → AI 성능 분석**에서 전송 통계를 확인하고 동의하면 등록한 Gemini 키와
모델로 정상 여부를 해석합니다. 판정은 관측 범위 정상·주의·이상 징후·판단 보류이며 출시 합격 인증은 아닙니다.
전체·회차별 통계, 실행 시간/수집 범위, 크래시·ANR 건수만 전송하며 원본 로그·앱 패키지·기기 식별번호는
보내지 않습니다. 회사에서 승인한 API 프로젝트를 사용하세요. 자료 부족, 미완료, 목표 시간 미달은
정상 판정을 허용하지 않습니다. 정상 분류를 강제하는 모델 응답도 서버에서 검증합니다.
분석은 세션별로 저장되어 요약 탭·HTML·엑셀의 AI Performance 시트에 포함됩니다. 같은 통계와 모델은
캐시를 재사용하고 통계 변경 시 과거 분석을 표시하지 않습니다. 키·프롬프트·응답 본문은 API 로그에
남기지 않으며 호출 소요 시간과 토큰 수만 기록합니다. 분석 실패 시 기존 통계 보고서를 유지합니다.
`GET /sessions/{id}/performance-analysis/preview`, `POST /sessions/{id}/performance-analysis`는
`/api/v1` 아래에 있으며 POST에는 미리보기의 `input_hash`와 `consent: true`가 필요합니다.
Gemini 응답은 [공식 JSON Schema 구조화 출력](https://ai.google.dev/gemini-api/docs/structured-output)을
사용하고 서버에서 재검증합니다.
상세 스키마와 실행 예시는 백엔드 `/docs`에서 확인할 수 있습니다.

## 문제 추적

설치 앱 이름은 단말의 Android `PackageManager.getApplicationLabel()` 결과를 사용합니다.
앱 검색은 `C:\appkium`의 `HangulSearch.kt`와 `SearchHighlight.kt`를 참고하여 초성(`ㅇㅅㅇ` → 익시오),
한글 발음(`블` → blind, `드라이브` → OneDrive), 영문 로마자 검색을 지원합니다.
이름 접두·부분 일치, 패키지, 초성, 발음 순서로 정렬하며 앱 이름과 패키지를 분리해서 표시합니다.
초성·문자열 일치 구간만 강조하고 발음 매칭은 임의의 글자를 강조하지 않습니다.
단말 런처에 표시되는 앱을 기본 검색 대상으로 하므로 YouTube 같은 기본 설치 앱도 포함합니다.
실행 아이콘 없는 패키지 포함 옵션, 방향키/Enter 선택, 한글 IME 조합 보호를 제공합니다.
검색 목록은 화면에 보이는 앱부터 아이콘을 불러오며 선택 화면과 PC 캐시를 공유합니다.
단말 PackageManager가 그린 128px PNG를 우선 사용하여 벡터·적응형 아이콘을 지원하고,
단말 렌더링이 불가능하면 APK 리소스 추출로 대체합니다.

이전 결과를 선택한 뒤 `기록 삭제` → `완전 삭제`로 해당 세션의 결과·테스트 로그·성능 데이터·
AI 분석·보고서를 제거합니다. 기본 내보내기 위치의 해당 엑셀 파일도 삭제하며, 사용자가 따로
복사하거나 이름을 바꾼 파일과 프로그램 공통 진단 로그는 포함하지 않습니다.
실행 중이거나 종료 정리가 진행 중인 세션은 삭제할 수 없습니다.
앱 목록은 단말·설치 유형별로 30초 캐시하고 **새로고침**으로 목록과 이름을 함께 갱신합니다.
내장 `apps.json`의 과거 이름은 검색 별칭으로만 사용하고 화면 이름으로 사용하지 않습니다.
조회 실패 시 패키지명을 표시합니다. 이름 조회는 단말별로 30초 동안 캐시하고 **새로고침**으로 즉시 갱신합니다.
`GET /api/v1/devices/{serial}/packages?refresh=true`도 동일하게 갱신합니다.

전체 앱 이름을 한 번에 읽기 위해 소스가 포함된 약 2KB 도구를 ADB로 임시 전송하고,
`app_process`에서 조회한 뒤 삭제합니다. APK 설치·앱 데이터 변경·앱 실행은 하지 않습니다.
소스는 `backend/device_tools/AppLabels.java`, 배포 파일은 `backend/src/monkey_api/data/app_labels.jar`입니다.
JDK와 Android SDK가 있으면 `backend/scripts/build_app_labels.py --android-jar <android.jar 경로>
--build-tools <SDK build-tools 버전 폴더>`로 다시 빌드할 수 있습니다.

선택 앱의 설치 버전과 Google Play 출시 정보를 함께 확인할 수 있습니다.
익시오(`com.lguplus.aicallagent`), U+tv 모바일(`com.lguplus.remocon`) 등 연결된 Play Console
계정에 조회 권한이 있는 앱을 지원합니다. 선택한 앱을 내부 패키지 허용 목록으로 차단하지 않습니다.
최초 Google 계정 연결 및 추가 패키지 설정은 [Google Play 연결 안내](GOOGLE_PLAY.md)를 참고하세요.

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
