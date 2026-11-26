# Android Monkey 테스트 자동화 v3.0

모듈화된 Android Monkey 테스트 자동화 도구입니다.

## 📁 프로젝트 구조

```
c:\Monkey\
├── monkey_v3.py              # 메인 실행 파일
├── src/
│   ├── __init__.py
│   ├── config.py             # 설정 및 상수
│   ├── core/                 # 핵심 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── adb_client.py     # ADB 명령어 래퍼
│   │   ├── monkey_runner.py  # Monkey 테스트 실행
│   │   ├── performance_monitor.py  # 성능 모니터링
│   │   ├── report_generator.py     # 리포트 생성
│   │   └── test_context.py   # 테스트 컨텍스트 관리
│   ├── ui/                   # UI 관련
│   │   ├── __init__.py
│   │   ├── main_app.py       # 메인 GUI 애플리케이션
│   │   └── ui_utils.py       # UI 유틸리티 함수
│   └── utils/                # 유틸리티
│       ├── __init__.py
│       └── logger.py         # 로깅 설정
├── logs/                     # 로그 파일
├── monkey_reports/           # HTML 리포트
├── performance_logs/         # 성능 로그
└── README.md
```

## 🚀 주요 개선 사항

### 1. 모듈화 및 단일 책임 원칙
- **AdbClient**: ADB 명령어 실행 전담
- **MonkeyRunner**: Monkey 테스트 실행 로직
- **PerformanceMonitor**: CPU/메모리 모니터링
- **ReportGenerator**: HTML/Excel 리포트 생성
- **TestContext**: 테스트 상태 관리

### 2. 설정 중앙화
- **config.py**: 모든 설정과 상수를 한 곳에서 관리
- 매직 스트링 제거 (CRASH_KEYWORDS, ANR_KEYWORDS 등)
- 경로 설정 중앙화

### 3. 로깅 개선
- **logger.py**: 통합 로깅 설정
- 중복 로깅 설정 제거
- 구조화된 로그 메시지

### 4. UI/비즈니스 로직 분리
- **main_app.py**: UI 로직만 담당
- **ui_utils.py**: 재사용 가능한 UI 컴포넌트
- 비즈니스 로직은 core 모듈에서 처리

### 5. 전역 변수 제거
- **TestContext** 클래스로 상태 관리
- 캡슐화된 데이터 접근

## 🔧 설치 및 실행

### 필요 사항
```bash
pip install -r requirements.txt
```

### 환경변수 설정
1. `.env.example` 파일을 `.env`로 복사
2. `.env` 파일에서 다음 값들을 설정:

```bash
# Gemini API 키 (AI 기반 이슈 분석용)
GEMINI_API_KEY=your_gemini_api_key_here
```

**Gemini API 키 발급 방법:**
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 방문
2. Google 계정으로 로그인
3. "Create API Key" 버튼 클릭
4. 발급받은 키를 `.env` 파일에 설정

### 실행
```bash
python monkey_v3.py
```

## 📊 주요 기능

### 1. 테스트 설정
- 프리셋 기반 테스트 (Smoke, Quick, Standard, Deep, Extreme)
- 사용자 정의 설정
- 예상 소요 시간 계산

### 2. 성능 모니터링
- 실시간 CPU/메모리 사용량 모니터링
- 성능 임계값 기반 자동 분석
- 동적 개선 제안 생성

### 3. 리포트 생성
- **HTML 리포트**: Chart.js 기반 그래프 포함
- **Excel 리포트**: 상세 데이터 및 성능 시트
- 자동 브라우저 열기

### 4. 디바이스 관리
- USB/무선 연결 자동 감지
- 다중 디바이스 지원
- 연결 상태 모니터링

## 🎯 코드 품질 개선

### Before vs After

| 항목 | Before | After |
|------|--------|-------|
| 파일 수 | 1개 (2835줄) | 11개 모듈 |
| 전역 변수 | 10+ 개 | 0개 (TestContext로 캡슐화) |
| 클래스 책임 | 단일 클래스가 모든 역할 | 역할별 클래스 분리 |
| 설정 관리 | 하드코딩 | config.py 중앙화 |
| 로깅 | 중복 설정 | 통합 logger.py |
| UI 업데이트 | 예외 무시 | safe_ui_update() 래퍼 |

### 테스트 가능성
- 각 모듈이 독립적으로 테스트 가능
- Mock 객체 사용 가능
- 의존성 주입 패턴 적용

### 확장성
- 새로운 테스트 도구 추가 용이
- 리포트 형식 확장 가능
- UI 테마 변경 용이

## 🐛 문제 해결

### 일반적인 문제
1. **디바이스 연결 실패**: ADB 드라이버 및 USB 디버깅 확인
2. **패키지 로드 실패**: 디바이스 권한 및 연결 상태 확인
3. **성능 모니터링 오류**: 디바이스 권한 및 앱 실행 상태 확인

### 로그 확인
```
logs/monkey_test.log  # 상세 로그
```

## 📈 향후 개선 계획

1. **테스트 시나리오 지원**: 커스텀 이벤트 시퀀스
2. **CI/CD 통합**: Jenkins/GitHub Actions 지원
3. **클라우드 리포팅**: 웹 대시보드 연동
4. **다중 디바이스 동시 테스트**
5. **AI 기반 이슈 분석**

## 📝 라이선스

이 프로젝트는 내부 사용을 위한 도구입니다.
