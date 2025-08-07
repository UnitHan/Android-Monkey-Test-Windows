#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
설정 및 상수 정의
"""
import os
import sys
from pathlib import Path
from src.utils.subprocess_utils import run_hidden_subprocess

# 테스트 프리셋 (정밀 계산 기반: 18분 정확도 최적화)
# Deep Test throttle 계산 공식:
# throttle = (target_seconds - overhead) × 1000 / (event_count × efficiency)
# 현재: (1080 - 23) × 1000 / (22000 × 0.37) = 130ms (22k 이벤트, 18분 정밀도)
PRESETS = {
    "Smoke Test": {"events": 3500, "seed": "random", "repeats": 5, "throttle": 250, "est_time": "35분"},
    "Quick Test": {"events": 7750, "seed": "random", "repeats": 5, "throttle": 220, "est_time": "50분"},
    "Standard Test": {"events": 12000, "seed": "random", "repeats": 6, "throttle": 200, "est_time": "1시간 30분"},
    "Deep Test": {"events": 22000, "seed": "random", "repeats": 10, "throttle": 130, "est_time": "3시간"},
    "Extreme Test": {"events": 32500, "seed": "random", "repeats": 15, "throttle": 100, "est_time": "8시간"},
    "재현테스트": {"events": 3000, "seed": "manual", "repeats": 5, "throttle": 300, "est_time": "30분", "manual_seed": True},
}


def get_base_dir():
    """실행 BASE_DIR 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 EXE 파일인 경우
        # EXE 파일이 위치한 폴더를 최우선으로 사용
        exe_dir = Path(sys.executable).parent
        
        # EXE 파일 위치에 직접 폴더 생성 시도
        try:
            exe_dir.mkdir(parents=True, exist_ok=True)
            # 쓰기 권한 테스트
            test_file = exe_dir / "write_test.tmp"
            test_file.write_text("test")
            test_file.unlink()
            
            # EXE 환경에서도 로그 폴더 미리 생성
            logs_dir = exe_dir / "logs"
            monkey_log_dir = exe_dir / "monkey_reports"
            performance_log_dir = exe_dir / "performance_logs"
            
            for dir_path in [logs_dir, monkey_log_dir, performance_log_dir]:
                dir_path.mkdir(exist_ok=True, parents=True)
            
            if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                print(f"✅ EXE 폴더 사용: {exe_dir}")
            return exe_dir
        except (PermissionError, OSError) as e:
            if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                print(f"⚠️ EXE 폴더 쓰기 실패: {exe_dir} - {e}")
        
        # EXE 폴더 쓰기가 실패하면 대체 폴더들 시도
        possible_dirs = [
            Path.home() / "AppData" / "Local" / "MonkeyTest",
            Path.home() / "Documents" / "MonkeyTest",
            Path.home() / "AppData" / "Local" / "Temp" / "MonkeyTest"
        ]
        
        for temp_dir in possible_dirs:
            try:
                temp_dir.mkdir(parents=True, exist_ok=True)
                # 쓰기 권한 테스트
                test_file = temp_dir / "write_test.tmp"
                test_file.write_text("test")
                test_file.unlink()
                if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                    print(f"✅ 데이터 폴더 설정: {temp_dir}")
                return temp_dir
            except (PermissionError, OSError) as e:
                if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                    print(f"⚠️ 폴더 접근 실패: {temp_dir} - {e}")
                continue
        
        # 모든 폴더가 실패하면 임시 폴더 사용
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "MonkeyTest"
        temp_dir.mkdir(parents=True, exist_ok=True)
        if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
            print(f"⚠️ 대체 폴더 사용: {temp_dir}")
        return temp_dir
    else:
        # 개발 환경인 경우 기존 방식 사용
        return Path(__file__).resolve().parent.parent

# 실행 환경에 따른 BASE_DIR 설정
BASE_DIR = get_base_dir()
LOGS_DIR = BASE_DIR / "logs"
MONKEY_LOG_DIR = BASE_DIR / "monkey_reports"
PERFORMANCE_LOG_DIR = BASE_DIR / "performance_logs"

# 디렉토리 생성 및 권한 확인
for dir_path in [LOGS_DIR, MONKEY_LOG_DIR, PERFORMANCE_LOG_DIR]:
    try:
        dir_path.mkdir(exist_ok=True, parents=True)
        # 쓰기 권한 테스트
        test_file = dir_path / "write_test.tmp"
        test_file.write_text("test", encoding='utf-8')
        test_file.unlink()
        if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
            print(f"✅ 폴더 권한 확인 완료: {dir_path}")
    except (PermissionError, OSError) as e:
        if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
            print(f"⚠️ 폴더 권한 문제: {dir_path} - {e}")
        # 대체 경로 시도
        import tempfile
        alt_path = Path(tempfile.gettempdir()) / "MonkeyTest" / dir_path.name
        try:
            alt_path.mkdir(exist_ok=True, parents=True)
            if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                print(f"🔄 대체 경로 사용: {alt_path}")
            globals()[dir_path.name.upper()] = alt_path
        except Exception as e2:
            if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                print(f"❌ 대체 경로도 실패: {e2}")

# ADB 설정 - EXE 빌드 시 동적 경로 설정
def get_adb_path():
    """ADB 경로를 동적으로 반환"""
    import sys
    import os
    import shutil
    import subprocess
    
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 경우
        possible_paths = []
        
        if hasattr(sys, '_MEIPASS'):
            # 임시 디렉토리에서 실행 중 - 더 많은 경로 시도
            meipass_path = getattr(sys, '_MEIPASS')
            possible_paths.extend([
                os.path.join(meipass_path, "adb_tools", "adb.exe"),
                os.path.join(meipass_path, "adb_tools", "platform-tools", "adb.exe"),
                os.path.join(meipass_path, "adb.exe")
            ])
        
        # 실행 파일 디렉토리에서 찾기 - 더 많은 경로 시도
        base_path = os.path.dirname(sys.executable)
        possible_paths.extend([
            os.path.join(base_path, "adb_tools", "platform-tools", "adb.exe"),
            os.path.join(base_path, "adb_tools", "adb.exe"),
            os.path.join(base_path, "adb.exe"),
            os.path.join(base_path, "..", "adb_tools", "platform-tools", "adb.exe"),  # 상위 폴더도 확인
            os.path.join(base_path, "..", "adb_tools", "adb.exe"),
        ])
        
        # 가능한 경로들을 순서대로 확인하고 실행 권한도 체크
        for adb_path in possible_paths:
            if os.path.exists(adb_path):
                try:
                    # 실행 권한 확인 (간단한 버전 체크)
                    # Windows에서 콘솔 창 숨김 설정
                    startupinfo = None
                    if os.name == 'nt':  # Windows
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                    
                    result = run_hidden_subprocess([adb_path, "version"], 
                                          capture_output=True, 
                                          text=True, 
                                          timeout=5,
                                          startupinfo=startupinfo)
                    if result.returncode == 0:
                        if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
                            print(f"✅ ADB 찾음 및 실행 확인: {adb_path}")
                        return adb_path
                except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                    # 실행 실패 시 다음 경로 시도
                    continue
    else:
        # 개발 환경에서 실행 중 - Android SDK 경로 우선 사용
        android_sdk_adb = os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe")
        if os.path.exists(android_sdk_adb):
            return android_sdk_adb
    
    # 시스템 PATH에서 adb 찾기 (마지막 수단)
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
            print(f"✅ 시스템 PATH에서 ADB 찾음: {adb_in_path}")
        return adb_in_path
    
    # 모든 방법이 실패하면 기본값 반환 (오류 메시지와 함께)
    if not getattr(sys, 'frozen', False):  # 개발 모드에서만 출력
        print("❌ ADB를 찾을 수 없습니다. adb.exe를 실행 파일과 같은 폴더에 배치해주세요.")
    return "adb"

ADB_PATH = get_adb_path()
DEFAULT_TIMEOUT = 30

# 시간 계산을 위한 오버헤드 상수 (정밀 계산 기반)
TIME_OVERHEAD = {
    "app_restart_per_repeat": 15,   # 각 반복당 앱 재시작 시간 (초)
    "logcat_setup": 5,              # 로그캣 설정 시간 (초)
    "monkey_startup": 8,            # Monkey 프로세스 시작 시간 (초)
    "performance_monitoring": 4,    # 성능 모니터링 오버헤드 (초)
    "cleanup_per_repeat": 5,        # 각 반복 정리 시간 (초)
    "final_report_generation": 20,  # 최종 리포트 생성 시간 (초)
    "buffer_percentage": 0.25,      # 예상치 못한 지연을 위한 25% 버퍼
    "throttle_efficiency": 0.35     # 실제 throttle 효율성 (35% - 보수적 추정)
}

# 키워드 상수
CRASH_KEYWORDS = [
    "FATAL EXCEPTION", "AndroidRuntime", "Process.*died", "Native crash",
    "tombstone", "signal 11", "signal 6", "SIGSEGV", "SIGABRT",
    "Fatal signal", "*** *** *** ***"
]

ANR_KEYWORDS = [
    "ANR in", "Application Not Responding", "Input dispatching timed out",
    "Broadcast timeout", "Service timeout", "ContentProvider timeout"
]

ERROR_KEYWORDS = [
    "OutOfMemoryError", "StackOverflowError", "NoClassDefFoundError",
    "ClassNotFoundException", "IllegalStateException"
]

# 성능 임계값
MEMORY_WARNING_THRESHOLD = 300  # MB
MEMORY_CRITICAL_THRESHOLD = 500  # MB
CPU_WARNING_THRESHOLD = 50  # %
CPU_CRITICAL_THRESHOLD = 80  # %

# ADB 패키지 조회 설정 (보안 강화 단말 대응)
PACKAGE_LIST_COMMANDS = [
    "shell pm list packages",           # 기본 명령어
    "shell pm list packages --user 0",  # 보안 강화 단말용 (권장)
    "shell pm list packages -3",        # 서드파티 앱만
    "shell pm list packages -u",        # 비활성화된 앱 포함
    "shell pm list packages --user current"  # 현재 사용자 패키지만
]

# GUI 설정 - 시각화 그래프가 한눈에 보이도록 창 크기 확대
WINDOW_SIZE = "1200x850"
MIN_WINDOW_SIZE = (1100, 600)

# 로깅 설정
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = "DEBUG"

def create_test_report_folder(package_name):
    """테스트 완료 후 패키지명과 타임스탬프로 구성된 폴더 생성"""
    import datetime
    import os
    
    # 안전한 패키지명으로 변환 (점을 언더스코어로 변경)
    safe_package_name = package_name.replace('.', '_') if package_name else "unknown_package"
    
    # 타임스탬프 생성
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 폴더명 생성 (원래 패키지명 유지)
    folder_name = f"{package_name}_{timestamp}"
    
    # 폴더 경로 생성
    folder_path = MONKEY_LOG_DIR / folder_name
    
    # 폴더 생성 (부모 디렉토리도 함께 생성)
    folder_path.mkdir(parents=True, exist_ok=True)
    
    return folder_path

def calculate_precise_throttle(target_minutes, event_count, efficiency=None):
    """정밀한 throttle 값 계산
    
    Args:
        target_minutes: 목표 실행 시간 (분)
        event_count: 이벤트 수
        efficiency: throttle 효율성 (기본값: TIME_OVERHEAD의 값 사용)
    
    Returns:
        int: 계산된 throttle 값 (ms)
    """
    if efficiency is None:
        efficiency = TIME_OVERHEAD["throttle_efficiency"]
    
    target_seconds = target_minutes * 60
    total_overhead = (TIME_OVERHEAD["app_restart_per_repeat"] + 
                     TIME_OVERHEAD["logcat_setup"] + 
                     TIME_OVERHEAD["monkey_startup"])
    
    actual_event_time = target_seconds - total_overhead
    throttle = (actual_event_time * 1000) / (event_count * efficiency)
    
    return int(throttle)

def get_optimized_deep_test_config():
    """Deep Test를 위한 최적화된 설정 반환 (22k 이벤트, 3시간 정확도)"""
    # 여러 효율성 옵션 제공 (더 보수적으로 조정)
    configs = {
        "conservative": calculate_precise_throttle(18, 22000, 0.36),  # 보수적 (36%) = 134ms
        "moderate": calculate_precise_throttle(18, 22000, 0.38),      # 적극적 (38%) = 127ms  
        "aggressive": calculate_precise_throttle(18, 22000, 0.40),    # 공격적 (40%) = 120ms
        "precise": calculate_precise_throttle(18, 22000, 0.37),       # 정밀 (37%) = 130ms - 추천
    }
    
    return configs

# 반복 실행 관련 설정
REPEAT_INTERVAL_MINUTES = 5  # 반복 실행 간격 (분)
MAX_REPEAT_CYCLES = 24  # 최대 반복 횟수 (24회 = 2시간)

# Gemini API 설정 (AI 기반 적응형 제어)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # 환경변수에서 로드
GEMINI_MODEL = "gemini-1.5-flash"  # 최신 안정 모델 (빠르고 효율적)

# 정밀 시간 계산 함수
def calculate_precise_duration(events, repeats, throttle_ms):
    """정밀한 테스트 시간 계산 (실제 측정 기반)"""
    # 기본 이벤트 시간
    base_event_time = events * throttle_ms / 1000  # 초 단위
    
    # 각 반복당 오버헤드
    per_repeat_overhead = (
        TIME_OVERHEAD["app_restart_per_repeat"] +
        TIME_OVERHEAD["logcat_setup"] +
        TIME_OVERHEAD["cleanup_per_repeat"]
    )
    
    # 전체 테스트 오버헤드
    total_overhead = (
        TIME_OVERHEAD["monkey_startup"] +
        TIME_OVERHEAD["performance_monitoring"] +
        TIME_OVERHEAD["final_report_generation"]
    )
    
    # 실제 throttle 효율성 적용
    actual_event_time = base_event_time / TIME_OVERHEAD["throttle_efficiency"]
    
    # 총 시간 계산
    total_time = (actual_event_time + per_repeat_overhead) * repeats + total_overhead
    
    # 버퍼 적용
    buffered_time = total_time * (1 + TIME_OVERHEAD["buffer_percentage"])
    
    # 시간 세부사항
    breakdown = {
        "pure_events": actual_event_time * repeats,
        "overhead_per_repeat": per_repeat_overhead * repeats,
        "total_overhead": total_overhead,
        "buffer": buffered_time - total_time,
        "total": buffered_time
    }
    
    return int(buffered_time), breakdown

# Deep Test 전용 정밀 계산 (18분 고정 실행)
def calculate_deep_test_duration():
    """Deep Test 18분 정확도를 위한 정밀 계산"""
    target_minutes = 18
    target_seconds = target_minutes * 60
    
    preset = PRESETS["Deep Test"]
    events = preset["events"]
    throttle = preset["throttle"]
    
    # 실제 측정 기반 효율성
    measured_efficiency = 0.37  # 37% (실제 테스트 결과 기반)
    
    # 오버헤드 계산
    startup_overhead = TIME_OVERHEAD["monkey_startup"]
    monitoring_overhead = TIME_OVERHEAD["performance_monitoring"]
    
    # 순수 이벤트 시간
    available_time = target_seconds - startup_overhead - monitoring_overhead
    
    # 필요한 throttle 역산
    required_throttle = (available_time * 1000) / (events * measured_efficiency)
    
    return {
        "target_seconds": target_seconds,
        "events": events,
        "recommended_throttle": int(required_throttle),
        "current_throttle": throttle,
        "efficiency": measured_efficiency,
        "estimated_accuracy": "±30초 이내"
    }
