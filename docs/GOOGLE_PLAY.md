# LG유플러스 앱의 Google Play 출시 정보

이 기능은 Google Play Developer API만 사용합니다. 익시오(`com.lguplus.aicallagent`),
U+tv 모바일(`com.lguplus.remocon`) 등 연결된 Play Console 계정에 조회 권한이 있는 앱을
선택하면 출시 정보를 조회합니다. 앱별 하드코딩 목록으로 조회를 차단하지 않으며,
사설스토어 조회나 웹 스크래핑을 사용하지 않습니다.

## 최초 연결

Play Console 로그인과 API 인증은 별도입니다. 다음 설정은 Google Cloud 및 Play Console에서 진행합니다.

1. Google Cloud에서 사용할 프로젝트를 선택하고 **Google Play Android Developer API**를 활성화합니다.
2. Google Auth Platform에서 앱 정보와 대상 사용자를 설정합니다. 테스트 모드라면
   `datasvcqa@gmail.com`을 테스트 사용자에 추가합니다.
3. OAuth 클라이언트를 **데스크톱 앱** 유형으로 만들고 클라이언트 JSON을 로컬에 다운로드합니다.
4. Play Console의 **사용자 및 권한**에서 위 계정에 조회할 앱의 권한이 있는지 확인합니다.
   OAuth 인증으로 기존 계정의 앱 접근 범위가 확대되지는 않습니다.
5. 앱의 **설정 → Google Play → 클라이언트 파일 등록**에서 다운로드한 JSON을 선택합니다.
   **Google 계정 연결**을 누르면 시스템 브라우저에서 로그인이 열립니다.
6. `datasvcqa@gmail.com`을 선택하고 동의한 뒤 앱으로 돌아옵니다. **연결 확인**으로
   기본 확인 후보(익시오, U+tv 모바일) 중 접근 가능한 앱을 조회합니다. 확인한 패키지명도 표시합니다.
   단말 연결 전에도 설정 메뉴를 사용할 수 있습니다.
7. 앱에서 조회할 앱을 선택하거나 **새로고침**을 누릅니다. 인증 완료 시 Play 조회도 자동 갱신됩니다.

**이 PC에서 연결 해제**는 로컬 인증 정보를 삭제합니다. Google 계정 전체의 앱 동의를 철회하는 기능은 아닙니다.
로그인 중에는 같은 버튼으로 취소할 수 있으며, 취소 후 도착한 로그인 결과는 저장하지 않습니다.
설정 창을 닫아도 로그인은 진행되며, 앱 종료 시 대기 중인 로그인은 취소됩니다.
클라이언트 파일을 바꾸면 기존 인증 정보는 삭제되어 다시 연결해야 합니다.

### 명령줄 연결 (선택)

앱 설정 대신 CLI를 사용할 수도 있습니다. 저장소 루트의 PowerShell에서 실행합니다.
JSON 경로는 실제 다운로드 경로로 바꿉니다.

   ```powershell
   .\backend\.venv\Scripts\python.exe -m pip install -e .\backend
   Set-Location backend
   .\.venv\Scripts\python.exe scripts/play_login.py --client-secrets "C:\Users\dwonh\Downloads\client_secret_DESKTOP.json"
   ```

열린 Google 로그인 창에서 `datasvcqa@gmail.com`을 선택하고 동의합니다.
   명령은 loopback 주소에서 최대 5분 동안 응답을 기다립니다. 로그인 힌트는 계정을 강제하지 않으므로
   실제로 선택한 계정이 권한을 결정합니다.
앱에서 익시오를 선택하고 **새로고침**을 누릅니다. 설치 버전과 Play 출시 정보가 함께 갱신됩니다.

기본 인증 파일은 `%LOCALAPPDATA%\MonkeyTest\credentials\play-oauth.json`입니다.
설정에서 등록한 클라이언트 파일은 같은 디렉터리의 `play-client.json`에 저장됩니다.
두 파일은 `.json` 확장자이지만 내부는 매번 다른 32바이트 salt와 Windows DPAPI 암호문입니다.
현재 Windows 사용자 계정에 묶입니다. 다른 PC에는 설치 파일에 포함된 배포 암호화 묶음을
최초 한 번 복원해 기존 클라이언트·OAuth 토큰을 유지합니다. Google에서 토큰을 철회·만료한 경우 재로그인합니다.
기존 평문 파일은 새 백엔드를 시작할 때 검증 후 암호화 형식으로 자동 이전합니다.
다운로드 폴더의 원본 클라이언트 JSON은 수정하지 않습니다. 설치 파일에는 앱에 등록된 클라이언트와
로그인 토큰을 암호화한 `deployment.vault.json`만 포함하며 평문 JSON과 배포 암호는 포함하지 않습니다.
브라우저나 프런트엔드에 토큰을 전달하지 않으며 백엔드가 필요할 때 갱신합니다.
클라이언트 JSON, 인증 파일 및 토큰은 Git에 추가하거나 채팅에 붙여넣지 않습니다.
OAuth 앱이 외부 사용자 대상 테스트 상태이면 refresh token이 일반적으로 7일 뒤 만료될 수 있습니다.
만료 또는 동의 철회 시 위 명령으로 다시 연결합니다.

## 설정

프로젝트 루트의 `.env` 또는 환경 변수에서 설정합니다. 변경 후 백엔드를 재시작합니다.

```dotenv
MONKEY_PLAY_PACKAGES=["com.lguplus.aicallagent","com.lguplus.remocon"]
# 선택: 기본 사용자 데이터 디렉터리 대신 다른 인증 파일을 사용하는 경우
MONKEY_PLAY_OAUTH_FILE=C:/secure/play-oauth.json
```

`MONKEY_PLAY_PACKAGES`는 설정 창의 **연결 확인**에 사용할 후보 목록입니다. 선택한 앱의 조회 허용 목록이
아니므로 다른 LG유플러스 앱을 선택할 때 목록 변경이나 재시작이 필요하지 않습니다.
패키지명 접두사로 소유자를 판단하지 않으며, 실제 접근 가능 여부는 Google 권한 검사로 결정됩니다.
한 후보가 권한 부족 또는 미등록이면 다음 후보를 확인합니다. 개별 앱의 권한 오류는 해당 앱 선택 시 표시합니다.
인증 경로를 바꾸면 로그인 명령도 같은 설정으로 실행하거나 `--output`으로 동일한 경로를 지정합니다.

## API 및 표시 의미

`GET /api/v1/play/packages/{package}`는 다음 공식 API의 `production` 트랙을 읽습니다.

```http
GET https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/tracks/production/releases
```

응답에는 출처, 조회 시각, 출시 이름, 출시 상태, 버전 코드 목록이 포함됩니다.
릴리스 조회는 GET만 사용하며 edit 생성이나 배포 변경을 수행하지 않습니다.

- **설치된 버전**: 기존 ADB 조회의 `versionName`, `versionCode`입니다.
- **출시 이름**: Google의 `releaseName`입니다. Android `versionName`으로 간주하지 않습니다.
  이 API는 APK의 `versionName` 필드를 제공하지 않습니다.
- **버전 코드 비교**: `PUBLISHED` 상태의 코드만 숫자로 비교합니다.
  검토 중, 승인 후 미출시, 초안, 알 수 없는 상태는 비교에서 제외합니다.
- **기기별 업데이트 여부**: 이 API만으로 확정할 수 없습니다. `PUBLISHED`에는 단계 배포 및
  재개 가능한 중단된 출시도 포함됩니다. 따라서 “최신”, “업데이트 필수”로 표시하지 않습니다.
  API는 오래되어 제외된 출시를 제외하고 최대 20개 출시를 반환합니다.

설치 정보와 Play 정보는 별도 요청이므로 Google 연결 실패가 ADB 조회를 막지 않습니다.
새로고침 실패 시 이전 Play 결과를 현재 결과인 것처럼 표시하지 않습니다.

| 오류 코드 | 확인할 내용 |
|---|---|
| `play_not_configured` | 최초 OAuth 연결 및 인증 파일 경로 |
| `play_auth_required` | 만료·동의 철회·잘못된 인증 파일, 재로그인 필요 |
| `play_forbidden` | 앱 조회 권한, API 활성화 및 조직 정책 |
| `play_not_found` | 패키지명과 production 트랙 |
| `play_rate_limited` | 요청 한도, 잠시 후 새로고침 |
| `play_timeout` / `play_error` | Google 연결 또는 응답 오류 |

오류의 요청 ID로 콘솔 로그를 확인할 수 있습니다. OAuth 토큰, Authorization 헤더 및 Google 오류 본문은
API 응답이나 애플리케이션 로그에 기록하지 않습니다.

## 공식 참고 자료

- [API 활성화 및 사용자 권한](https://developers.google.com/android-publisher/getting_started)
- [출시 목록 조회](https://developers.google.com/android-publisher/api-ref/rest/v3/applications.tracks.releases/list)
- [출시 이름·버전 코드·출시 상태 정의](https://developers.google.com/android-publisher/api-ref/rest/v3/applications.tracks.releases)
- [데스크톱 OAuth 인증](https://developers.google.com/identity/protocols/oauth2/native-app)
- [테스트 앱의 refresh token 만료 조건](https://developers.google.com/identity/protocols/oauth2#expiration)

HTTP 응답 모의 테스트로 앱별 권한 및 오류 처리를 검증합니다. 2026-11-26 실제 연결 계정으로
익시오(출시 코드 `13424`)와 U+tv 모바일(출시 코드 `11001`)의 production 조회 성공을 확인했습니다.
각 앱의 향후 조회 가능 여부는 계정 권한과 Google 응답에 따릅니다.

## 단말 앱 아이콘

선택한 앱의 APK를 ADB로 PC 임시 폴더에 가져오고 Android SDK Build Tools의 `aapt2`로 아이콘 리소스를
찾습니다. PNG/WebP 등 래스터 이미지와 래스터 전경·단색/래스터 배경으로 구성된 적응형 아이콘을
128×128 PNG로 변환합니다. 적응형 아이콘은 일정한 둥근 사각형으로 합성하므로 단말 런처의 테마와
마스크 모양까지 똑같이 재현하지는 않습니다. XML 벡터 등 지원하지 않는 리소스는 기본 아이콘으로 표시합니다.

- 단말에 별도 앱을 설치하지 않으며 Google 인증이나 네트워크 다운로드가 필요하지 않습니다.
- 최초 선택 시 APK 전송 시간이 필요하며, 추출 후 임시 APK는 삭제합니다.
- 캐시는 `%LOCALAPPDATA%\MonkeyTest\icons`에 저장합니다. 단말, 패키지, 버전 코드, 업데이트 시각,
  APK 경로를 키에 반영하므로 재설치·업데이트 후 새 아이콘을 추출합니다.
- 아이콘 조회 실패는 버전 조회나 테스트 시작을 막지 않습니다. 새로고침은 아이콘 캐시 키도 재확인합니다.
- 설치 패키지는 `aapt2`를 내장합니다. 개발 실행은 SDK Build Tools에서 탐색하며 별도 경로는 `MONKEY_AAPT2_PATH`로 지정합니다.
- `GET /api/v1/devices/{serial}/packages/{package}/icon`은 PNG base64, 캐시 사용 여부, 식별 키를 반환합니다.

실제 연결 단말의 익시오(`01.34.00`, 버전 코드 `13424`) APK에서 적응형 아이콘 추출을 확인했습니다.
