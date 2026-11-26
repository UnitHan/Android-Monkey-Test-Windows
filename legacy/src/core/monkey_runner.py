#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey 테스트 실행 (원본 기능 복구)
"""
import os
import re
import time
import datetime
import threading
import subprocess
import queue
from typing import Dict, Any, List, Optional, Callable
from src.core.adb_client import AdbClient
from src.core.test_context import TestContext
from src.core.performance_monitor import PerformanceMonitor
from src.core.network_monitor import create_network_monitor
from src.core.adaptive_tuner import get_adaptive_tuner
from src.utils.performance_processor import PerformanceProcessor
from src.utils.execution_timer import RepeatExecutionTimer, format_duration
from src.utils.subprocess_utils import popen_hidden_subprocess, run_hidden_subprocess
from src.config import PRESETS, MONKEY_LOG_DIR, PERFORMANCE_LOG_DIR, CRASH_KEYWORDS, ANR_KEYWORDS, ERROR_KEYWORDS, TIME_OVERHEAD
from src.utils.logger import setup_logger
from src.ui.ui_utils import calculate_precise_duration

logger = setup_logger(__name__)

class MonkeyRunner:
    """Monkey 테스트 실행 클래스 (원본 기능 복구)"""
    
    def __init__(self, adb_client: AdbClient, test_context: TestContext):
        self.adb_client = adb_client
        self.test_context = test_context
        self.performance_monitor = PerformanceMonitor(adb_client, test_context)
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.progress_update_callback: Optional[Callable] = None
        
        # 모니터링 제어 플래그
        self.logcat_active = False
        self.monitoring_active = False
        
        # 정밀 시간 추적
        self.test_start_time = None
        self.estimated_total_seconds = 0
        self.actual_elapsed_seconds = 0
        
        # 반복 실행 타이머
        self.execution_timer = RepeatExecutionTimer()
        
        # 현재 반복의 Seed 값 저장 (결과 리포트용)
        self.current_repeat_seed = None
        
        # 🔥 새로운 기능들 초기화
        # 네트워크 모니터링 (device_serial이 있는 경우만)
        self.network_monitor = None
        if test_context.device_serial:
            self.network_monitor = create_network_monitor(adb_client, test_context.device_serial)
            self.network_monitor.set_recovery_callback(self._on_network_recovery)
        
        # Gemini AI 적응형 튜너
        self.adaptive_tuner = get_adaptive_tuner()
        
        # 적응형 파라미터 (실행 중 동적 조정)
        self.adaptive_events = None
        self.adaptive_throttle = None
        
        # 각 반복의 시작 시간 저장 (start_time 필드용)
        self.repeat_start_times = {}
        
        # 자동 보정 기능 관련 변수
        self.target_duration_per_repeat = 18 * 60  # 18분 = 1080초
        self.time_correction_history = []  # 보정 이력 저장
        self.current_throttle_adjustment = 0  # 현재 throttle 조정값
        
        # Deep Test 적응형 제어 변수
        self.deep_test_history = []  # Deep Test 성능 이력
        self.smoke_test_history = []  # Smoke Test 성능 이력
        self.quick_test_history = []  # Quick Test 성능 이력
        self.standard_test_history = []  # Standard Test 성능 이력
        self.extreme_test_history = []  # Extreme Test 성능 이력
        self.dynamic_throttle_enabled = True  # 동적 throttle 조절 활성화
        
        # 타임아웃 카운터 초기화
        self._current_timeout_count = 0
        
        # 공통 ANR/타임아웃 감지 설정 (모든 프리셋 적용)
        self.anr_timeout_threshold = 10  # ANR 감지 임계값 (초)
        self.response_timeout_threshold = 15  # 응답 타임아웃 (초)
        
        # Gemini API 기반 지능형 제어 (API 키가 있을 때만 활성화)
        self.gemini_controller = None
        self.gemini_enabled = False
        self._initialize_gemini_controller()
        
        # 앱 포그라운드 모니터링 (백그라운드 전환 시 자동 복구)
        self.foreground_monitor = None
        self.foreground_monitoring_enabled = True
    
    def _initialize_gemini_controller(self):
        """Gemini API 컨트롤러 초기화"""
        try:
            import os
            from src.utils.gemini_adaptive_controller import GeminiAdaptiveController
            
            # 환경변수 또는 설정에서 API 키 조회
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                # 설정 파일에서 조회 시도
                try:
                    from src.config import GEMINI_API_KEY
                    api_key = GEMINI_API_KEY
                except ImportError:
                    pass
            
            if api_key and api_key.strip():
                self.gemini_controller = GeminiAdaptiveController(api_key)
                self.gemini_enabled = True
                logger.info("🤖 Gemini AI 적응형 제어 활성화됨")
            else:
                logger.info("🔧 Gemini API 키 없음, 기본 적응형 제어 사용")
                
        except Exception as e:
            logger.warning(f"Gemini 컨트롤러 초기화 실패: {e}")
            self.gemini_enabled = False
    
    def _initialize_foreground_monitor(self, package_name: str):
        """앱 포그라운드 모니터 초기화"""
        try:
            from src.utils.app_foreground_monitor import AppForegroundMonitor
            from src.config import ADB_PATH
            
            self.foreground_monitor = AppForegroundMonitor(ADB_PATH, package_name)
            
            # 백그라운드 감지 시 호출될 콜백 설정
            def on_background_detected(message: str):
                logger.warning(f"📱 {message}")
                if self.progress_callback:
                    self.progress_callback(f"앱 복구: {message}", 0, 0)
            
            self.foreground_monitor.set_recovery_callback(on_background_detected)
            logger.info(f"🔍 앱 포그라운드 모니터 초기화 완료: {package_name}")
            
        except Exception as e:
            logger.warning(f"포그라운드 모니터 초기화 실패: {e}")
            self.foreground_monitor = None
    
    def start_foreground_monitoring(self, package_name: str):
        """앱 포그라운드 모니터링 시작"""
        try:
            if not self.foreground_monitoring_enabled:
                logger.debug("포그라운드 모니터링이 비활성화됨")
                return
            
            if not self.foreground_monitor:
                self._initialize_foreground_monitor(package_name)
            
            if self.foreground_monitor:
                self.foreground_monitor.start_monitoring()
                logger.info("🔍 앱 포그라운드 모니터링 시작됨")
            
        except Exception as e:
            logger.error(f"포그라운드 모니터링 시작 실패: {e}")
    
    def stop_foreground_monitoring(self):
        """앱 포그라운드 모니터링 중지"""
        try:
            if self.foreground_monitor:
                status = self.foreground_monitor.get_status()
                self.foreground_monitor.stop_monitoring()
                
                logger.info(f"🔍 앱 포그라운드 모니터링 중지됨")
                logger.info(f"   - 총 복구 횟수: {status.get('recovery_count', 0)}")
                
        except Exception as e:
            logger.error(f"포그라운드 모니터링 중지 실패: {e}")
    
    def get_foreground_monitor_status(self) -> dict:
        """포그라운드 모니터 상태 반환"""
        if self.foreground_monitor:
            return self.foreground_monitor.get_status()
        return {'monitoring': False, 'error': 'Monitor not initialized'}
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """진행 상황 콜백 설정"""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[bool, str], None]):
        """완료 콜백 설정"""
        self.completion_callback = callback
        
    def set_status_callback(self, callback: Callable[[str], None]):
        """상태 메시지 콜백 설정"""
        self.status_callback = callback
    
    def set_progress_update_callback(self, callback: Callable[[int, int, str], None]):
        """프로그래스바 업데이트 콜백 설정"""
        self.progress_update_callback = callback
    
    def start_test(self, repeat_mode: bool = False) -> bool:
        """테스트 시작 (반복 모드 선택 가능) - Gemini AI 적응형 최적화 및 네트워크 모니터링 포함"""
        if self.test_context.test_running:
            logger.warning("이미 테스트가 진행 중입니다.")
            return False
        
        if not self.test_context.app_package_name:
            logger.error("테스트할 앱이 선택되지 않았습니다.")
            return False
        
        # 🤖 Gemini AI 적응형 최적화 적용
        preset_name = getattr(self.test_context, 'test_preset', '')
        current_config = self.test_context.get_test_config()
        
        if preset_name in ["Deep Test", "Extreme Test", "Standard Test", "Quick Test", "Smoke Test"]:
            logger.info(f"🤖 Gemini AI 적응형 최적화 시작: {preset_name}")
            
            # 최적화된 파라미터 적용
            optimized_events, optimized_throttle = self._apply_adaptive_optimization(
                preset_name, current_config["events"], current_config["throttle"]
            )
            
            # 테스트 컨텍스트에 최적화된 값 적용
            if optimized_events != current_config["events"]:
                self.test_context.events = optimized_events
            if optimized_throttle != current_config["throttle"]:
                self.test_context.throttle = optimized_throttle
        
        # 디바이스 정보 업데이트
        self.test_context.update_device_info(self.adb_client)
        
        # 테스트 데이터 초기화
        self.test_context.reset_test_data()
        self.test_context.test_running = True
        
        # 🛜 네트워크 모니터링 시작
        self.start_network_monitoring()
        
        # 📱 백그라운드 모니터링 시작 (앱 포그라운드 유지)
        self.start_background_monitoring()
        
        # 요약 정보 즉시 업데이트
        summary = self.test_context.get_test_summary()
        summary["result_summary"] = "테스트 진행 중..."
        self.test_context.current_test_report["summary"] = summary
        
        # UI 즉시 업데이트 (요약 탭)
        if self.completion_callback:
            self.completion_callback(True, "UI_UPDATE_SUMMARY")
        
        # 정밀 시간 계산 (최적화된 파라미터 기준)
        final_config = self.test_context.get_test_config()
        self.estimated_total_seconds, time_breakdown = calculate_precise_duration(
            final_config["events"], 
            final_config["repeats"], 
            final_config["throttle"]
        )
        
        logger.info(f"테스트 시작 - 예상 시간: {self.estimated_total_seconds}초")
        logger.info(f"시간 세부사항: {time_breakdown}")
        
        if self.adaptive_events or self.adaptive_throttle:
            logger.info(f"🤖 적응형 파라미터 적용됨 - 이벤트: {final_config['events']}, 스로틀: {final_config['throttle']}ms")
            
        # 실제 테스트 실행
        threading.Thread(target=self._execute_test_with_timing, daemon=True).start()
        return True
    
    def _execute_test_with_timing(self):
        """정밀한 시간 추적과 함께 테스트 실행"""
        self.test_start_time = time.time()
        
        # 단일 테스트 실행
        success = self._run_single_test_cycle()
        
        # 테스트 완료 처리
        self._finalize_repeated_test()
    
    def _finalize_repeated_test(self):
        """테스트 완료 처리 - Gemini AI 학습 데이터 기록 포함"""
        try:
            # 🛜 네트워크 모니터링 중지
            self.stop_network_monitoring()
            
            # � 백그라운드 모니터링 중지
            self.stop_background_monitoring()
            
            # �🔍 앱 포그라운드 모니터링 중지
            self.stop_foreground_monitoring()
            
            # 🤖 Gemini AI 학습 데이터 기록 및 최적화 분석
            if hasattr(self, 'test_start_time') and self.test_start_time:
                actual_duration_seconds = time.time() - self.test_start_time
                actual_duration_minutes = actual_duration_seconds / 60
                
                # 현재 사용된 파라미터 가져오기
                final_config = self.test_context.get_test_config()
                preset_name = getattr(self.test_context, 'test_preset', '')
                
                if preset_name and preset_name in ["Deep Test", "Extreme Test", "Standard Test", "Quick Test", "Smoke Test"]:
                    self._record_test_result_for_learning(
                        preset_name, 
                        final_config["events"], 
                        final_config["throttle"], 
                        actual_duration_minutes
                    )
                    
                    # 🤖 Gemini API를 사용한 성능 분석 및 다음 실행 최적화
                    self._analyze_performance_with_gemini(
                        preset_name,
                        final_config,
                        actual_duration_minutes
                    )
                    
                    logger.info(f"🤖 Gemini 학습 완료: {preset_name} - {actual_duration_minutes:.1f}분 소요")
            
            self.test_context.test_running = False
            
        except Exception as e:
            logger.error(f"테스트 완료 처리 오류: {e}")
            self.test_context.test_running = False
    
    def _run_single_test_cycle(self) -> bool:
        """단일 테스트 사이클 실행"""
        package_name = self.test_context.app_package_name
        return self._run_monkey_test(package_name)

    def _run_monkey_test(self, package_name):
        """실제로 Monkey 테스트를 실행하고 로그를 수집합니다."""
        # 테스트 시작 시 로거 재설정 (패키지명 기반 로그 파일 생성)
        global logger
        from src.utils.logger import setup_logger
        
        logger.info(f"Monkey 테스트 시작: 패키지={package_name}")
        logger = setup_logger("monkey_test", package_name)
        logger.info(f"새로운 테스트 세션 시작: {package_name}")
        
        # 타임아웃 카운터 초기화
        self._current_timeout_count = 0
        
        current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 🔍 앱 포그라운드 모니터링 시작 (백그라운드 전환 시 자동 복구)
        self.start_foreground_monitoring(package_name)
        
        # 프리셋 설정 로드
        preset_data = self.test_context.get_test_config()
        events = preset_data["events"]
        seed = preset_data["seed"]
        repeats = preset_data["repeats"]
        throttle = preset_data["throttle"]
        
        logger.info(f"설정: events={events}, seed={seed}, repeats={repeats}, throttle={throttle}")
        logger.info(f"포그라운드 모니터링: {'활성화됨' if self.foreground_monitoring_enabled else '비활성화됨'}")

        # 테스트 요약 초기화 (디바이스 정보 포함)
        device_info = self.adb_client.get_device_info() if self.adb_client else {}
        device_name = device_info.get('model', 'Unknown Device')
        android_version = device_info.get('android_version', 'Unknown')
        device_serial = self.adb_client.device_serial if self.adb_client else ""
        connection_mode = "USB" if device_serial and ":" not in device_serial else "Wi-Fi"
        
        # 테스트 시작 시간 저장 (수행 시간 계산용)
        test_start_datetime = datetime.datetime.now()
        
        self.test_context.current_test_report["summary"] = {
            "test_target": f"{package_name}",
            "test_tool": "Android Monkey",
            "test_period": f"{test_start_datetime.strftime('%Y-%m-%d %H:%M')}",
            "test_start_time": test_start_datetime,  # 수행 시간 계산용
            "preset": f"{preset_data.get('preset_name', 'Custom')} ({events} events x {repeats}회)",
            "total_events": events * repeats,
            "device": f"{device_name} (Android {android_version})",
            "connection_mode": connection_mode,
            "result_summary": "테스트 진행 중..."
        }
        
        # 테스트 시작 시 바로 UI 업데이트 (completion_callback 재사용)
        if self.completion_callback:
            try:
                # UI 업데이트를 위한 특별한 시그널
                self.completion_callback(None, "UI_UPDATE_SUMMARY")
            except:
                pass
        
        # 상태 콜백 호출
        if self.status_callback:
            try:
                self.status_callback(f"테스트 시작: {repeats}회차 실행 준비 중...")
            except:
                pass

        all_crash_logs = []
        all_anr_logs = []
        all_logcats = []
        # 성능 데이터 초기화
        current_performance_data = []

        try:
            logger.info(f"총 {repeats}회차 테스트 시작!")
            logger.info(f"각 회차당 {events}개 이벤트, {throttle}ms 간격")
            
            # 전체 테스트 시간 측정 시작
            self.execution_timer.start_total()
            
            for i in range(1, repeats + 1):
                logger.info(f"\\n{'='*60}")
                logger.info(f"🚀 테스트 회차 {i}/{repeats} 시작!")
                logger.info(f"{'='*60}")
                
                # 반복별 시작 시간 기록 (차트 시간대 표시용)
                repeat_start_time = datetime.datetime.now()
                self.repeat_start_times[i] = repeat_start_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"반복 {i} 시작 시간: {self.repeat_start_times[i]}")
                
                # 테스트 중단 확인
                if not self.test_context.test_running:
                    logger.info(f"테스트가 중단되었습니다. 반복 {i}에서 종료.")
                    self.logcat_active = False
                    self.monitoring_active = False
                    break
                    
                logger.info(f"테스트 반복 {i}/{repeats} 시작")
                if self.status_callback:
                    try:
                        self.status_callback(f"테스트 진행 중: {i}/{repeats}회차...")
                    except:
                        pass
                
                # 프로그래스바 업데이트
                if self.progress_update_callback:
                    try:
                        self.progress_update_callback(i-1, repeats, f"테스트 {i}/{repeats}회차 시작")
                    except:
                        pass
                
                # 각 반복 시작 전 앱 재시작
                logger.info(f"반복 {i} 시작 전 앱 재시작")
                if not self._restart_app_before_test(package_name):
                    logger.warning(f"반복 {i} 앱 재시작 실패, 테스트 계속 진행")
                else:
                    logger.info(f"반복 {i} 앱 재시작 성공")
                    time.sleep(3)  # 앱 로딩 대기
                
                # 개별 반복 시간 측정 시작 (앱 재시작 후)
                self.execution_timer.start_repeat()

                # 반복별 Seed 결정
                from src.utils.random_seed_generator import RandomSeedGenerator
                from src.config import PRESETS
                
                preset_name = preset_data.get("preset_name", "Custom")
                
                if preset_name == "재현테스트":
                    # 재현테스트: 수동 입력된 시드 사용
                    current_seed = int(preset_data.get("seed", 1000))
                    logger.info(f"반복 {i} 재현테스트 수동 Seed 사용: {current_seed}")
                elif preset_name in PRESETS and PRESETS[preset_name].get("seed") == "random":
                    # 다른 프리셋들: 매 반복마다 새로운 랜덤 시드 생성
                    current_seed = int(RandomSeedGenerator.generate_seed())
                    logger.info(f"반복 {i} 자동 생성 Random Seed 사용: {current_seed}")
                elif preset_name == "Custom":
                    # 사용자 지정: 랜덤 시드 생성
                    current_seed = int(RandomSeedGenerator.generate_seed())
                    logger.info(f"반복 {i} 사용자 지정 Random Seed 사용: {current_seed}")
                else:
                    # 기본값 (기존 설정이 있다면 사용)
                    current_seed = int(preset_data.get("seed", RandomSeedGenerator.generate_seed()))
                    logger.info(f"반복 {i} 기본 Seed 사용: {current_seed}")
                
                # 현재 실행 중인 반복에 대한 Seed 값을 저장 (결과 리포트용)
                self.current_repeat_seed = current_seed

                # Monkey 명령어 구성 (Smoke Test/Quick Test/Standard Test/Deep Test/Extreme Test 최적화)
                # Smoke Test, Quick Test, Standard Test, Deep Test 및 Extreme Test의 경우 Gemini AI 적응형 제어 적용
                preset_data = self.test_context.get_test_config()
                is_smoke_test = preset_data.get('preset_name') == 'Smoke Test'
                is_quick_test = preset_data.get('preset_name') == 'Quick Test'
                is_standard_test = preset_data.get('preset_name') == 'Standard Test'
                is_deep_test = preset_data.get('preset_name') == 'Deep Test'
                is_extreme_test = preset_data.get('preset_name') == 'Extreme Test'
                
                if is_smoke_test or is_quick_test or is_standard_test or is_deep_test or is_extreme_test:
                    # Smoke Test/Quick Test/Standard Test/Deep Test/Extreme Test: 적응형 이벤트 수 + 시간 기반 제어
                    # 1차 실행에서 디바이스 성능 측정 후 이벤트 수 동적 조절
                    if is_smoke_test:
                        test_name = "Smoke Test"
                    elif is_quick_test:
                        test_name = "Quick Test"
                    elif is_standard_test:
                        test_name = "Standard Test"
                    elif is_deep_test:
                        test_name = "Deep Test"
                    else:
                        test_name = "Extreme Test"
                    
                    if i == 1:  # 첫 번째 회차
                        # 기본 이벤트 수로 시작 (성능 측정용)
                        adaptive_events = events
                        logger.info(f"🎯 {test_name} 1회차: 성능 측정 모드 ({adaptive_events:,}개 이벤트)")
                    else:
                        # 2회차부터는 1회차 결과 기반 적응형 조절
                        adaptive_events = self._calculate_adaptive_events(events, i, test_name)
                        logger.info(f"🎯 {test_name} {i}회차: 적응형 조절 ({adaptive_events:,}개 이벤트)")
                    
                    # throttle 값 설정 (Smoke Test: 250ms, Quick Test: 220ms, Standard Test: 200ms, Deep Test: 150ms, Extreme Test: 180ms)
                    if is_smoke_test:
                        adaptive_throttle = 250
                    elif is_quick_test:
                        adaptive_throttle = 220
                    elif is_standard_test:
                        adaptive_throttle = 200
                    elif is_deep_test:
                        adaptive_throttle = 150
                    else:  # is_extreme_test
                        adaptive_throttle = 180
                    
                    if is_smoke_test:
                        # Smoke Test: 표준 호환 설정으로 안정성 우선
                        full_monkey_command = (
                            f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey '
                            f'-p {package_name} '
                            f'--throttle {adaptive_throttle} '  # 최적화된 throttle 값
                            f'-s {current_seed} '  # 랜덤 시드
                            f'--ignore-crashes --ignore-security-exceptions '  # 모든 프리셋에서 타임아웃 감지
                            f'--monitor-native-crashes --kill-process-after-error '
                            f'--pct-touch 25 --pct-motion 20 --pct-trackball 0 --pct-nav 15 '
                            f'--pct-majornav 10 --pct-syskeys 5 --pct-appswitch 3 '
                            f'--pct-anyevent 22 --pct-pinchzoom 0 --pct-rotation 0 '
                            f'-v -v {adaptive_events}'
                        )
                    elif is_quick_test:
                        # Quick Test: 중강도 설정으로 균형 중시
                        full_monkey_command = (
                            f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey '
                            f'-p {package_name} '
                            f'--throttle {adaptive_throttle} '  # 최적화된 throttle 값
                            f'-s {current_seed} '  # 랜덤 시드
                            f'--ignore-crashes --ignore-security-exceptions '  # 모든 프리셋에서 타임아웃 감지
                            f'--monitor-native-crashes --kill-process-after-error '
                            f'--pct-touch 27 --pct-motion 25 --pct-trackball 0 --pct-nav 12 '
                            f'--pct-majornav 10 --pct-syskeys 5 --pct-appswitch 4 '
                            f'--pct-anyevent 17 --pct-pinchzoom 0 --pct-rotation 0 '
                            f'-v -v {adaptive_events}'
                        )
                    elif is_standard_test:
                        # Standard Test: 표준 품질 보증 테스트용 균형잡힌 고강도 설정
                        # ANR과 타임아웃을 정확히 감지하기 위해 --ignore-timeouts 제거
                        full_monkey_command = (
                            f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey '
                            f'-p {package_name} '
                            f'--throttle {adaptive_throttle} '  # 최적화된 throttle 값 (200ms)
                            f'-s {current_seed} '  # 랜덤 시드
                            f'--ignore-crashes --ignore-security-exceptions '  # timeouts는 감지하도록 제거
                            f'--monitor-native-crashes --kill-process-after-error '
                            f'--pct-touch 28 --pct-motion 23 --pct-trackball 0 --pct-nav 14 '
                            f'--pct-majornav 12 --pct-syskeys 6 --pct-appswitch 5 '
                            f'--pct-anyevent 12 --pct-pinchzoom 0 --pct-rotation 0 '
                            f'-v -v {adaptive_events}'
                        )
                    else:
                        # Deep Test/Extreme Test: 고강도 설정
                        full_monkey_command = (
                            f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey '
                            f'-p {package_name} '
                            f'--throttle {adaptive_throttle} '  # 최적화된 throttle 값
                            f'-s 4850 '  # 고정 시드
                            f'--ignore-crashes --ignore-security-exceptions '  # 모든 프리셋에서 타임아웃 감지
                            f'--monitor-native-crashes --kill-process-after-error '
                            f'--pct-touch 30 --pct-motion 30 --pct-nav 10 '
                            f'--pct-majornav 10 --pct-syskeys 5 --pct-appswitch 3 '
                            f'--pct-anyevent 10 --pct-pinchzoom 2 '
                            f'--bugreport -v -v {adaptive_events}'
                        )
                    
                    # 적응형 이벤트 수를 실제 실행에 반영
                    events = adaptive_events
                    
                    # 목표 시간 설정
                    if is_smoke_test:
                        target_time = 7  # Smoke Test: 7분
                    elif is_quick_test:
                        target_time = 10  # Quick Test: 10분 (50분 / 5회차)
                    elif is_standard_test:
                        target_time = 15  # Standard Test: 15분 (90분 / 6회차)
                    elif is_deep_test:
                        target_time = 18  # Deep Test: 18분
                    else:  # is_extreme_test
                        target_time = 32  # Extreme Test: 32분
                    
                    logger.info(f"🎯 {test_name} 모드: 적응형 {target_time}분 정확 실행 설정")
                    logger.info(f"  - Throttle: {adaptive_throttle}ms (고정)")
                    logger.info(f"  - Events: {adaptive_events:,}개 (적응형)")
                    if is_smoke_test or is_quick_test:
                        logger.info(f"  - Seed: {current_seed} (랜덤)")
                    else:
                        logger.info(f"  - Seed: 4850 (고정)")
                    logger.info(f"  - 동적 시간 제어: 활성화")
                else:
                    # 일반 테스트: 표준 호환 설정
                    full_monkey_command = (
                        f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey '
                        f'-p {package_name} '
                        f'--throttle {throttle} '
                        f'-s {current_seed} '
                        f'--ignore-crashes --ignore-security-exceptions '  # 모든 프리셋에서 타임아웃 감지
                        f'--monitor-native-crashes --kill-process-after-error '
                        f'--pct-touch 25 --pct-motion 20 --pct-trackball 0 --pct-nav 15 '
                        f'--pct-majornav 10 --pct-syskeys 5 --pct-appswitch 3 '
                        f'--pct-anyevent 22 --pct-pinchzoom 0 --pct-rotation 0 '
                        f'-v -v {events}'
                    )
                
                # 예상 실행 시간 계산 (더 정확한 계산)
                effective_throttle = throttle * TIME_OVERHEAD["throttle_efficiency"]
                expected_event_time = events * effective_throttle / 1000
                expected_total_time = expected_event_time + TIME_OVERHEAD["monkey_startup"] + TIME_OVERHEAD["performance_monitoring"]
                
                # Monkey 명령어 정확성 검증
                self._validate_monkey_command(full_monkey_command, events, throttle, is_deep_test or is_extreme_test)
                
                # Deep Test/Extreme Test의 경우 추가적인 시간 예측 로깅
                theoretical_time = events * throttle / 1000 / 60  # 이론상 시간 (분)
                practical_time = expected_total_time / 60  # 실제 예상 시간 (분)
                
                logger.info(f"반복 {i} 실행 정보:")
                logger.info(f"  이벤트 수: {events}")
                logger.info(f"  Throttle: {throttle}ms")
                logger.info(f"  이론상 실행 시간: {theoretical_time:.1f}분")
                logger.info(f"  실제 예상 시간: {practical_time:.1f}분")
                
                if is_smoke_test:
                    logger.info(f"  Smoke Test 목표: 7분/회차")
                    if practical_time < 5:  # Smoke Test의 경우 5분 미만이면 경고
                        logger.warning(f"⚠️ 예상 시간({practical_time:.1f}분)이 Smoke Test 목표(7분)보다 짧습니다.")
                elif is_quick_test:
                    logger.info(f"  Quick Test 목표: 10분/회차")
                    if practical_time < 8:  # Quick Test의 경우 8분 미만이면 경고
                        logger.warning(f"⚠️ 예상 시간({practical_time:.1f}분)이 Quick Test 목표(10분)보다 짧습니다.")
                elif is_standard_test:
                    logger.info(f"  Standard Test 목표: 15분/회차")
                    if practical_time < 12:  # Standard Test의 경우 12분 미만이면 경고
                        logger.warning(f"⚠️ 예상 시간({practical_time:.1f}분)이 Standard Test 목표(15분)보다 짧습니다.")
                elif is_deep_test:
                    logger.info(f"  Deep Test 목표: 18분/회차")
                    if practical_time < 15:  # Deep Test의 경우 15분 미만이면 경고
                        logger.warning(f"⚠️ 예상 시간({practical_time:.1f}분)이 Deep Test 목표(18분)보다 짧습니다.")
                elif is_extreme_test:
                    logger.info(f"  Extreme Test 목표: 32분/회차")
                    if practical_time < 28:  # Extreme Test의 경우 28분 미만이면 경고
                        logger.warning(f"⚠️ 예상 시간({practical_time:.1f}분)이 Extreme Test 목표(32분)보다 짧습니다.")
                
                logger.info(f"반복 {i} 실행 정보:")
                logger.info(f"  이벤트 수: {events}")
                logger.info(f"  Seed: {current_seed}")
                logger.info(f"  Throttle: {throttle}ms")
                logger.info(f"  예상 순수 이벤트 시간: {expected_event_time:.1f}초")
                logger.info(f"  예상 총 실행 시간: {expected_total_time:.1f}초")
                logger.info(f"  몽키 명령어: {full_monkey_command}")
                
                # 앱이 실제로 실행 중인지 확인
                app_pid = self.adb_client.get_main_process_pid(package_name)
                if app_pid is None:
                    logger.warning(f"앱이 실행되지 않은 상태에서 몽키 테스트 시작: {package_name}")
                else:
                    logger.info(f"앱 실행 확인됨: PID {app_pid}")
                
                logger.info("로그캣 및 성능 모니터링 시작")
                
                # 로그캣 모니터링 시작
                self.logcat_active = True
                
                # ADB 경로와 device_serial 검증
                if not self.adb_client.adb_path or not self.adb_client.device_serial:
                    logger.error("ADB 경로 또는 장치 시리얼이 설정되지 않았습니다")
                    continue
                
                adb_path = str(self.adb_client.adb_path)
                device_serial = str(self.adb_client.device_serial)
                
                # logcat 초기화 및 시작
                logcat_process = popen_hidden_subprocess(
                    [adb_path, "-s", device_serial, "logcat", "-c"], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logcat_process.wait()
                
                logcat_process = popen_hidden_subprocess(
                    [adb_path, "-s", device_serial, "logcat"], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
                )
                
                logcat_reader_thread = threading.Thread(
                    target=self._read_logcat, 
                    args=(logcat_process, i, package_name, all_crash_logs, all_anr_logs, all_logcats)
                )
                logcat_reader_thread.daemon = True
                logcat_reader_thread.start()

                # 성능 모니터링 시작
                self.monitoring_active = True
                performance_thread = threading.Thread(
                    target=self._monitor_performance, 
                    args=(package_name, i, current_performance_data)
                )
                performance_thread.daemon = True
                performance_thread.start()

                # Monkey 테스트 실행 (원본과 동일하게 shell=True 사용)
                logger.info(f"Monkey 명령어 실행: {full_monkey_command}")
                
                # 시작 시간 기록
                start_time = time.time()
                
                monkey_run_process = popen_hidden_subprocess(
                    full_monkey_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    shell=True
                )

                # 프로세스 시작 확인 및 상세 디버깅
                initial_check_time = time.time()
                time.sleep(3)  # 조금 더 긴 대기 시간
                if monkey_run_process.poll() is not None:
                    # 프로세스가 이미 종료됨 - 상세 오류 분석
                    stdout, stderr = monkey_run_process.communicate()
                    return_code = monkey_run_process.returncode
                    startup_duration = time.time() - initial_check_time
                    
                    logger.error(f"🚨 Monkey 프로세스 조기 종료 감지 - 반복 {i}")
                    logger.error(f"🚨 종료 코드: {return_code}")
                    logger.error(f"🚨 시작 후 종료까지: {startup_duration:.1f}초")
                    logger.error(f"🚨 명령어: {full_monkey_command}")
                    logger.error(f"🚨 Monkey stdout ({len(stdout)} chars): {stdout[:1000]}...")
                    logger.error(f"🚨 Monkey stderr ({len(stderr)} chars): {stderr[:1000]}...")
                    
                    # 앱 상태 확인
                    app_pid = self.adb_client.get_main_process_pid(package_name)
                    logger.error(f"🚨 앱 상태 PID: {app_pid}")
                    
                    # ADB 연결 상태 확인
                    device_status = self.adb_client.run_command("devices")
                    logger.error(f"🚨 디바이스 상태: {device_status[:200]}...")
                    
                    # 모니터링 종료
                    self.logcat_active = False
                    self.monitoring_active = False
                    try:
                        logcat_process.terminate()
                        logcat_process.wait(timeout=2)
                    except:
                        try:
                            logcat_process.kill()
                        except:
                            pass
                    
                    # Deep Test/Extreme Test/Standard Test/Quick Test/Smoke Test의 경우 추가 정보 출력
                    preset_data = self.test_context.get_test_config()
                    if preset_data.get('preset_name') == 'Smoke Test':
                        logger.error(f"🚨 Smoke Test 조기 종료: 7분 대신 {startup_duration:.1f}초만 실행됨")
                        logger.error(f"🚨 원인 분석 필요: 명령어 구문, 앱 상태, ADB 연결 등 확인")
                    elif preset_data.get('preset_name') == 'Quick Test':
                        logger.error(f"🚨 Quick Test 조기 종료: 10분 대신 {startup_duration:.1f}초만 실행됨")
                        logger.error(f"🚨 원인 분석 필요: 명령어 구문, 앱 상태, ADB 연결 등 확인")
                    elif preset_data.get('preset_name') == 'Standard Test':
                        logger.error(f"🚨 Standard Test 조기 종료: 15분 대신 {startup_duration:.1f}초만 실행됨")
                        logger.error(f"🚨 원인 분석 필요: 명령어 구문, 앱 상태, ADB 연결 등 확인")
                    elif preset_data.get('preset_name') == 'Deep Test':
                        logger.error(f"🚨 Deep Test 조기 종료: 18분 대신 {startup_duration:.1f}초만 실행됨")
                        logger.error(f"🚨 원인 분석 필요: 명령어 구문, 앱 상태, ADB 연결 등 확인")
                    elif preset_data.get('preset_name') == 'Extreme Test':
                        logger.error(f"🚨 Extreme Test 조기 종료: 32분 대신 {startup_duration:.1f}초만 실행됨")
                        logger.error(f"🚨 원인 분석 필요: 명령어 구문, 앱 상태, ADB 연결 등 확인")
                    
                    # 다음 반복으로 건너뛰기
                    logger.warning(f"반복 {i} 건너뛰기 - Monkey 프로세스 시작 실패")
                    continue

                # Monkey 프로세스 완료 대기 및 정밀한 시간 추적
                actual_monkey_elapsed, detected_events = self._wait_for_monkey_completion(monkey_run_process, i, events, throttle, start_time)

                # 모니터링 중지
                self.logcat_active = False
                self.monitoring_active = False
                
                # 프로세스 정리
                try:
                    logcat_process.terminate()
                    logcat_process.wait(timeout=2)
                except:
                    pass

                # 개별 반복 시간 측정 종료
                execution_timer_duration = self.execution_timer.stop_repeat()
                
                # 더 일관된 시간 표시: ExecutionTimer 결과를 기본으로 사용
                # 실제 Monkey 실행 시간이 비정상적으로 짧은 경우에만 경고
                if actual_monkey_elapsed < execution_timer_duration * 0.1:
                    logger.warning(f"⚠️ 반복 {i}: Monkey 실행 시간이 비정상적으로 짧음 (Monkey: {actual_monkey_elapsed:.1f}초, Timer: {execution_timer_duration:.1f}초)")
                    # 비정상적인 경우에는 ExecutionTimer 결과 사용
                    final_duration = execution_timer_duration
                    duration_source = "ExecutionTimer (복구됨)"
                else:
                    # 정상적인 경우에는 더 정확한 Monkey 실행 시간 사용
                    final_duration = actual_monkey_elapsed
                    duration_source = "Monkey 실행시간"
                
                # 일관된 시간 표시
                consistent_duration_str = format_duration(final_duration)
                
                logger.info(f"반복 {i} 완료:")
                logger.info(f"  실행 시간: {consistent_duration_str} ({duration_source})")
                logger.info(f"  ExecutionTimer: {format_duration(execution_timer_duration)}")
                logger.info(f"  Monkey 측정: {format_duration(actual_monkey_elapsed)}")
                logger.info(f"  감지된 이벤트 수: {detected_events}/{events}")
                
                # 진행 상황 업데이트
                if self.progress_callback:
                    try:
                        self.progress_callback(f"반복 {i} 완료", i, repeats)
                    except:
                        pass
                
                # 프로그래스바 업데이트
                if self.progress_update_callback:
                    try:
                        self.progress_update_callback(i, repeats, f"테스트 {i}/{repeats}회차 완료")
                    except:
                        pass

                # 결과를 details에 추가 (일관된 실행 시간 사용)
                self._add_run_result_to_details(i, consistent_duration_str, events, all_crash_logs, all_anr_logs, current_performance_data)
                
                # 반복 사이 대기
                if i < repeats:
                    time.sleep(2)
            
            # 전체 테스트 시간 측정 종료
            total_duration = self.execution_timer.stop_total()
            logger.info(f"전체 테스트 완료: {format_duration(total_duration)}")
            
            # 테스트 완료 처리
            self._finalize_test_results(all_crash_logs, all_anr_logs, current_performance_data)
            return True
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
            if self.completion_callback:
                try:
                    self.completion_callback(False, f"테스트 실행 중 오류: {e}")
                except:
                    pass
            return False
        finally:
            # 모든 모니터링 프로세스 완전 정지
            self.test_context.test_running = False
            self.logcat_active = False
            self.monitoring_active = False
            
            # 백그라운드 모니터링 중지 (포그라운드 모니터 포함)
            try:
                self.stop_background_monitoring()
            except Exception as bg_error:
                logger.error(f"백그라운드 모니터링 중지 실패: {bg_error}")
            
            # 포그라운드 모니터링 완전 중지
            try:
                if hasattr(self, 'foreground_monitor') and self.foreground_monitor:
                    logger.info("finally 블록: 포그라운드 모니터링 강제 중지")
                    self.foreground_monitor.stop_monitoring()
                    self.foreground_monitor = None
            except Exception as fg_error:
                logger.warning(f"finally 블록에서 포그라운드 모니터링 중지 실패: {fg_error}")
            
            if self.status_callback:
                try:
                    self.status_callback("테스트 완료")
                except:
                    pass

    def _restart_app_before_test(self, package_name):
        """테스트 전 앱 재시작 (연결 복구 + 완전한 캐시 정리 포함)"""
        try:
            logger.info(f"앱 재시작 및 캐시 정리 시작: {package_name}")
            
            # 1. 장치 연결 상태 확인 및 복구
            if not self._ensure_device_connection():
                logger.error("장치 연결 복구 실패")
                return False
            
            # 2. 앱 강제 종료 (모든 프로세스)
            logger.info("앱 강제 종료 중...")
            kill_result = self.adb_client.run_command(f"shell am force-stop {package_name}")
            if kill_result and "device offline" in kill_result.lower():
                logger.warning("앱 종료 중 device offline 감지, 연결 복구 시도")
                if not self._recover_device_connection():
                    logger.error("연결 복구 실패")
                    return False
                # 복구 후 재시도
                kill_result = self.adb_client.run_command(f"shell am force-stop {package_name}")
            
            # 3. 프로세스 완전 종료 확인
            time.sleep(2)
            # 프로세스 PID로 확인
            pid = self.adb_client.get_main_process_pid(package_name)
            if pid:
                logger.info("강제 프로세스 종료 실행")
                # PID로 강제 종료
                self.adb_client.run_command(f"shell kill -9 {pid}")
                logger.info(f"PID {pid} 강제 종료")
                time.sleep(1)
            
            # 4. 간단한 백그라운드 정리만 (권한 문제 회피)
            logger.info("백그라운드 앱 정리...")
            # 권한이 필요 없는 안전한 정리만 수행
            self.adb_client.run_command("shell am kill-all")  # 백그라운드 앱 정리
            logger.info("✅ 백그라운드 정리 완료")
            time.sleep(1)
            
            # 5. 앱 시작
            logger.info("앱 시작...")
            start_result = self.adb_client.run_command(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
            if start_result and "device offline" in start_result.lower():
                logger.warning("앱 시작 중 device offline 감지, 연결 복구 시도")
                if not self._recover_device_connection():
                    logger.error("연결 복구 실패")
                    return False
                # 복구 후 재시도
                start_result = self.adb_client.run_command(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
            
            if start_result and start_result.startswith("Error:"):
                logger.warning(f"앱 시작 실패: {start_result}")
                return False
            else:
                logger.info(f"✅ 앱 시작 성공: {package_name}")
                
                # 6. 앱 완전 로딩 대기
                logger.info("앱 완전 로딩 대기...")
                time.sleep(5)  # 더 긴 로딩 대기
                
                # 7. 앱 실행 상태 재확인
                # PID로 앱 실행 확인
                final_pid = self.adb_client.get_main_process_pid(package_name)
                if final_pid:
                    logger.info("✅ 앱 실행 상태 확인 완료")
                    return True
                else:
                    logger.warning("앱 실행 상태 확인 실패")
                    return False
                
        except Exception as e:
            logger.error(f"앱 재시작 및 캐시 정리 중 오류: {e}")
            return False

    def _ensure_device_connection(self):
        """장치 연결 상태 확인"""
        try:
            # 간단한 adb 명령어로 연결 상태 확인
            result = self.adb_client.run_command("devices")
            if "device offline" in result.lower() or "no devices/emulators found" in result.lower():
                logger.warning("장치가 offline 상태 또는 연결되지 않음")
                return False
            return True
        except Exception as e:
            logger.error(f"장치 연결 상태 확인 실패: {e}")
            return False

    def _recover_device_connection(self):
        """장치 연결 복구 시도"""
        try:
            logger.info("🔄 장치 연결 복구 시작...")
            
            # 사용자에게 복구 시도 알림
            if self.status_callback:
                try:
                    self.status_callback("🔄 장치 연결 복구 중...")
                except:
                    pass
            
            # 무선 연결인지 확인
            if (self.test_context.is_wireless_mode and 
                self.adb_client.device_serial and 
                ":" in self.adb_client.device_serial):
                return self._recover_wireless_connection()
            else:
                return self._recover_usb_connection()
                
        except Exception as e:
            logger.error(f"연결 복구 중 오류: {e}")
            return False

    def _recover_wireless_connection(self):
        """무선 연결 복구"""
        try:
            device_ip = self.adb_client.device_serial
            logger.info(f"🔄 무선 연결 복구 시도: {device_ip}")
            
            # 사용자에게 무선 복구 시도 알림
            if self.status_callback:
                try:
                    self.status_callback(f"📶 무선 연결 복구 중: {device_ip}")
                except:
                    pass
            
            # 1. 기존 연결 끊기
            logger.info("기존 무선 연결 끊기...")
            self.adb_client.run_command(f"disconnect {device_ip}")
            time.sleep(2)
            
            # 2. 재연결 시도 (최대 3회)
            for attempt in range(3):
                logger.info(f"무선 재연결 시도 {attempt + 1}/3...")
                
                # 사용자에게 시도 횟수 알림
                if self.status_callback:
                    try:
                        self.status_callback(f"📶 무선 재연결 시도 {attempt + 1}/3")
                    except:
                        pass
                
                connect_result = self.adb_client.run_command(f"connect {device_ip}")
                
                if "connected to" in connect_result.lower():
                    logger.info(f"✅ 무선 연결 복구 성공: {device_ip}")
                    
                    # 사용자에게 복구 성공 알림
                    if self.status_callback:
                        try:
                            self.status_callback(f"✅ 무선 연결 복구 성공: {device_ip}")
                        except:
                            pass
                    
                    time.sleep(2)  # 연결 안정화 대기
                    
                    # 연결 확인
                    if self._verify_connection():
                        return True
                else:
                    logger.warning(f"무선 연결 시도 {attempt + 1} 실패: {connect_result}")
                    time.sleep(3)
            
            logger.error("무선 연결 복구 실패")
            
            # 사용자에게 복구 실패 알림
            if self.status_callback:
                try:
                    self.status_callback("❌ 무선 연결 복구 실패")
                except:
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"무선 연결 복구 중 오류: {e}")
            return False

    def _recover_usb_connection(self):
        """USB 연결 복구"""
        try:
            logger.info("🔄 USB 연결 복구 시도...")
            
            # 사용자에게 USB 복구 시도 알림
            if self.status_callback:
                try:
                    self.status_callback("🔌 USB 연결 복구 중...")
                except:
                    pass
            
            # 1. adb 서버 재시작
            logger.info("ADB 서버 재시작...")
            if self.status_callback:
                try:
                    self.status_callback("🔄 ADB 서버 재시작 중...")
                except:
                    pass
            
            self.adb_client.run_command("kill-server")
            time.sleep(2)
            self.adb_client.run_command("start-server")
            time.sleep(3)
            
            # 2. 장치 대기
            logger.info("장치 연결 대기...")
            if self.status_callback:
                try:
                    self.status_callback("⏳ 장치 연결 대기 중...")
                except:
                    pass
            
            wait_result = self.adb_client.run_command("wait-for-device")
            time.sleep(2)
            
            # 3. 연결 확인
            if self._verify_connection():
                logger.info("✅ USB 연결 복구 성공")
                
                # 사용자에게 복구 성공 알림
                if self.status_callback:
                    try:
                        self.status_callback("✅ USB 연결 복구 성공")
                    except:
                        pass
                
                return True
            else:
                logger.error("USB 연결 복구 실패")
                
                # 사용자에게 복구 실패 알림
                if self.status_callback:
                    try:
                        self.status_callback("❌ USB 연결 복구 실패")
                    except:
                        pass
                
                return False
                
        except Exception as e:
            logger.error(f"USB 연결 복구 중 오류: {e}")
            return False

    def _verify_connection(self):
        """연결 상태 검증"""
        try:
            # 1. 장치 목록 확인
            devices_result = self.adb_client.run_command("devices")
            if "device" not in devices_result or "offline" in devices_result:
                return False
            
            # 2. 간단한 shell 명령어 실행 테스트
            test_result = self.adb_client.run_command("shell echo 'connection_test'")
            if "connection_test" in test_result and "offline" not in test_result.lower():
                logger.info("연결 상태 검증 성공")
                return True
            else:
                logger.warning(f"연결 검증 실패: {test_result}")
                return False
                
        except Exception as e:
            logger.error(f"연결 검증 중 오류: {e}")
            return False

    def _handle_device_offline_during_test(self, run_num):
        """테스트 중 device offline 상황 처리"""
        try:
            logger.warning(f"🔄 반복 {run_num} 중 device offline 처리 시작...")
            
            # 1. 현재 상태 확인
            if not self._ensure_device_connection():
                logger.warning(f"반복 {run_num}: 장치 연결 끊어짐 확인됨")
                
                # 2. 연결 복구 시도
                if self._recover_device_connection():
                    logger.info(f"✅ 반복 {run_num}: 장치 연결 복구 성공")
                    
                    # 3. 복구 후 짧은 대기
                    time.sleep(3)
                    
                    # 4. 연결 재확인
                    if self._verify_connection():
                        logger.info(f"✅ 반복 {run_num}: 연결 복구 검증 완료")
                        return True
                    else:
                        logger.error(f"❌ 반복 {run_num}: 연결 복구 검증 실패")
                        return False
                else:
                    logger.error(f"❌ 반복 {run_num}: 장치 연결 복구 실패")
                    return False
            else:
                logger.info(f"반복 {run_num}: 장치 연결 정상 (일시적 문제였을 수 있음)")
                return True
                
        except Exception as e:
            logger.error(f"반복 {run_num} offline 처리 중 오류: {e}")
            return False

    def _wait_for_monkey_completion(self, monkey_run_process, run_num, events, throttle, start_time):
        """Monkey 프로세스 완료 대기 및 정밀한 시간 추적 (Deep Test 18분/Extreme Test 32분 정확 실행 포함)"""
        
        monkey_output_lines = []
        monkey_error_lines = []
        
        # Smoke Test/Quick Test/Deep Test/Extreme Test 모드 감지
        preset_data = self.test_context.get_test_config()
        is_smoke_test = preset_data.get('preset_name') == 'Smoke Test'
        is_quick_test = preset_data.get('preset_name') == 'Quick Test'
        is_deep_test = preset_data.get('preset_name') == 'Deep Test'
        is_extreme_test = preset_data.get('preset_name') == 'Extreme Test'
        
        # 변수 초기화
        expected_event_time = 0
        expected_overhead = 0
        
        if is_smoke_test:
            target_duration = 7 * 60  # Smoke Test: 7분 (420초)
            logger.info(f"🎯 Smoke Test 모드: 정확히 {target_duration/60}분 실행 목표")
            expected_total_time = target_duration
        elif is_quick_test:
            target_duration = 10 * 60  # Quick Test: 10분 (600초)
            logger.info(f"🎯 Quick Test 모드: 정확히 {target_duration/60}분 실행 목표")
            expected_total_time = target_duration
        elif is_deep_test:
            target_duration = 18 * 60  # Deep Test: 18분 (1080초)
            logger.info(f"🎯 Deep Test 모드: 정확히 {target_duration/60}분 실행 목표")
            expected_total_time = target_duration
        elif is_extreme_test:
            target_duration = 32 * 60  # Extreme Test: 32분 (1920초)
            logger.info(f"🎯 Extreme Test 모드: 정확히 {target_duration/60}분 실행 목표")
            expected_total_time = target_duration
        else:
            target_duration = 0  # 일반 테스트
            # 기존 로직: 정밀한 시간 계산 (실제 테스트 기반 보정)
            effective_throttle = throttle * TIME_OVERHEAD["throttle_efficiency"]
            expected_event_time = events * effective_throttle / 1000  # 순수 이벤트 시간 (초)
            expected_overhead = TIME_OVERHEAD["monkey_startup"] + TIME_OVERHEAD["performance_monitoring"]
            expected_total_time = expected_event_time + expected_overhead
            
        # 타임아웃 설정
        if is_smoke_test or is_quick_test or is_deep_test or is_extreme_test:
            max_wait_time = target_duration + 120  # 목표 시간 + 2분 여유
            no_activity_timeout = 180  # 3분 무활동 허용
        else:
            # 타임아웃 설정
            if expected_total_time > 600:  # 10분 이상인 경우
                max_wait_time = expected_total_time * 1.2 + 120  # 예상 시간의 1.2배 + 2분
                no_activity_timeout = min(180, expected_total_time * 0.08)  # 최대 3분 또는 예상시간의 8%
            else:
                max_wait_time = expected_total_time * 1.5 + 60  # 예상 시간의 1.5배 + 1분
                no_activity_timeout = min(60, expected_total_time * 0.2)  # 60초 또는 예상시간의 20%
        
        logger.info(f"반복 {run_num} 시간 설정:")
        if is_smoke_test:
            logger.info(f"  Smoke Test 목표 시간: {expected_total_time/60:.1f}분")
            logger.info(f"  동적 시간 제어: 활성화")
        elif is_quick_test:
            logger.info(f"  Quick Test 목표 시간: {expected_total_time/60:.1f}분")
            logger.info(f"  동적 시간 제어: 활성화")
        elif is_deep_test:
            logger.info(f"  Deep Test 목표 시간: {expected_total_time/60:.1f}분")
            logger.info(f"  동적 시간 제어: 활성화")
        elif is_extreme_test:
            logger.info(f"  Extreme Test 목표 시간: {expected_total_time/60:.1f}분")
            logger.info(f"  동적 시간 제어: 활성화")
        else:
            logger.info(f"  순수 이벤트 시간: {expected_event_time:.1f}초")
            logger.info(f"  오버헤드: {expected_overhead:.1f}초")
            logger.info(f"  총 예상 시간: {expected_total_time:.1f}초")
        logger.info(f"  최대 대기 시간: {max_wait_time/60:.1f}분")
        logger.info(f"  무활동 타임아웃: {no_activity_timeout}초")
        
        # 진행률 업데이트를 위한 카운터
        last_progress_update = time.time()
        last_event_time = time.time()
        last_reported_progress = 0
        
        # 시간 기반 진행률 추적
        time_based_progress = 0
        event_based_progress = 0
        
        # 프로세스 모니터링 설정 (Deep Test 등 긴 테스트 고려)
        process_started = False
        
        # Deep Test나 긴 테스트의 경우 적절한 타임아웃 설정
        if expected_total_time > 600:  # 10분 이상인 경우 (Deep Test 등)
            max_wait_time = expected_total_time * 1.2 + 120  # 예상 시간의 1.2배 + 2분
            no_activity_timeout = min(180, expected_total_time * 0.08)  # 최대 3분 또는 예상시간의 8%
            logger.info(f"⏰ Deep Test 모드: 최대 대기 {max_wait_time/60:.1f}분, 무활동 타임아웃 {no_activity_timeout}초")
        else:
            max_wait_time = expected_total_time * 1.5 + 60  # 예상 시간의 1.5배 + 1분
            no_activity_timeout = min(60, expected_total_time * 0.2)  # 60초 또는 예상시간의 20%
            logger.info(f"⏰ 일반 테스트 모드: 최대 대기 {max_wait_time/60:.1f}분, 무활동 타임아웃 {no_activity_timeout}초")
        
        # 실시간 출력 읽기를 위한 큐
        stdout_queue = queue.Queue()
        stderr_queue = queue.Queue()
        
        def read_stdout():
            try:
                for line in iter(monkey_run_process.stdout.readline, ''):
                    if line:
                        stdout_queue.put(line.strip())
            except:
                pass
        
        def read_stderr():
            try:
                for line in iter(monkey_run_process.stderr.readline, ''):
                    if line:
                        stderr_queue.put(line.strip())
            except:
                pass
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        
        event_count = 0
        significant_events = 0  # 의미있는 이벤트 카운터
        
        while monkey_run_process.poll() is None:
            if not process_started:
                process_started = True
                logger.info(f"Monkey 프로세스 시작됨 - PID: {monkey_run_process.pid}")
            
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # stdout에서 새 라인 읽기 및 이벤트 감지
            try:
                while not stdout_queue.empty():
                    line = stdout_queue.get_nowait()
                    if line:
                        monkey_output_lines.append(line)
                        
                        # 더 정확한 이벤트 패턴 감지 (Deep Test 최적화)
                        event_patterns = [
                            'sending event', 'send event', 'injecting', 'inject',
                            'touch event', 'key event', 'motion event', 'nav event',
                            'events injected:', 'events sent:', ':sending'  # monkey 실제 로그 패턴
                        ]
                        
                        line_lower = line.lower()
                        event_detected = False
                        
                        # 이벤트 패턴 확인
                        for pattern in event_patterns:
                            if pattern in line_lower:
                                event_count += 1
                                significant_events += 1
                                last_event_time = current_time
                                event_detected = True
                                
                                # Deep Test의 경우 더 상세한 로깅 (처음 100개와 마지막 100개)
                                if (significant_events <= 100 or significant_events % 1000 == 0 or 
                                    significant_events >= events - 100):
                                    logger.info(f"이벤트 진행: {significant_events}/{events} - {line[:80]}")
                                else:
                                    logger.debug(f"이벤트 감지 #{event_count}: {line[:100]}")
                                break
                        
                        # Monkey 완료 메시지 감지 (100% 완료 확인)
                        if not event_detected and ('events injected' in line_lower or 
                                                  'monkey finished' in line_lower):
                            logger.info(f"🏁 Monkey 완료 메시지 감지: {line}")
                            
                            # 정확히 모든 이벤트가 실행되었는지 확인
                            completion_percentage = (significant_events / events) * 100
                            if significant_events >= events:
                                logger.info(f"✅ 모든 이벤트 완료: {significant_events}/{events} (100%)")
                            elif significant_events >= events * 0.98:  # 98% 이상이면 허용
                                logger.warning(f"⚠️ 거의 완료: {significant_events}/{events} ({completion_percentage:.1f}%)")
                            else:
                                logger.error(f"❌ 조기 종료: {significant_events}/{events} ({completion_percentage:.1f}%)")
                                if events >= 10000:  # Deep Test급 테스트
                                    logger.error(f"❌ Deep Test 불완전 실행: {events - significant_events}개 이벤트 누락")
                                    # 불완전 실행 시 프로세스 계속 실행하도록 처리
                                    continue
                        
                        # Monkey 중단/실패 메시지 감지
                        elif ('monkey aborted' in line_lower or 'killing monkey' in line_lower or
                              'monkey stopped' in line_lower or 'crash' in line_lower):
                            logger.warning(f"🚨 Monkey 중단/오류 감지: {line}")
                            if significant_events < events * 0.9:  # 90% 미만이면 문제
                                logger.error(f"🚨 심각한 조기 종료: {significant_events}/{events} ({significant_events/events*100:.1f}%)")
            except queue.Empty:
                pass
            
            # stderr에서 오류 메시지 확인 및 offline 감지
            try:
                while not stderr_queue.empty():
                    error_line = stderr_queue.get_nowait()
                    if error_line:
                        monkey_error_lines.append(error_line)
                        logger.warning(f"Monkey stderr: {error_line}")
                        
                        # device offline 감지
                        if "device offline" in error_line.lower():
                            logger.error(f"⚠️ Device offline 감지 - 반복 {run_num}: {error_line}")
                            
                            # 연결 복구 시도
                            if self._handle_device_offline_during_test(run_num):
                                logger.info(f"✅ 연결 복구 성공 - 반복 {run_num} 계속 진행")
                                # 복구 성공 시 타임아웃 리셋
                                last_event_time = current_time
                            else:
                                logger.error(f"❌ 연결 복구 실패 - 반복 {run_num} 중단")
                                try:
                                    monkey_run_process.terminate()
                                    monkey_run_process.wait(timeout=5)
                                except:
                                    monkey_run_process.kill()
                                break
            except queue.Empty:
                pass
            
            # 시간 기반 및 이벤트 기반 진행률 계산
            time_based_progress = min(100, int((elapsed_time / expected_total_time) * 100)) if expected_total_time > 0 else 0
            event_based_progress = min(100, int((significant_events / events) * 100)) if events > 0 else 0
            
            # Deep Test 실시간 조절 (5분마다 미세 조정)
            if is_deep_test and elapsed_time > 300 and int(elapsed_time) % 300 == 0:  # 5분마다
                current_throttle = 150  # 기본값
                optimal_throttle = self._get_dynamic_throttle(current_throttle, run_num, elapsed_time)
                if optimal_throttle != current_throttle:
                    logger.info(f"⚡ 실시간 throttle 권장: {optimal_throttle}ms (다음 회차 적용 예정)")
            
            # 더 정확한 진행률 선택 (시간과 이벤트 중 더 안정적인 값)
            combined_progress = max(time_based_progress, event_based_progress)
            
            # 진행 상황 업데이트 (1초마다, 변화가 있을 때만)
            if current_time - last_progress_update >= 1.0 and combined_progress > last_reported_progress:
                if self.progress_callback:
                    try:
                        progress_message = f"반복 {run_num}: {combined_progress}% 완료 (이벤트 {significant_events}/{events}, 시간 {elapsed_time:.1f}s)"
                        self.progress_callback(progress_message, combined_progress, 100)
                    except:
                        pass
                
                last_progress_update = current_time
                last_reported_progress = combined_progress
                
                # 디버그 정보
                logger.debug(f"진행률 업데이트 - 반복 {run_num}: 시간 {time_based_progress}%, 이벤트 {event_based_progress}%, 종합 {combined_progress}%")
            
            # 무활동 상태 체크 (마지막 이벤트로부터 너무 오래 지났는지)
            if significant_events > 0 and (current_time - last_event_time) > no_activity_timeout:
                logger.warning(f"반복 {run_num}: {no_activity_timeout}초 동안 이벤트 활동 없음. 프로세스 상태 확인 중...")
                
                # 프로세스가 여전히 실행 중인지 확인
                if monkey_run_process.poll() is None:
                    logger.warning(f"반복 {run_num}: 프로세스는 실행 중이나 이벤트 활동 없음. 계속 대기...")
                    last_event_time = current_time  # 타임아웃 리셋
            
            # Deep Test 다단계 시간 제어 (더 정교한 방식)
            if is_deep_test:
                # 단계별 시간 체크
                progress_ratio = elapsed_time / target_duration
                
                # 1단계: 16분 (90%) 경고
                if progress_ratio >= 0.9 and not hasattr(self, '_deep_test_90_warned'):
                    self._deep_test_90_warned = True
                    logger.info(f"⏰ Deep Test 90% 도달: {elapsed_time/60:.1f}분 경과, 남은 시간 {(target_duration-elapsed_time)/60:.1f}분")
                
                # 2단계: 17분 30초 (97%) 준비 경고
                if progress_ratio >= 0.97 and not hasattr(self, '_deep_test_97_warned'):
                    self._deep_test_97_warned = True
                    logger.info(f"⚠️ Deep Test 종료 준비: {elapsed_time/60:.1f}분 경과, 30초 후 종료")
                
                # 3단계: 18분 정확 종료
                if elapsed_time >= target_duration:
                    completion_percentage = (significant_events / events) * 100 if events > 0 else 0
                    
                    logger.info(f"🎯 Deep Test 목표 시간({target_duration/60:.1f}분) 달성")
                    logger.info(f"📊 완료 상태: {significant_events:,}/{events:,} 이벤트 ({completion_percentage:.1f}%)")
                    
                    # 부드러운 종료 처리
                    try:
                        # 1차: 정상 종료 신호 (SIGTERM)
                        logger.info("🔄 정상 종료 신호 전송...")
                        monkey_run_process.terminate()
                        
                        # 5초 대기
                        try:
                            monkey_run_process.wait(timeout=5)
                            logger.info(f"✅ Deep Test 정상 종료: {elapsed_time:.1f}초 실행됨")
                        except subprocess.TimeoutExpired:
                            # 2차: 강제 종료 (SIGKILL)
                            logger.warning(f"⚠️ 정상 종료 지연, 강제 종료 수행")
                            monkey_run_process.kill()
                            monkey_run_process.wait(timeout=3)
                            logger.info(f"✅ Deep Test 강제 종료: {elapsed_time:.1f}초 실행됨")
                            
                    except Exception as e:
                        logger.error(f"❌ Deep Test 종료 중 오류: {e}")
                        try:
                            monkey_run_process.kill()
                        except:
                            pass
                    
                    # 종료 후 정리
                    break
            
            # 최대 대기 시간 체크 (기존 로직)
            if elapsed_time > max_wait_time:
                logger.error(f"반복 {run_num}: 최대 대기 시간({max_wait_time}초) 초과. 프로세스 강제 종료.")
                try:
                    monkey_run_process.terminate()
                    monkey_run_process.wait(timeout=5)
                except:
                    monkey_run_process.kill()
                break
            
            time.sleep(0.1)
        
        # 프로세스가 종료된 후 남은 출력도 읽기
        try:
            remaining_stdout = monkey_run_process.stdout.read()
            if remaining_stdout:
                logger.info(f"Monkey 최종 stdout: {remaining_stdout[:200]}...")
                monkey_output_lines.extend(remaining_stdout.strip().split('\n'))
        except:
            pass
        
        try:
            remaining_stderr = monkey_run_process.stderr.read()
            if remaining_stderr:
                logger.warning(f"Monkey 최종 stderr: {remaining_stderr[:200]}...")
                monkey_error_lines.extend(remaining_stderr.strip().split('\n'))
        except:
            pass
        
        # 프로세스 종료 코드 확인
        return_code = monkey_run_process.returncode
        logger.info(f"Monkey 프로세스 종료 코드: {return_code}")
        
        # 최종 결과 로깅 및 튜닝 분석
        final_elapsed = time.time() - start_time
        accuracy = (expected_total_time/final_elapsed)*100 if final_elapsed > 0 else 0
        target_accuracy = accuracy  # 기본값
        
        # Deep Test 정확도 분석
        if is_deep_test:
            target_accuracy = (target_duration/final_elapsed)*100 if final_elapsed > 0 else 0
            deviation = abs(final_elapsed - target_duration)
            precision_score = self._calculate_precision_score(run_num, final_elapsed)
            
            logger.info(f"🎯 Deep Test 회차 {run_num} 분석:")
            logger.info(f"  목표 시간: {target_duration/60:.1f}분 ({target_duration}초)")
            logger.info(f"  실제 시간: {final_elapsed/60:.1f}분 ({final_elapsed:.1f}초)")
            logger.info(f"  시간 정확도: {target_accuracy:.1f}%")
            logger.info(f"  편차: {deviation:.1f}초 ({deviation/60:.1f}분)")
            logger.info(f"  정확도 점수: {precision_score:.1f}/100점")
            
            # 정확도 등급 표시
            if precision_score >= 95:
                grade = "🏆 최우수 (A+)"
            elif precision_score >= 85:
                grade = "🥇 우수 (A)"
            elif precision_score >= 70:
                grade = "🥈 양호 (B)"
            elif precision_score >= 50:
                grade = "🥉 보통 (C)"
            else:
                grade = "❌ 미흡 (D)"
            
            logger.info(f"  품질 등급: {grade}")
            
            # 튜닝 권장사항 (더 구체적)
            if deviation > 60:  # 1분 이상 편차
                if final_elapsed < target_duration:
                    if precision_score < 70:
                        logger.warning(f"⚠️ 조기 종료 심각: 이벤트 수 {int(events * 1.2):,}개로 증가 검토")
                    else:
                        logger.warning(f"⚠️ 조기 종료 감지: throttle 증가 또는 이벤트 수 증가 검토")
                else:
                    if precision_score < 70:
                        logger.warning(f"⚠️ 초과 실행 심각: throttle 120ms로 감소 검토")
                    else:
                        logger.warning(f"⚠️ 초과 실행 감지: throttle 감소 또는 시간 제어 강화 검토")
            elif deviation > 30:  # 30초 이상 편차
                logger.info(f"📊 미세 조절 권장: 다음 회차에서 자동 적응형 조절 적용")
            else:
                logger.info(f"✅ 우수한 시간 정확도: 현재 설정 유지 권장")
                
        logger.info(f"반복 {run_num} 완료:")
        logger.info(f"  예상 시간: {expected_total_time:.1f}초")
        logger.info(f"  실제 시간: {final_elapsed:.1f}초")
        logger.info(f"  시간 정확도: {accuracy:.1f}%")
        logger.info(f"  이벤트 진행: {significant_events}/{events}")
        logger.info(f"  총 출력 라인: {len(monkey_output_lines)}")
        
        # 성능 튜닝 데이터 수집
        preset_data = self.test_context.get_test_config()
        is_smoke_test = preset_data.get('preset_name') == 'Smoke Test'
        is_quick_test = preset_data.get('preset_name') == 'Quick Test'
        is_extreme_test = preset_data.get('preset_name') == 'Extreme Test'
        
        performance_data = {
            'run_number': run_num,
            'is_smoke_test': is_smoke_test,
            'is_quick_test': is_quick_test,
            'is_deep_test': is_deep_test,
            'is_extreme_test': is_extreme_test,
            'target_duration': target_duration if (is_smoke_test or is_quick_test or is_deep_test or is_extreme_test) else expected_total_time,
            'actual_duration': final_elapsed,
            'accuracy_percent': target_accuracy if (is_smoke_test or is_quick_test or is_deep_test or is_extreme_test) else accuracy,
            'events_completed': significant_events,
            'events_target': events,
            'throttle_used': 250 if is_smoke_test else (220 if is_quick_test else (150 if is_deep_test else (180 if is_extreme_test else throttle))),
            'return_code': return_code
        }
        
        # 적응형 학습 데이터 저장
        preset_data = self.test_context.get_test_config()
        is_smoke_test = preset_data.get('preset_name') == 'Smoke Test'
        is_quick_test = preset_data.get('preset_name') == 'Quick Test'
        is_standard_test = preset_data.get('preset_name') == 'Standard Test'
        
        if is_smoke_test:
            self._save_smoke_test_performance_data(run_num, final_elapsed, significant_events, events)
        elif is_quick_test:
            self._save_quick_test_performance_data(run_num, final_elapsed, significant_events, events)
        elif is_standard_test:
            self._save_standard_test_performance_data(run_num, final_elapsed, significant_events, events)
        elif is_deep_test:
            self._save_deep_test_performance_data(run_num, final_elapsed, significant_events, events)
        elif is_extreme_test:
            self._save_extreme_test_performance(run_num, final_elapsed, significant_events, events)
        
        # 튜닝 분석 로그 (JSON 형태로 추후 분석 가능)
        logger.info(f"📊 성능 데이터: {performance_data}")
        
        # Deep Test 자동 보정 기능 (현재 비활성화 - 정밀 계산 사용)
        # try:
        #     self.apply_time_correction(run_num, final_elapsed)
        # except Exception as e:
        #     logger.error(f"시간 자동 보정 중 오류: {e}")
        
        # 실제 시간이 예상 시간보다 현저히 짧으면 경고 (더 상세한 진단)
        if final_elapsed < expected_total_time * 0.1:  # 예상 시간의 10% 미만이면
            logger.error(f"⚠️ 몽키 테스트가 예상보다 너무 빨리 종료됨!")
            logger.error(f"⚠️ 예상: {expected_total_time:.1f}초, 실제: {final_elapsed:.1f}초")
            logger.error(f"⚠️ 감지된 이벤트: {significant_events}/{events}")
            logger.error(f"⚠️ 프로세스 종료 코드: {return_code}")
            
            if monkey_error_lines:
                logger.error(f"⚠️ 오류 출력: {monkey_error_lines[:3]}")
            if monkey_output_lines:
                logger.error(f"⚠️ 마지막 출력: {monkey_output_lines[-3:]}")
                
            logger.error(f"⚠️ 명령어 재검토 필요: {monkey_run_process.args if hasattr(monkey_run_process, 'args') else '명령어 정보 없음'}")
        
        return final_elapsed, significant_events

    def _save_smoke_test_performance_data(self, run_num: int, actual_duration: float, completed_events: int, target_events: int):
        """Smoke Test 성능 데이터 저장 (적응형 조절용)"""
        try:
            if not hasattr(self, 'smoke_test_history'):
                self.smoke_test_history = []
            
            performance_record = {
                'run': run_num,
                'duration': actual_duration,
                'target_duration': 7 * 60,  # 420초 (7분)
                'completed_events': completed_events,
                'target_events': target_events,
                'event_rate': completed_events / actual_duration if actual_duration > 0 else 0,
                'accuracy': (7 * 60) / actual_duration if actual_duration > 0 else 0
            }
            
            self.smoke_test_history.append(performance_record)
            logger.info(f"📈 Smoke Test 성능 기록 저장: 회차 {run_num}, 정확도 {performance_record['accuracy']*100:.1f}%")
            
            # 적응형 튜너에도 기록
            if hasattr(self, 'adaptive_tuner') and self.adaptive_tuner:
                self.adaptive_tuner.record_test_result(
                    "Smoke Test", 
                    target_events,
                    250,  # Smoke Test throttle
                    actual_duration / 60,  # 분 단위
                    getattr(self, 'current_package', 'unknown')
                )
            
        except Exception as e:
            logger.error(f"Smoke Test 성능 데이터 저장 실패: {e}")

    def _save_quick_test_performance_data(self, run_num: int, actual_duration: float, completed_events: int, target_events: int):
        """Quick Test 성능 데이터 저장 (적응형 조절용)"""
        try:
            if not hasattr(self, 'quick_test_history'):
                self.quick_test_history = []
            
            performance_record = {
                'run': run_num,
                'duration': actual_duration,
                'target_duration': 10 * 60,  # 600초 (10분)
                'completed_events': completed_events,
                'target_events': target_events,
                'event_rate': completed_events / actual_duration if actual_duration > 0 else 0,
                'accuracy': (10 * 60) / actual_duration if actual_duration > 0 else 0
            }
            
            self.quick_test_history.append(performance_record)
            logger.info(f"📈 Quick Test 성능 기록 저장: 회차 {run_num}, 정확도 {performance_record['accuracy']*100:.1f}%")
            
            # 적응형 튜너에도 기록
            if hasattr(self, 'adaptive_tuner') and self.adaptive_tuner:
                self.adaptive_tuner.record_test_result(
                    "Quick Test", 
                    target_events,
                    220,  # Quick Test throttle
                    actual_duration / 60,  # 분 단위
                    getattr(self, 'current_package', 'unknown')
                )
            
        except Exception as e:
            logger.error(f"Quick Test 성능 데이터 저장 실패: {e}")

    def _save_standard_test_performance_data(self, run_num: int, actual_duration: float, completed_events: int, target_events: int):
        """Standard Test 성능 데이터 저장 (적응형 조절용)"""
        try:
            if not hasattr(self, 'standard_test_history'):
                self.standard_test_history = []
            
            performance_record = {
                'run': run_num,
                'duration': actual_duration,
                'target_duration': 15 * 60,  # 900초 (15분)
                'completed_events': completed_events,
                'target_events': target_events,
                'event_rate': completed_events / actual_duration if actual_duration > 0 else 0,
                'accuracy': (15 * 60) / actual_duration if actual_duration > 0 else 0
            }
            
            self.standard_test_history.append(performance_record)
            
            logger.info(f"📈 Standard Test 성능 기록 저장: 회차 {run_num}, 정확도 {performance_record['accuracy']*100:.1f}%")
            
            # 적응형 튜너에도 기록
            if hasattr(self, 'adaptive_tuner') and self.adaptive_tuner:
                self.adaptive_tuner.record_test_result(
                    "Standard Test", 
                    target_events,
                    200,  # Standard Test throttle
                    actual_duration / 60,  # 분 단위
                    getattr(self, 'current_package', 'unknown')
                )
            
        except Exception as e:
            logger.error(f"Standard Test 성능 데이터 저장 실패: {e}")

    def _enhanced_standard_test_monitoring(self, package_name: str, run_num: int) -> dict:
        """Standard Test용 강화된 ANR/타임아웃 모니터링"""
        monitoring_result = {
            'anr_detected': False,
            'timeout_detected': False,
            'response_times': [],
            'unresponsive_periods': []
        }
        
        try:
            # 앱 응답성 주기적 체크 (Standard Test 전용)
            check_interval = 5  # 5초마다 체크
            max_checks = (15 * 60) // check_interval  # 15분 동안
            
            unresponsive_start = None
            consecutive_timeouts = 0
            
            for check_count in range(max_checks):
                if not self.test_context.test_running:
                    break
                
                # 앱 응답성 체크
                start_time = time.time()
                response_result = self.adb_client.run_command(
                    f"shell dumpsys activity activities | grep -E '{package_name}|Resumed'"
                )
                response_time = time.time() - start_time
                
                monitoring_result['response_times'].append(response_time)
                
                # 타임아웃 감지 (Standard Test 임계값: 15초)
                if response_time > self.standard_test_response_timeout:
                    consecutive_timeouts += 1
                    if unresponsive_start is None:
                        unresponsive_start = time.time()
                    
                    logger.warning(f"⚠️ Standard Test 회차 {run_num}: 앱 응답 지연 {response_time:.1f}초")
                    
                    # 연속 타임아웃 감지
                    if consecutive_timeouts >= 2:
                        monitoring_result['timeout_detected'] = True
                        logger.error(f"🚨 Standard Test 회차 {run_num}: 연속 타임아웃 감지 (앱 무응답 상태)")
                        
                else:
                    if unresponsive_start:
                        unresponsive_duration = time.time() - unresponsive_start
                        monitoring_result['unresponsive_periods'].append(unresponsive_duration)
                        unresponsive_start = None
                    consecutive_timeouts = 0
                
                time.sleep(check_interval)
            
            # ANR 패턴 분석
            if len(monitoring_result['response_times']) > 0:
                avg_response = sum(monitoring_result['response_times']) / len(monitoring_result['response_times'])
                max_response = max(monitoring_result['response_times'])
                
                # ANR 패턴 감지 (평균 응답시간이 10초 이상이거나 최대 응답시간이 30초 이상)
                if avg_response > self.standard_test_anr_timeout or max_response > 30:
                    monitoring_result['anr_detected'] = True
                    logger.error(f"🚨 Standard Test 회차 {run_num}: ANR 패턴 감지 (평균: {avg_response:.1f}초, 최대: {max_response:.1f}초)")
            
        except Exception as e:
            logger.error(f"Standard Test 강화 모니터링 오류: {e}")
        
        return monitoring_result

    def _save_deep_test_performance_data(self, run_num: int, actual_duration: float, completed_events: int, target_events: int):
        """Deep Test 성능 데이터 저장 (적응형 조절용)"""
        try:
            if not hasattr(self, 'deep_test_history'):
                self.deep_test_history = []
            
            performance_record = {
                'run': run_num,
                'duration': actual_duration,
                'target_duration': 18 * 60,  # 1080초
                'completed_events': completed_events,
                'target_events': target_events,
                'event_rate': completed_events / actual_duration if actual_duration > 0 else 0,
                'accuracy': (18 * 60) / actual_duration if actual_duration > 0 else 0
            }
            
            self.deep_test_history.append(performance_record)
            logger.info(f"📈 Deep Test 성능 기록 저장: 회차 {run_num}, 정확도 {performance_record['accuracy']*100:.1f}%")
            
        except Exception as e:
            logger.error(f"Deep Test 성능 데이터 저장 실패: {e}")

    def _save_extreme_test_performance(self, run_num: int, actual_duration: float, 
                                     completed_events: int, target_events: int):
        """Extreme Test 성능 데이터 저장"""
        try:
            if not hasattr(self, 'extreme_test_history'):
                self.extreme_test_history = []
            
            performance_record = {
                'run': run_num,
                'duration': actual_duration,
                'target_duration': 32 * 60,  # 1920초
                'completed_events': completed_events,
                'target_events': target_events,
                'event_rate': completed_events / actual_duration if actual_duration > 0 else 0,
                'accuracy': (32 * 60) / actual_duration if actual_duration > 0 else 0
            }
            
            self.extreme_test_history.append(performance_record)
            logger.info(f"📈 Extreme Test 성능 기록 저장: 회차 {run_num}, 정확도 {performance_record['accuracy']*100:.1f}%")
            
            # 적응형 튜너에도 기록
            if hasattr(self, 'adaptive_tuner') and self.adaptive_tuner:
                self.adaptive_tuner.record_test_result(
                    "Extreme Test", 
                    target_events,
                    180,  # Extreme Test throttle
                    actual_duration / 60,  # 분 단위
                    getattr(self, 'current_package', 'unknown')
                )
            
        except Exception as e:
            logger.error(f"Extreme Test 성능 데이터 저장 실패: {e}")

    def _calculate_adaptive_events(self, base_events: int, current_run: int, preset_name: str = "Deep Test") -> int:
        """적응형 이벤트 수 계산 (Gemini AI 지능형 분석 + 이전 회차 성능 기반) - Smoke Test/Quick Test/Standard Test/Deep Test/Extreme Test 지원"""
        try:
            # 최소 이벤트 수 상수 정의
            MIN_SMOKE_TEST_EVENTS = 3500
            MIN_QUICK_TEST_EVENTS = 7750
            MIN_STANDARD_TEST_EVENTS = 12000
            MIN_DEEP_TEST_EVENTS = 22000
            MIN_EXTREME_TEST_EVENTS = 32500
            
            # 프리셋별 목표 시간 설정
            is_smoke_test = preset_name == "Smoke Test"
            is_quick_test = preset_name == "Quick Test"
            is_standard_test = preset_name == "Standard Test"
            is_extreme_test = preset_name == "Extreme Test"
            is_deep_test = preset_name == "Deep Test"
            
            if is_smoke_test:
                target_duration = 7 * 60  # Smoke Test: 7분
                target_minutes = 7.0
            elif is_quick_test:
                target_duration = 10 * 60  # Quick Test: 10분
                target_minutes = 10.0
            elif is_standard_test:
                target_duration = 15 * 60  # Standard Test: 15분 (회차당)
                target_minutes = 15.0
            elif is_extreme_test:
                target_duration = 32 * 60  # Extreme Test: 32분
                target_minutes = 32.0
            else:  # Deep Test
                target_duration = 18 * 60  # Deep Test: 18분
                target_minutes = 18.0
            
            # 히스토리 속성명 결정
            if is_smoke_test:
                history_attr = 'smoke_test_history'
            elif is_quick_test:
                history_attr = 'quick_test_history'
            elif is_standard_test:
                history_attr = 'standard_test_history'
            elif is_extreme_test:
                history_attr = 'extreme_test_history'
            else:
                history_attr = 'deep_test_history'
            
            if not hasattr(self, history_attr) or not getattr(self, history_attr):
                logger.info(f"🔄 적응형 조절: {preset_name} 성능 이력 없음")
                
                # 첫 번째 실행에서도 Gemini AI 분석 시도
                gemini_events = None
                if self.adaptive_tuner:
                    try:
                        logger.info("🤖 Gemini AI 지능형 분석 시작...")
                        
                        # 적응형 튜너에서 최적화된 파라미터 추천받기
                        optimized_throttle = 250 if is_smoke_test else (220 if is_quick_test else (150 if is_deep_test else 180))
                        optimized_events, optimized_throttle, reasoning = self.adaptive_tuner.get_optimized_parameters(
                            preset_name, base_events, optimized_throttle
                        )
                        
                        # Smoke Test, Quick Test, Deep Test, Extreme Test의 최소 이벤트 수 보장
                        if is_smoke_test:  # Smoke Test인 경우
                            if optimized_events < MIN_SMOKE_TEST_EVENTS:
                                logger.info(f"🛡️ Smoke Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_SMOKE_TEST_EVENTS:,}개")
                                optimized_events = MIN_SMOKE_TEST_EVENTS
                                reasoning = f"{reasoning} (Smoke Test 최소 3.5k 이벤트 보장으로 보정됨)"
                        elif is_quick_test:  # Quick Test인 경우
                            if optimized_events < MIN_QUICK_TEST_EVENTS:
                                logger.info(f"🛡️ Quick Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_QUICK_TEST_EVENTS:,}개")
                                optimized_events = MIN_QUICK_TEST_EVENTS
                                reasoning = f"{reasoning} (Quick Test 최소 6.5k 이벤트 보장으로 보정됨)"
                        elif is_deep_test:  # Deep Test인 경우
                            if optimized_events < MIN_DEEP_TEST_EVENTS:
                                logger.info(f"🛡️ Deep Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_DEEP_TEST_EVENTS:,}개")
                                optimized_events = MIN_DEEP_TEST_EVENTS
                                reasoning = f"{reasoning} (Deep Test 최소 22k 이벤트 보장으로 보정됨)"
                        elif is_extreme_test:  # Extreme Test인 경우
                            if optimized_events < MIN_EXTREME_TEST_EVENTS:
                                logger.info(f"🛡️ Extreme Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_EXTREME_TEST_EVENTS:,}개")
                                optimized_events = MIN_EXTREME_TEST_EVENTS
                                reasoning = f"{reasoning} (Extreme Test 최소 32.5k 이벤트 보장으로 보정됨)"
                        
                        if optimized_events != base_events:
                            gemini_events = optimized_events
                            logger.info(f"🧠 Gemini AI 추천: {gemini_events:,}개 이벤트")
                            logger.info(f"   AI 분석 근거: {reasoning}")
                        else:
                            logger.info(f"🤖 Gemini AI: 현재 설정 최적 상태 - {reasoning}")
                            
                    except Exception as e:
                        logger.warning(f"Gemini AI 분석 실패, 기본 알고리즘 사용: {e}")
                
                # 최종 결과에도 Smoke Test, Quick Test, Standard Test, Deep Test, Extreme Test 최소값 적용
                final_events = gemini_events if gemini_events else base_events
                
                # Smoke Test, Quick Test, Standard Test, Deep Test, Extreme Test 절대 최소값 보장
                if is_smoke_test:  # Smoke Test인 경우
                    if final_events < MIN_SMOKE_TEST_EVENTS:
                        logger.info(f"🛡️ Smoke Test 최소 이벤트 수 최종 보정: {final_events:,}개 → {MIN_SMOKE_TEST_EVENTS:,}개")
                        final_events = MIN_SMOKE_TEST_EVENTS
                elif is_quick_test:  # Quick Test인 경우
                    if final_events < MIN_QUICK_TEST_EVENTS:
                        logger.info(f"🛡️ Quick Test 최소 이벤트 수 최종 보정: {final_events:,}개 → {MIN_QUICK_TEST_EVENTS:,}개")
                        final_events = MIN_QUICK_TEST_EVENTS
                elif is_standard_test:  # Standard Test인 경우
                    if final_events < MIN_STANDARD_TEST_EVENTS:
                        logger.info(f"🛡️ Standard Test 최소 이벤트 수 최종 보정: {final_events:,}개 → {MIN_STANDARD_TEST_EVENTS:,}개")
                        final_events = MIN_STANDARD_TEST_EVENTS
                elif is_deep_test:  # Deep Test인 경우
                    if final_events < MIN_DEEP_TEST_EVENTS:
                        logger.info(f"🛡️ Deep Test 최소 이벤트 수 최종 보정: {final_events:,}개 → {MIN_DEEP_TEST_EVENTS:,}개")
                        final_events = MIN_DEEP_TEST_EVENTS
                elif is_extreme_test:  # Extreme Test인 경우
                    if final_events < MIN_EXTREME_TEST_EVENTS:
                        logger.info(f"🛡️ Extreme Test 최소 이벤트 수 최종 보정: {final_events:,}개 → {MIN_EXTREME_TEST_EVENTS:,}개")
                        final_events = MIN_EXTREME_TEST_EVENTS
                
                return final_events
            
            # 최근 성능 데이터 분석
            history = getattr(self, history_attr)
            recent_history = history[-min(3, len(history)):]  # 최근 3회차
            
            # 평균 이벤트 처리 속도 계산
            avg_event_rate = sum(record['event_rate'] for record in recent_history) / len(recent_history)
            avg_accuracy = sum(record['accuracy'] for record in recent_history) / len(recent_history)
            
            logger.info(f"📊 {preset_name} 성능 분석 (최근 {len(recent_history)}회차):")
            logger.info(f"  평균 이벤트 처리 속도: {avg_event_rate:.1f} events/sec")
            logger.info(f"  평균 시간 정확도: {avg_accuracy*100:.1f}%")
            
            # Gemini AI 지능형 분석 시도 (최소 1회차부터)
            gemini_events = None
            if self.adaptive_tuner and len(recent_history) >= 1:
                try:
                    logger.info("🤖 Gemini AI 지능형 분석 시작...")
                    
                    # 적응형 튜너에서 최적화된 파라미터 추천받기
                    optimized_throttle = 250 if is_smoke_test else (220 if is_quick_test else (200 if is_standard_test else (150 if is_deep_test else 180)))
                    optimized_events, optimized_throttle, reasoning = self.adaptive_tuner.get_optimized_parameters(
                        preset_name, base_events, optimized_throttle
                    )
                    
                    # Smoke Test, Quick Test, Standard Test, Deep Test, Extreme Test 최소 이벤트 수 보장
                    if is_smoke_test:  # Smoke Test인 경우
                        if optimized_events < MIN_SMOKE_TEST_EVENTS:
                            logger.info(f"🛡️ Smoke Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_SMOKE_TEST_EVENTS:,}개")
                            optimized_events = MIN_SMOKE_TEST_EVENTS
                            reasoning = f"{reasoning} (Smoke Test 최소 3.5k 이벤트 보장으로 보정됨)"
                    elif is_quick_test:  # Quick Test인 경우
                        if optimized_events < MIN_QUICK_TEST_EVENTS:
                            logger.info(f"🛡️ Quick Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_QUICK_TEST_EVENTS:,}개")
                            optimized_events = MIN_QUICK_TEST_EVENTS
                            reasoning = f"{reasoning} (Quick Test 최소 6.5k 이벤트 보장으로 보정됨)"
                    elif is_standard_test:  # Standard Test인 경우
                        if optimized_events < MIN_STANDARD_TEST_EVENTS:
                            logger.info(f"🛡️ Standard Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_STANDARD_TEST_EVENTS:,}개")
                            optimized_events = MIN_STANDARD_TEST_EVENTS
                            reasoning = f"{reasoning} (Standard Test 최소 12k 이벤트 보장으로 보정됨)"
                    elif is_deep_test:  # Deep Test인 경우
                        if optimized_events < MIN_DEEP_TEST_EVENTS:
                            logger.info(f"🛡️ Deep Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_DEEP_TEST_EVENTS:,}개")
                            optimized_events = MIN_DEEP_TEST_EVENTS
                            reasoning = f"{reasoning} (Deep Test 최소 22k 이벤트 보장으로 보정됨)"
                    elif is_extreme_test:  # Extreme Test인 경우
                        if optimized_events < MIN_EXTREME_TEST_EVENTS:
                            logger.info(f"🛡️ Extreme Test 최소 이벤트 수 보정: {optimized_events:,}개 → {MIN_EXTREME_TEST_EVENTS:,}개")
                            optimized_events = MIN_EXTREME_TEST_EVENTS
                            reasoning = f"{reasoning} (Extreme Test 최소 32.5k 이벤트 보장으로 보정됨)"
                    
                    if optimized_events != base_events:
                        gemini_events = optimized_events
                        logger.info(f"🧠 Gemini AI 추천: {gemini_events:,}개 이벤트")
                        logger.info(f"   AI 분석 근거: {reasoning}")
                    else:
                        logger.info(f"🤖 Gemini AI: 현재 설정 최적 상태 - {reasoning}")
                        
                except Exception as e:
                    logger.warning(f"Gemini AI 분석 실패, 기본 알고리즘 사용: {e}")
            
            # AI 추천이 있으면 우선 사용, 없으면 기본 알고리즘
            if gemini_events:
                optimal_events = gemini_events
                source = "Gemini AI"
            else:
                # 기본 알고리즘: 목표 시간에 맞는 이벤트 수 계산
                optimal_events = int(target_duration * avg_event_rate)
                source = "기본 알고리즘"
            
            # 프리셋별 안전 범위 설정
            if is_smoke_test:
                safety_margin = 0.20  # Smoke Test: ±20% 제한 (더 유연)
                logger.info("🎯 Smoke Test 모드: 이벤트 수 유연 제한 (±20%)")
            elif is_quick_test:
                safety_margin = 0.15  # Quick Test: ±15% 제한 (균형)
                logger.info("🎯 Quick Test 모드: 이벤트 수 균형 제한 (±15%)")
            elif is_standard_test:
                safety_margin = 0.12  # Standard Test: ±12% 제한 (안정성 중시)
                logger.info("🎯 Standard Test 모드: 이벤트 수 안정 제한 (±12%)")
            elif is_extreme_test:
                safety_margin = 0.15  # Extreme Test: ±15% 제한
                logger.info("🎯 Extreme Test 모드: 이벤트 수 제한 (±15%)")
            else:  # Deep Test
                safety_margin = 0.10  # Deep Test: ±10% 제한 
                logger.info("🎯 Deep Test 모드: 이벤트 수 엄격 제한 (±10%)")
                
            min_events = int(base_events * (1 - safety_margin))
            max_events = int(base_events * (1 + safety_margin))
            
            # Smoke Test, Quick Test, Standard Test, Deep Test, Extreme Test 절대 최소값 보장
            if is_smoke_test:  # Smoke Test인 경우
                min_events = max(min_events, MIN_SMOKE_TEST_EVENTS)
                logger.info(f"🛡️ Smoke Test 최소 이벤트 수 보장: {MIN_SMOKE_TEST_EVENTS:,}개 이상")
            elif is_quick_test:  # Quick Test인 경우
                min_events = max(min_events, MIN_QUICK_TEST_EVENTS)
                logger.info(f"🛡️ Quick Test 최소 이벤트 수 보장: {MIN_QUICK_TEST_EVENTS:,}개 이상")
            elif is_standard_test:  # Standard Test인 경우
                min_events = max(min_events, MIN_STANDARD_TEST_EVENTS)
                logger.info(f"🛡️ Standard Test 최소 이벤트 수 보장: {MIN_STANDARD_TEST_EVENTS:,}개 이상")
            elif is_deep_test:  # Deep Test인 경우
                min_events = max(min_events, MIN_DEEP_TEST_EVENTS)
                logger.info(f"🛡️ Deep Test 최소 이벤트 수 보장: {MIN_DEEP_TEST_EVENTS:,}개 이상")
            elif is_extreme_test:  # Extreme Test인 경우
                min_events = max(min_events, MIN_EXTREME_TEST_EVENTS)
                logger.info(f"🛡️ Extreme Test 최소 이벤트 수 보장: {MIN_EXTREME_TEST_EVENTS:,}개 이상")
            
            adaptive_events = max(min_events, min(max_events, optimal_events))
            
            # 조절 이유 로깅
            adjustment_reason = ""
            if avg_accuracy < 0.9:  # 90% 미만
                adjustment_reason = f"시간이 길어지는 경향 (평균 {avg_accuracy*100:.1f}%)"
            elif avg_accuracy > 1.1:  # 110% 초과
                adjustment_events = int(adaptive_events * 1.1)  # 10% 증가
                adaptive_events = min(max_events, adaptive_events)
                adjustment_reason = f"시간이 짧아지는 경향 (평균 {avg_accuracy*100:.1f}%)"
            else:
                adjustment_reason = f"양호한 정확도 (평균 {avg_accuracy*100:.1f}%)"
            
            # 정확도 향상을 위한 추가 조정
            expected_duration = adaptive_events / avg_event_rate / 60  # 예상 시간(분)
            
            if abs(expected_duration - target_minutes) > 0.5:  # 0.5분 이상 차이
                # throttle 효율성을 역산하여 정확한 값 계산
                actual_efficiency = avg_event_rate / (base_events / target_duration)  # 실제 효율성
                logger.info(f"📐 실제 측정 효율성: {actual_efficiency:.3f}")
                
                # 효율성 기반으로 이벤트 수 재조정
                precise_events = int(target_duration * avg_event_rate)
                if min_events <= precise_events <= max_events:
                    adaptive_events = precise_events
                    logger.info(f"🔧 {preset_name} {target_minutes}분 정확도 보정: {adaptive_events:,}개 이벤트로 재조정")
            
            change_percent = ((adaptive_events - base_events) / base_events) * 100
            
            logger.info(f"🎯 적응형 이벤트 조절 ({source}):")
            logger.info(f"  기본 이벤트: {base_events:,}개")
            logger.info(f"  조절 이벤트: {adaptive_events:,}개 ({change_percent:+.1f}%)")
            logger.info(f"  조절 사유: {adjustment_reason}")
            logger.info(f"  예상 시간: {adaptive_events / avg_event_rate / 60:.1f}분")
            
            return adaptive_events
            
        except Exception as e:
            logger.error(f"{preset_name} 적응형 이벤트 수 계산 실패: {e}")
            return base_events

    def _get_dynamic_throttle(self, base_throttle: int, current_run: int, elapsed_time: float) -> int:
        """실시간 성능 기반 동적 throttle 조절"""
        try:
            if not self.dynamic_throttle_enabled:
                return base_throttle
            
            target_duration = 18 * 60  # 1080초
            
            # 현재 진행률 및 예상 완료 시간 계산
            if elapsed_time > 60:  # 1분 이상 경과 시에만 조절
                progress_ratio = elapsed_time / target_duration
                
                # 예상 완료 시간 (현재 속도 기준)
                estimated_total = elapsed_time / progress_ratio if progress_ratio > 0 else target_duration
                time_deviation = estimated_total - target_duration
                
                logger.debug(f"🔧 동적 throttle 분석:")
                logger.debug(f"  현재 경과: {elapsed_time:.1f}초 ({progress_ratio*100:.1f}%)")
                logger.debug(f"  예상 완료: {estimated_total:.1f}초")
                logger.debug(f"  시간 편차: {time_deviation:.1f}초")
                
                # throttle 조절 계산
                if abs(time_deviation) > 60:  # 1분 이상 편차
                    if time_deviation > 0:  # 예상 시간이 길어짐 → throttle 감소
                        adjustment = min(10, int(time_deviation / 30))  # 최대 10ms 감소
                        adjusted_throttle = max(100, base_throttle - adjustment)
                        reason = f"진행 속도 느림 (예상 +{time_deviation/60:.1f}분)"
                    else:  # 예상 시간이 짧아짐 → throttle 증가
                        adjustment = min(10, int(abs(time_deviation) / 30))  # 최대 10ms 증가
                        adjusted_throttle = min(200, base_throttle + adjustment)
                        reason = f"진행 속도 빠름 (예상 -{abs(time_deviation)/60:.1f}분)"
                    
                    if adjusted_throttle != base_throttle:
                        logger.info(f"🔧 동적 throttle 조절: {base_throttle}ms → {adjusted_throttle}ms ({reason})")
                        return adjusted_throttle
            
            return base_throttle
            
        except Exception as e:
            logger.error(f"동적 throttle 조절 실패: {e}")
            return base_throttle

    def _calculate_precision_score(self, run_num: int, actual_duration: float) -> float:
        """회차별 시간 정확도 점수 계산 (0-100점)"""
        try:
            target_duration = 18 * 60  # 1080초
            deviation = abs(actual_duration - target_duration)
            
            # 정확도 점수 계산 (편차가 작을수록 높은 점수)
            if deviation <= 30:  # 30초 이내 → 95-100점
                score = 100 - (deviation / 30) * 5
            elif deviation <= 60:  # 1분 이내 → 85-95점
                score = 95 - ((deviation - 30) / 30) * 10
            elif deviation <= 120:  # 2분 이내 → 70-85점
                score = 85 - ((deviation - 60) / 60) * 15
            else:  # 2분 초과 → 0-70점
                score = max(0, 70 - ((deviation - 120) / 60) * 10)
            
            logger.info(f"🎯 회차 {run_num} 정확도 점수: {score:.1f}점 (편차: {deviation:.1f}초)")
            return score
            
        except Exception as e:
            logger.error(f"정확도 점수 계산 실패: {e}")
            return 0.0

    def _read_logcat(self, process, run_num, package_name, crash_logs_list, anr_logs_list, all_logcats_list):
        """Logcat 출력을 실시간으로 읽고 crash/ANR을 감지합니다."""
        logger.info(f"Logcat 읽기 시작 - 반복 {run_num}, 패키지 {package_name}")
        logcat_filename = os.path.join(MONKEY_LOG_DIR, 
            f"{package_name.replace('.', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_run_{run_num}_logcat.log")
        
        line_count = 0  # 라인 카운터 추가
        
        # Standard Test용 강화된 크래시/ANR 카운터 초기화
        preset_data = self.test_context.get_test_config()
        is_standard_test = preset_data.get('preset_name') == 'Standard Test'
        self._current_timeout_count = 0
        self._current_anr_count = 0
        
        try:
            with open(logcat_filename, "w", encoding='utf-8') as f_log:
                current_crash_context = []
                current_anr_context = []
                crash_detected = False
                anr_detected = False
                
                while self.logcat_active and self.test_context.test_running:
                    try:
                        line = process.stdout.readline()
                        if not line:
                            break
                        
                        line = line.strip()
                        if not line:
                            continue
                        
                        line_count += 1
                        
                        # 로그 파일에 저장
                        f_log.write(line + "\\n")
                        f_log.flush()
                        
                        # 디버깅: logcat 라인 확인
                        if line_count <= 10:  # 처음 10줄만 로깅
                            logger.info(f"Logcat 라인 {line_count}: '{line.strip()}'")
                        
                        # 크래시 감지 (더 정교한 조건)
                        for keyword in CRASH_KEYWORDS:
                            if keyword.lower() in line.lower() and package_name in line:
                                # Monkey의 stderr 출력이나 명령어 파싱 과정은 제외
                                if ("arg:" in line or "data=" in line or "mNextArg" in line or 
                                    "argwas=" in line or "nextarg=" in line or
                                    line.strip().startswith("arg:") or line.strip().startswith("data=")):
                                    continue
                                
                                # 실제 크래시 로그만 감지 (AndroidRuntime이나 FATAL EXCEPTION 포함)
                                if keyword in ["CRASH"] and not any(real_crash in line for real_crash in 
                                    ["FATAL EXCEPTION", "AndroidRuntime", "Process", "died", "Native crash"]):
                                    continue
                                
                                if not crash_detected:
                                    crash_detected = True
                                    current_crash_context = [line]
                                    logger.warning(f"🚨 실제 크래시 감지 - 반복 {run_num}: {keyword}")
                                    logger.warning(f"🚨 크래시 라인 전체: '{line.strip()}'")
                                    logger.warning(f"🚨 패키지명 확인: '{package_name}' in '{line}'")
                                else:
                                    current_crash_context.append(line)
                                break
                        
                        # ANR 감지 (더 정교한 조건)
                        for keyword in ANR_KEYWORDS:
                            if keyword.lower() in line.lower() and package_name in line:
                                # Monkey의 stderr 출력이나 명령어 파싱 과정은 제외
                                if ("arg:" in line or "data=" in line or "mNextArg" in line or 
                                    "argwas=" in line or "nextarg=" in line or
                                    line.strip().startswith("arg:") or line.strip().startswith("data=")):
                                    continue
                                
                                if not anr_detected:
                                    anr_detected = True
                                    current_anr_context = [line]
                                    
                                    # Standard Test용 강화된 ANR 감지
                                    if is_standard_test:
                                        self._current_anr_count += 1
                                        logger.error(f"🚨 Standard Test ANR 감지 - 반복 {run_num}: {keyword}")
                                        logger.error(f"🚨 ANR 발생 횟수: {self._current_anr_count}회")
                                    else:
                                        logger.warning(f"ANR 감지 - 반복 {run_num}: {keyword}")
                                    
                                    logger.warning(f"ANR 라인 내용: {line[:100]}...")
                                else:
                                    current_anr_context.append(line)
                                break
                        
                        # 모든 프리셋에 공통 타임아웃 패턴 감지
                        timeout_keywords = ['timeout', 'timed out', 'not responding', 'blocked', 'deadlock']
                        for timeout_keyword in timeout_keywords:
                            if timeout_keyword.lower() in line.lower() and package_name in line:
                                self._current_timeout_count += 1
                                preset_name = preset_data.get('preset_name', 'Unknown')
                                logger.error(f"🚨 {preset_name} 타임아웃 패턴 감지 - 반복 {run_num}: {timeout_keyword}")
                                logger.error(f"🚨 타임아웃 발생 횟수: {self._current_timeout_count}회")
                                break
                        
                        # 컨텍스트 수집 계속
                        if crash_detected and len(current_crash_context) < 20:
                            current_crash_context.append(line)
                        elif crash_detected and len(current_crash_context) >= 20:
                            # 크래시 정보 저장
                            self._analyze_and_store_crash(crash_logs_list, run_num, package_name, 
                                                        "CRASH", current_crash_context, logcat_filename)
                            crash_detected = False
                            current_crash_context = []
                        
                        if anr_detected and len(current_anr_context) < 20:
                            current_anr_context.append(line)
                        elif anr_detected and len(current_anr_context) >= 20:
                            # ANR 정보 저장
                            self._analyze_and_store_crash(anr_logs_list, run_num, package_name, 
                                                        "ANR", current_anr_context, logcat_filename)
                            anr_detected = False
                            current_anr_context = []
                            
                    except Exception as e:
                        logger.error(f"Logcat 라인 처리 중 오류: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Logcat 읽기 중 오류 - 반복 {run_num}: {e}")

    def _monitor_performance(self, package_name, run_num, performance_data_list):
        """CPU 및 메모리 사용량을 주기적으로 모니터링합니다. (연결 복구 포함)"""
        logger.info(f"성능 모니터링 시작 - 반복 {run_num}, 패키지 {package_name}")
        monitoring_count = 0
        offline_recovery_attempts = 0
        max_offline_recovery_attempts = 3
        
        while self.monitoring_active and self.test_context.test_running:
            try:
                # 메모리 사용량 확인 - AdbClient의 메서드 사용
                logger.info(f"메모리 정보 조회 시작 - 반복 {run_num}")
                memory_mb = self.adb_client.get_memory_info(package_name)
                
                # device offline 감지 및 처리
                if memory_mb is None:
                    logger.warning(f"메모리 정보 조회 실패 - 반복 {run_num}")
                    # 실패 이유를 더 자세히 조사
                    test_result = self.adb_client.run_command(f"shell dumpsys meminfo {package_name}")
                    
                    if "device offline" in test_result.lower():
                        logger.warning(f"⚠️ 성능 모니터링 중 device offline 감지 - 반복 {run_num}")
                        
                        if offline_recovery_attempts < max_offline_recovery_attempts:
                            offline_recovery_attempts += 1
                            logger.info(f"🔄 성능 모니터링 중 연결 복구 시도 {offline_recovery_attempts}/{max_offline_recovery_attempts}")
                            
                            if self._recover_device_connection():
                                logger.info(f"✅ 성능 모니터링 중 연결 복구 성공 - 반복 {run_num}")
                                offline_recovery_attempts = 0  # 복구 성공 시 카운터 리셋
                                time.sleep(2)  # 복구 후 안정화 대기
                                continue
                            else:
                                logger.error(f"❌ 성능 모니터링 중 연결 복구 실패 - 반복 {run_num}")
                                time.sleep(5)  # 실패 시 더 긴 대기
                                continue
                        else:
                            logger.error(f"❌ 성능 모니터링 중 최대 복구 시도 횟수 초과 - 반복 {run_num}")
                            # 모니터링은 중단하되 테스트는 계속 진행
                            break
                    else:
                        logger.warning(f"메모리 조회 실패 상세: {test_result[:200]}...")
                        memory_mb = 0
                else:
                    logger.info(f"메모리 정보 조회 결과: {memory_mb:.1f}MB - 반복 {run_num}")
                    offline_recovery_attempts = 0  # 정상 조회 시 카운터 리셋
                
                # CPU 사용률 확인 - AdbClient의 메서드 사용  
                logger.info(f"CPU 정보 조회 시작 - 반복 {run_num}")
                cpu_percent = self.adb_client.get_cpu_usage(package_name)
                
                if cpu_percent is None:
                    logger.warning(f"CPU 정보 조회 실패 - 반복 {run_num}")
                    # PID 조회 상태 확인
                    pid = self.adb_client.get_main_process_pid(package_name)
                    logger.warning(f"PID 조회 결과: {pid}")
                    if pid:
                        test_top = self.adb_client.run_command(f"shell top -n 1 -p {pid}")
                        if "device offline" in test_top.lower():
                            logger.warning(f"⚠️ CPU 조회 중 device offline 감지 - 반복 {run_num}")
                        else:
                            logger.warning(f"top 명령어 실행 결과: {test_top[:200]}...")
                    cpu_percent = 0
                else:
                    logger.info(f"CPU 정보 조회 결과: {cpu_percent}% - 반복 {run_num}")
                
                # 성능 데이터 저장 (정확한 시간 정보 포함)
                current_time = datetime.datetime.now()
                
                # 메모리와 CPU 값 반올림 (소수점 1자리)
                memory_rounded = round(memory_mb, 1) if memory_mb and memory_mb > 0 else 0.0
                cpu_rounded = round(cpu_percent, 1) if cpu_percent and cpu_percent > 0 else 0.0
                
                performance_data = {
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "time_detailed": current_time.strftime("%H:%M:%S.%f")[:-3],  # 밀리초 포함
                    "run": run_num,
                    "memory_mb": memory_rounded,
                    "cpu_percent": cpu_rounded
                }
                performance_data_list.append(performance_data)
                logger.info(f"성능 데이터 저장: {performance_data}")
                
                monitoring_count += 1
                if monitoring_count % 3 == 0:  # 3회마다 로그
                    logger.info(f"성능 모니터링 상태 - 반복 {run_num}: 메모리 {memory_rounded}MB, CPU {cpu_rounded}%")
                
                time.sleep(2)  # 2초마다 모니터링
                
            except Exception as e:
                logger.error(f"성능 모니터링 중 오류 - 반복 {run_num}: {e}")
                import traceback
                logger.error(f"성능 모니터링 오류 상세: {traceback.format_exc()}")
                time.sleep(2)
        
        logger.info(f"성능 모니터링 종료 - 반복 {run_num}, 총 {monitoring_count}회 수집")
        
        # 모니터링 완전 중지 보장
        logger.info(f"성능 모니터링 스레드 종료 확인 - 반복 {run_num}")
        time.sleep(0.5)  # 마지막 로그 처리 대기

    def _analyze_and_store_crash(self, crash_logs_list, run_num, package_name, crash_type, crash_context, logcat_filename):
        """크래시 분석 및 저장"""
        crash_logs_list.append({
            "run": run_num,
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "type": crash_type,
            "context": crash_context[:20],  # 처음 20줄만 저장
            "log_file": logcat_filename
        })
        logger.info(f"크래시 저장완료 - 반복 {run_num}, 타입: {crash_type}")

    def _finalize_test_results(self, all_crash_logs, all_anr_logs, current_performance_data):
        """테스트 결과 최종화"""
        try:
            # 1. 모든 백그라운드 모니터링 중지
            logger.info("테스트 완료 - 모든 모니터링 프로세스 중지")
            self.test_context.test_running = False
            self.logcat_active = False
            self.monitoring_active = False
            
            # 2. 백그라운드 모니터링 강제 중지
            try:
                self.stop_background_monitoring()
                logger.info("✅ 백그라운드 모니터링 강제 중지됨")
            except Exception as bg_error:
                logger.error(f"백그라운드 모니터링 중지 실패: {bg_error}")
            
            # 3. 포그라운드 모니터링 중지
            try:
                self.stop_foreground_monitoring()
                logger.info("✅ 포그라운드 모니터링 정상 중지됨")
            except Exception as fg_error:
                logger.error(f"포그라운드 모니터링 중지 실패: {fg_error}")
            
            # 4. 모니터링 완전 종료 대기
            import time
            time.sleep(1)  # 모니터링 스레드 완전 종료 대기
            
            # 5. 요약 업데이트
            total_crashes = len(all_crash_logs)
            total_anrs = len(all_anr_logs)
            
            # 테스트 종료 시간 및 수행 시간 계산
            test_end_datetime = datetime.datetime.now()
            test_start_time = self.test_context.current_test_report["summary"].get("test_start_time")
            
            if test_start_time:
                # 수행 시간 계산 (날짜 넘어가는 경우 포함)
                duration = test_end_datetime - test_start_time
                total_seconds = int(duration.total_seconds())
                
                # 음수인 경우 (시계 문제) 절댓값으로 처리
                if total_seconds < 0:
                    total_seconds = abs(total_seconds)
                
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                
                # 수행 시간 포맷팅
                if hours > 0:
                    duration_str = f"{hours:02d}시간 {minutes:02d}분"
                else:
                    duration_str = f"{minutes:02d}분"
                    
                logger.info(f"⏰ 테스트 수행 시간: {duration_str} (시작: {test_start_time.strftime('%H:%M')}, 종료: {test_end_datetime.strftime('%H:%M')})")
            else:
                duration_str = "00분"
            
            self.test_context.current_test_report["summary"]["result_summary"] = f"{total_crashes}회 Crash, {total_anrs}회 ANR"
            self.test_context.current_test_report["summary"]["test_period"] += f" ~ {test_end_datetime.strftime('%H:%M')}"
            self.test_context.current_test_report["summary"]["execution_time"] = duration_str
            
            # 상세 결과 업데이트
            self.test_context.current_test_report["logs"]["crashes"] = all_crash_logs
            self.test_context.current_test_report["logs"]["anrs"] = all_anr_logs
            self.test_context.current_test_report["logs"]["performance"] = current_performance_data
            
            # test_context에 성능 데이터 저장 (HTML 리포트용)
            self.test_context.current_performance_data = current_performance_data
            logger.info(f"테스트 컨텍스트에 성능 데이터 저장: {len(current_performance_data)}개 항목")
            
            # 성능 데이터 처리 및 차트 생성
            self._process_performance_data_and_generate_charts(current_performance_data)
            
            # 성능 데이터를 엑셀에 저장
            if current_performance_data:
                package_name = self.test_context.app_package_name or "unknown_app"
                excel_file = self._save_performance_data_to_excel(current_performance_data, package_name)
                if excel_file:
                    logger.info(f"성능 데이터 엑셀 저장 완료: {excel_file}")
            
            # 개선 제안 생성
            self._generate_improvement_suggestions(total_crashes, total_anrs, current_performance_data)
            
            # 완료 콜백 호출
            if self.completion_callback:
                try:
                    success_message = f"테스트 완료: {total_crashes}회 크래시, {total_anrs}회 ANR"
                    self.completion_callback(True, success_message)
                except:
                    pass
            
            logger.info(f"테스트 완료 - 크래시: {total_crashes}회, ANR: {total_anrs}회")
            
        except Exception as e:
            logger.error(f"테스트 결과 최종화 오류: {e}")
            if self.completion_callback:
                try:
                    self.completion_callback(False, f"결과 처리 중 오류: {e}")
                except:
                    pass

    def _generate_improvement_suggestions(self, total_crashes, total_anrs, performance_data):
        """개선 제안 생성"""
        suggestions = []
        
        if total_crashes > 0:
            suggestions.append(f"🚨 크래시 {total_crashes}회 발생 → 크래시 로그 분석 및 예외 처리 강화 필요")
        
        if total_anrs > 0:
            suggestions.append(f"⚠️ ANR {total_anrs}회 발생 → 메인 스레드 최적화 및 비동기 처리 필요")
        
        # 성능 분석
        if performance_data:
            mem_values = [p["memory_mb"] for p in performance_data if p.get("memory_mb")]
            cpu_values = [p["cpu_percent"] for p in performance_data if p.get("cpu_percent")]
            
            if mem_values:
                max_memory = max(mem_values)
                avg_memory = sum(mem_values) / len(mem_values)
                if max_memory > 200:
                    suggestions.append(f"💾 메모리 사용량 높음 (최대 {round(max_memory)}MB) → 메모리 누수 확인 필요")
                elif avg_memory > 100:
                    suggestions.append(f"📊 평균 메모리 사용량 주의 ({round(avg_memory)}MB) → 메모리 최적화 권장")
            
            if cpu_values:
                max_cpu = max(cpu_values)
                avg_cpu = sum(cpu_values) / len(cpu_values)
                if max_cpu > 80:
                    suggestions.append(f"🔥 CPU 사용률 높음 (최대 {round(max_cpu)}%) → 연산 최적화 필요")
                elif avg_cpu > 50:
                    suggestions.append(f"⚡ 평균 CPU 사용률 주의 ({round(avg_cpu)}%) → 성능 최적화 권장")
        
        if not suggestions:
            suggestions.append("✅ 특별한 이슈가 발견되지 않았습니다. 안정적인 앱입니다.")
        
        self.test_context.current_test_report["issues"] = suggestions

    def _process_performance_data_and_generate_charts(self, performance_data):
        """성능 데이터 처리 및 시간대별 차트 생성"""
        try:
            if not performance_data:
                logger.warning("성능 데이터가 없어서 차트를 생성할 수 없습니다.")
                return
                
            # PerformanceProcessor를 사용하여 성능 데이터 처리
            processor = PerformanceProcessor()
            
            # 성능 데이터 로드 및 처리
            if processor.load_performance_data(performance_data):
                processor.process_metrics()
                processor.calculate_run_summaries()
                
                # 기본 차트 데이터 생성
                chart_data = processor.generate_chart_data()
                logger.info(f"기본 차트 데이터 생성 완료 - 키: {list(chart_data.keys()) if chart_data else '없음'}")
                
                # 시간대별 차트 생성을 위한 데이터 준비
                try:
                    from src.utils.chart_generator import ChartGenerator
                    chart_generator = ChartGenerator()
                    
                    # 성능 데이터를 시간대별 형식으로 변환
                    time_data = []
                    for data in performance_data:
                        if 'timestamp' in data and data.get('memory_mb') and data.get('cpu_percent'):
                            # 시간 문자열을 datetime 객체로 변환
                            try:
                                if isinstance(data['timestamp'], str):
                                    time_str = data['timestamp']
                                    # 다양한 시간 형식 지원
                                    if len(time_str) >= 19:  # "2025-07-19 00:52:27" 형식
                                        full_datetime = datetime.datetime.strptime(time_str[:19], "%Y-%m-%d %H:%M:%S")
                                    elif len(time_str) >= 8:  # "00:52:27" 형식 (HH:MM:SS)
                                        today = datetime.datetime.now().date()
                                        time_obj = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
                                        full_datetime = datetime.datetime.combine(today, time_obj)
                                    else:
                                        logger.warning(f"지원되지 않는 시간 형식: {time_str}")
                                        continue
                                else:
                                    full_datetime = data['timestamp']
                                
                                time_data.append({
                                    'time': full_datetime,
                                    'memory': data['memory_mb'],
                                    'cpu': data['cpu_percent']
                                })
                            except Exception as time_error:
                                logger.warning(f"시간 변환 오류: {time_error}")
                                continue
                    
                    # 시간대별 차트 생성
                    if time_data:
                        package_name = self.test_context.current_test_report.get('package_name', 'Unknown Package')
                        
                        logger.info(f"시간대별 차트 생성 시작 - {len(time_data)}개 데이터포인트")
                        
                        # 메모리 시간대별 차트
                        memory_timeline_chart = chart_generator._create_memory_timeline_chart_from_time_data(time_data, package_name)
                        if memory_timeline_chart:
                            chart_data['memory'] = memory_timeline_chart
                            logger.info("메모리 시간대별 차트 생성 성공")
                        else:
                            logger.warning("메모리 시간대별 차트 생성 실패")
                        
                        # CPU 시간대별 차트
                        cpu_timeline_chart = chart_generator._create_cpu_timeline_chart_from_time_data(time_data, package_name)
                        if cpu_timeline_chart:
                            chart_data['cpu'] = cpu_timeline_chart
                            logger.info("CPU 시간대별 차트 생성 성공")
                        else:
                            logger.warning("CPU 시간대별 차트 생성 실패")
                        
                        logger.info(f"시간대별 차트 생성 완료 - 총 차트 수: {len([k for k in chart_data.keys() if chart_data[k] is not None])}")
                    else:
                        logger.warning("시간대별 차트 생성을 위한 time_data가 비어있음")
                    
                except Exception as timeline_error:
                    logger.warning(f"시간대별 차트 생성 실패: {timeline_error}")
                
                # 차트 데이터를 테스트 컨텍스트에 저장
                self.test_context.current_test_report["charts"] = chart_data
                
                # 차트 데이터 저장 확인 로그
                logger.info(f"차트 데이터 저장 완료 - 키: {list(chart_data.keys()) if chart_data else '없음'}")
                logger.info(f"테스트 리포트에 charts 키 추가됨")
                
                logger.info(f"성능 데이터 처리 완료 - {len(processor.processed_metrics)}개 메트릭, {len(processor.run_summaries)}개 실행 요약")
            else:
                logger.error("성능 데이터 로드에 실패했습니다.")
            
        except Exception as e:
            logger.error(f"성능 데이터 처리 중 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")

    def _save_performance_data_to_excel(self, performance_data, package_name):
        """성능 데이터를 시간대별로 엑셀에 저장"""
        try:
            import openpyxl
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment
            
            if not performance_data:
                logger.warning("저장할 성능 데이터가 없습니다.")
                return None
            
            # 엑셀 파일명 생성
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_package_name = package_name.replace('.', '_').replace(' ', '_')
            excel_filename = os.path.join(PERFORMANCE_LOG_DIR, f"performance_data_{safe_package_name}_{timestamp}.xlsx")
            
            # 워크북 생성
            wb = Workbook()
            ws = wb.active
            if ws is None:
                logger.error("워크시트 생성 실패")
                return None
            ws.title = "Performance Data"
            
            # 헤더 작성
            headers = ["시간", "회차", "메모리 사용량 (MB)", "CPU 사용률 (%)", "비고"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
            
            # 데이터 작성
            for row, data in enumerate(performance_data, 2):
                # 메모리 값 반올림 (소수점 1자리)
                memory_mb = data.get('memory_mb', 0)
                if isinstance(memory_mb, (int, float)) and memory_mb > 0:
                    memory_display = round(memory_mb, 1)
                else:
                    memory_display = 0
                
                # CPU 값 반올림 (소수점 1자리)
                cpu_percent = data.get('cpu_percent', 0)
                if isinstance(cpu_percent, (int, float)) and cpu_percent > 0:
                    cpu_display = round(cpu_percent, 1)
                else:
                    cpu_display = 0
                
                # 디버깅용 로그 추가
                logger.info(f"엑셀 행 {row} 저장 - 메모리: {memory_mb} → {memory_display}, CPU: {cpu_percent} → {cpu_display}")
                
                ws.cell(row=row, column=1, value=data.get('timestamp', 'N/A'))
                ws.cell(row=row, column=2, value=f"{data.get('run', 'N/A')}회차")
                ws.cell(row=row, column=3, value=memory_display)
                ws.cell(row=row, column=4, value=cpu_display)
                ws.cell(row=row, column=5, value="정상")
            
            # 열 너비 자동 조정
            from openpyxl.utils import get_column_letter
            for col_num in range(1, len(headers) + 1):
                column_letter = get_column_letter(col_num)
                max_length = 0
                for row_num in range(1, len(performance_data) + 2):
                    cell = ws.cell(row=row_num, column=col_num)
                    try:
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # 파일 저장
            wb.save(excel_filename)
            logger.info(f"성능 데이터 엑셀 저장 완료: {excel_filename}")
            return excel_filename
            
        except Exception as e:
            logger.error(f"성능 데이터 엑셀 저장 실패: {e}")
            return None

    def _add_run_result_to_details(self, run_num, duration_str, events, all_crash_logs, all_anr_logs, current_performance_data):
        """각 반복 완료 시 결과를 details에 추가"""
        try:
            # 이 반복에서 발생한 크래시/ANR 개수 계산
            crashes_in_run = len([log for log in all_crash_logs if log.get("run") == run_num])
            anrs_in_run = len([log for log in all_anr_logs if log.get("run") == run_num])
            
            # 이 반복의 성능 데이터 추출
            run_performance_data = [d for d in current_performance_data if d.get("run") == run_num]
            
            # 메모리/CPU 피크 계산
            mem_peak = "N/A"
            cpu_peak = "N/A"
            
            if run_performance_data:
                mem_values = [d["memory_mb"] for d in run_performance_data if d.get("memory_mb")]
                cpu_values = [d["cpu_percent"] for d in run_performance_data if d.get("cpu_percent")]
                
                if mem_values:
                    mem_peak = f"{round(max(mem_values))}MB"
                if cpu_values:
                    cpu_peak = f"{round(max(cpu_values))}%"
            
            # details에 추가
            detail_entry = {
                "repeat": f"{run_num}회차",
                "time": duration_str,
                "seed": str(self.current_repeat_seed) if self.current_repeat_seed else "N/A",
                "events": events,
                "crash": "❌ 1" if crashes_in_run > 0 else "✅ 0",
                "anr": "❌ 1" if anrs_in_run > 0 else "✅ 0",
                "timeout": "✅ 0",
                "mem_peak": mem_peak,
                "cpu_peak": cpu_peak,
                "start_time": self.repeat_start_times.get(run_num, "N/A")  # 반복 시작 시간 추가
            }

            if "details" not in self.test_context.current_test_report:
                self.test_context.current_test_report["details"] = []
            
            self.test_context.current_test_report["details"].append(detail_entry)
            
            # 회차별 완료 시 바로 UI 업데이트 (차트 포함)
            if self.completion_callback:
                try:
                    self.completion_callback(None, "UI_UPDATE_DETAILS")
                    # 실시간 차트 업데이트를 위한 추가 신호
                    self.completion_callback(None, "UI_UPDATE_CHARTS")
                except:
                    pass
            
        except Exception as e:
            logger.error(f"결과 세부사항 추가 중 오류: {e}")

    def stop_test(self):
        """테스트 중지"""
        if self.test_context.test_running:
            logger.info("테스트 중지 요청")
            self.test_context.test_running = False
            self.logcat_active = False
            self.monitoring_active = False
            
            # 포그라운드 모니터링 중지
            try:
                self.stop_foreground_monitoring()
                logger.info("테스트 중지: 포그라운드 모니터링 중지됨")
            except Exception as e:
                logger.error(f"테스트 중지 시 포그라운드 모니터링 중지 실패: {e}")
            
            if self.status_callback:
                try:
                    self.status_callback("테스트 중지됨")
                except:
                    pass
    
    def get_test_status(self) -> Dict[str, Any]:
        """현재 테스트 상태 반환"""
        return {
            "running": self.test_context.test_running,
            "elapsed_seconds": self.actual_elapsed_seconds
        }
    
    def calculate_time_correction(self, actual_duration: float, repeat_number: int) -> int:
        """실행 시간 기반 throttle 자동 보정 계산"""
        try:
            # 목표 시간과 실제 시간의 차이 계산
            time_diff = self.target_duration_per_repeat - actual_duration
            time_ratio = actual_duration / self.target_duration_per_repeat
            
            logger.info(f"⏱️ 시간 분석 (반복 {repeat_number}):")
            logger.info(f"   목표 시간: {self.target_duration_per_repeat}초 ({self.target_duration_per_repeat/60:.1f}분)")
            logger.info(f"   실제 시간: {actual_duration:.1f}초 ({actual_duration/60:.1f}분)")
            logger.info(f"   시간 차이: {time_diff:.1f}초")
            logger.info(f"   시간 비율: {time_ratio:.3f}")
            
            # 보정값 계산 (비율 기반)
            current_throttle = self.test_context.get_test_config()["throttle"]
            adjusted_throttle = current_throttle
            
            if abs(time_diff) > 30:  # 30초 이상 차이가 날 때만 보정
                if time_ratio < 0.85:  # 85% 미만이면 너무 빠름 - throttle 증가
                    throttle_increase = int(current_throttle * (1.15 - time_ratio))
                    adjusted_throttle = current_throttle + throttle_increase
                    adjustment_reason = f"실행 속도가 너무 빠름 (목표의 {time_ratio:.1%})"
                    
                elif time_ratio > 1.15:  # 115% 초과면 너무 느림 - throttle 감소
                    throttle_decrease = int(current_throttle * (time_ratio - 1.05))
                    adjusted_throttle = max(50, current_throttle - throttle_decrease)  # 최소 50ms
                    adjustment_reason = f"실행 속도가 너무 느림 (목표의 {time_ratio:.1%})"
                else:
                    adjustment_reason = "시간 차이가 허용 범위 내"
            else:
                adjustment_reason = "시간 차이가 미미함 (30초 이내)"
            
            # 극단적인 값 방지
            adjusted_throttle = max(50, min(500, adjusted_throttle))
            throttle_change = adjusted_throttle - current_throttle
            
            # 보정 이력 저장
            correction_record = {
                "repeat": repeat_number,
                "target_duration": self.target_duration_per_repeat,
                "actual_duration": actual_duration,
                "time_diff": time_diff,
                "time_ratio": time_ratio,
                "original_throttle": current_throttle,
                "adjusted_throttle": adjusted_throttle,
                "throttle_change": throttle_change,
                "reason": adjustment_reason
            }
            self.time_correction_history.append(correction_record)
            
            logger.info(f"🔧 Throttle 보정:")
            logger.info(f"   현재 Throttle: {current_throttle}ms")
            logger.info(f"   조정 Throttle: {adjusted_throttle}ms ({throttle_change:+d}ms)")
            logger.info(f"   보정 사유: {adjustment_reason}")
            
            return adjusted_throttle
            
        except Exception as e:
            logger.error(f"시간 보정 계산 중 오류: {e}")
            return self.test_context.get_test_config()["throttle"]
    
    def apply_time_correction(self, repeat_number: int, actual_duration: float):
        """다음 회차를 위한 시간 보정 적용"""
        try:
            # Deep Test 모드에서만 자동 보정 적용
            if self.test_context.preset_name != "Deep Test":
                return
            
            # 첫 번째 회차 이후부터 보정 적용
            if repeat_number < 1:
                return
            
            # 새로운 throttle 값 계산
            new_throttle = self.calculate_time_correction(actual_duration, repeat_number)
            
            # 테스트 설정 업데이트
            current_config = self.test_context.get_test_config()
            if new_throttle != current_config["throttle"]:
                # config 업데이트
                if self.test_context.preset_name in PRESETS:
                    PRESETS[self.test_context.preset_name]["throttle"] = new_throttle
                
                # 현재 컨텍스트 업데이트
                current_config["throttle"] = new_throttle
                self.test_context.throttle = new_throttle  # TestContext 직접 업데이트
                
                logger.info(f"✅ 다음 회차 Throttle 자동 조정: {new_throttle}ms")
                
                # 상태 콜백으로 UI에 알림
                if self.status_callback:
                    try:
                        status_msg = f"⏱️ 시간 보정: Throttle {new_throttle}ms로 조정 (목표: 18분/회차)"
                        self.status_callback(status_msg)
                    except:
                        pass
            else:
                logger.info("🔧 Throttle 유지: 보정 불필요")
                
        except Exception as e:
            logger.error(f"시간 보정 적용 중 오류: {e}")
    
    def get_time_correction_summary(self) -> Dict[str, Any]:
        """시간 보정 요약 정보 반환"""
        try:
            if not self.time_correction_history:
                return {"enabled": False, "message": "보정 이력 없음"}
            
            total_corrections = len(self.time_correction_history)
            avg_time_ratio = sum(record["time_ratio"] for record in self.time_correction_history) / total_corrections
            total_throttle_change = sum(record["throttle_change"] for record in self.time_correction_history)
            
            last_correction = self.time_correction_history[-1]
            
            return {
                "enabled": True,
                "target_duration": self.target_duration_per_repeat,
                "total_corrections": total_corrections,
                "avg_time_ratio": avg_time_ratio,
                "total_throttle_change": total_throttle_change,
                "last_correction": last_correction,
                "history": self.time_correction_history
            }
            
        except Exception as e:
            logger.error(f"시간 보정 요약 생성 중 오류: {e}")
            return {"enabled": False, "error": str(e)}
    
    def is_test_running(self) -> bool:
        """테스트 실행 중인지 확인"""
        return self.test_context.test_running
    
    def _validate_monkey_command(self, command: str, events: int, throttle: int, is_deep_test: bool):
        """Monkey 명령어 정확성 및 호환성 검증"""
        try:
            logger.info("🔍 Monkey 명령어 검증 시작...")
            
            # 1. 필수 파라미터 검증
            required_params = [
                "--throttle",
                "-p ",
                f" {events}"
            ]
            
            for param in required_params:
                if param not in command:
                    logger.error(f"❌ 필수 파라미터 누락: {param}")
                    return False
            
            # 2. 퍼센티지 합계 검증 (100%가 되어야 함)
            percentage_params = {
                '--pct-touch': 0,
                '--pct-motion': 0,
                '--pct-trackball': 0,
                '--pct-nav': 0,
                '--pct-majornav': 0,
                '--pct-syskeys': 0,
                '--pct-appswitch': 0,
                '--pct-anyevent': 0,
                '--pct-pinchzoom': 0,
                '--pct-rotation': 0
            }
            
            # 명령어에서 퍼센티지 값 추출
            import re
            for param_name in percentage_params:
                pattern = f"{param_name}\\s+(\\d+)"
                match = re.search(pattern, command)
                if match:
                    percentage_params[param_name] = int(match.group(1))
            
            total_percentage = sum(percentage_params.values())
            logger.info(f"이벤트 타입 분배: {percentage_params}")
            logger.info(f"총 퍼센티지: {total_percentage}%")
            
            if total_percentage != 100:
                logger.warning(f"⚠️ 이벤트 퍼센티지 합계가 100%가 아님: {total_percentage}%")
                if total_percentage < 90 or total_percentage > 110:
                    logger.error(f"❌ 퍼센티지 합계 오류가 심각함: {total_percentage}%")
                    return False
            
            # 3. Deep Test 특화 검증
            if is_deep_test:
                # throttle 값이 목표 시간에 맞는지 검증
                expected_duration = (events * throttle * 0.35) / 1000  # 35% 효율성
                target_duration = 18 * 60  # 18분
                
                time_accuracy = abs(expected_duration - target_duration) / target_duration
                logger.info(f"Deep Test 시간 정확도: 예상 {expected_duration/60:.1f}분, 목표 18분, 오차 {time_accuracy*100:.1f}%")
                
                if time_accuracy > 0.15:  # 15% 이상 오차
                    logger.warning(f"⚠️ Deep Test 시간 정확도 낮음: 오차 {time_accuracy*100:.1f}%")
            
            # 4. 호환성 검증을 위한 간단한 버전 확인 (--help 대신 version 사용)
            test_command = f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell monkey --version 2>/dev/null'
            try:
                import subprocess
                # Windows에서 콘솔 창 숨김 설정
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                
                # --version도 안되면 간단한 연결 테스트만
                simple_test = f'"{self.adb_client.adb_path}" -s {self.adb_client.device_serial} shell echo "monkey_test"'
                result = run_hidden_subprocess(simple_test, shell=True, capture_output=True, 
                                      text=True, timeout=5)
                
                if result.returncode == 0 and "monkey_test" in result.stdout:
                    logger.info("✅ ADB 연결 및 shell 명령어 호환성 확인 완료")
                else:
                    logger.warning(f"⚠️ ADB shell 테스트 응답 이상: {result.stderr[:100]}")
                    
            except Exception as e:
                logger.warning(f"⚠️ ADB 호환성 테스트 건너뛰기: {e}")
            
            # 5. 최종 검증 결과
            logger.info("✅ Monkey 명령어 검증 완료")
            logger.info(f"📋 명령어 요약:")
            logger.info(f"  • 이벤트 수: {events:,}개")
            logger.info(f"  • Throttle: {throttle}ms")
            logger.info(f"  • 모드: {'Deep Test (18분 정밀)' if is_deep_test else '일반 테스트'}")
            logger.info(f"  • 이벤트 분배: Touch {percentage_params.get('--pct-touch', 0)}%, Motion {percentage_params.get('--pct-motion', 0)}%, Any {percentage_params.get('--pct-anyevent', 0)}%")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Monkey 명령어 검증 중 오류: {e}")
            return False
    
    def _on_network_recovery(self, network_state, success: bool):
        """네트워크 복구 완료 시 호출되는 콜백"""
        try:
            if success:
                logger.info(f"🛜 네트워크 복구 완료: {network_state.value}")
                if self.status_callback:
                    self.status_callback(f"네트워크 복구됨: {network_state.value}")
            else:
                logger.warning(f"🚨 네트워크 복구 실패: {network_state.value}")
                if self.status_callback:
                    self.status_callback(f"네트워크 복구 실패: {network_state.value}")
        except Exception as e:
            logger.error(f"네트워크 복구 콜백 오류: {e}")
    
    def _apply_adaptive_optimization(self, preset_name: str, current_events: int, current_throttle: int) -> tuple[int, int]:
        """Gemini AI 기반 적응형 최적화 적용"""
        try:
            if not self.adaptive_tuner:
                return current_events, current_throttle
            
            # Gemini AI 분석 및 최적화 추천
            optimized_events, optimized_throttle, reasoning = self.adaptive_tuner.get_optimized_parameters(
                preset_name, current_events, current_throttle
            )
            
            # 최적화 적용
            if optimized_events != current_events or optimized_throttle != current_throttle:
                logger.info(f"🤖 Gemini AI 최적화 적용: {preset_name}")
                logger.info(f"   이벤트: {current_events} → {optimized_events}")
                logger.info(f"   스로틀: {current_throttle}ms → {optimized_throttle}ms") 
                logger.info(f"   추론: {reasoning}")
                
                # 적응형 파라미터 저장
                self.adaptive_events = optimized_events
                self.adaptive_throttle = optimized_throttle
                
                return optimized_events, optimized_throttle
            else:
                logger.debug(f"🤖 Gemini AI: {preset_name} 현재 설정이 최적상태")
                return current_events, current_throttle
                
        except Exception as e:
            logger.error(f"적응형 최적화 적용 오류: {e}")
            return current_events, current_throttle
    
    def _record_test_result_for_learning(self, preset_name: str, events: int, throttle: int, duration_minutes: float):
        """테스트 결과를 Gemini AI 학습용으로 기록"""
        try:
            if not self.adaptive_tuner:
                return
            
            package_name = getattr(self.test_context, 'app_package_name', '')
            self.adaptive_tuner.record_test_result(
                preset_name, events, throttle, duration_minutes, package_name
            )
            
            logger.debug(f"🤖 Gemini 학습 데이터 기록 완료: {preset_name} - {duration_minutes:.1f}분")
            
        except Exception as e:
            logger.error(f"학습 데이터 기록 오류: {e}")
    
    def _analyze_performance_with_gemini(self, preset_name: str, config: dict, actual_duration_minutes: float):
        """Gemini API를 사용한 성능 분석 및 최적화 권장"""
        try:
            if not self.gemini_enabled or not self.gemini_controller:
                logger.debug("Gemini AI 비활성화됨, 성능 분석 스킵")
                return
            
            # API 호출 빈도 증가를 위한 강제 로깅
            logger.info(f"🤖 Gemini API 분석 시작: {preset_name} (실행 시간: {actual_duration_minutes:.1f}분)")
            
            # 성능 데이터 준비
            current_performance = {
                'actual_duration': actual_duration_minutes * 60,  # 초 단위
                'target_duration': 18 * 60 if preset_name == "Deep Test" else config.get('target_duration', 0),
                'events_completed': config['events'],
                'throttle_used': config['throttle'],
                'accuracy_percent': self._calculate_accuracy_score(actual_duration_minutes, preset_name),
                'timestamp': time.time()
            }
            
            # 이전 성능 이력 가져오기
            performance_history = getattr(self, f'{preset_name.lower().replace(" ", "_")}_history', [])
            performance_history.append(current_performance)
            
            # 최근 5회만 유지
            if len(performance_history) > 5:
                performance_history = performance_history[-5:]
                setattr(self, f'{preset_name.lower().replace(" ", "_")}_history', performance_history)
            
            # 디바이스 정보 수집
            device_info = self._get_device_info()
            
            # 포그라운드 모니터 상태 추가
            foreground_status = self.get_foreground_monitor_status()
            if foreground_status.get('recovery_count', 0) > 0:
                logger.info(f"📱 앱 복구 이벤트: {foreground_status['recovery_count']}회 감지됨")
            
            # Gemini API 호출하여 분석 및 권장사항 받기
            logger.info(f"🤖 Gemini AI 성능 분석 중: {preset_name}")
            
            recommendations = self.gemini_controller.analyze_performance_and_recommend(
                performance_history=performance_history,
                current_run=len(performance_history),
                device_info=device_info,
                app_package=getattr(self.test_context, 'app_package_name', 'unknown')
            )
            
            if recommendations:
                # 권장사항 로깅
                logger.info(f"🤖 Gemini 분석 결과:")
                logger.info(f"   📊 요약: {recommendations.get('summary', 'N/A')}")
                logger.info(f"   📈 트렌드: {recommendations.get('trend_analysis', 'N/A')}")
                logger.info(f"   🎯 권장 이벤트: {recommendations.get('recommended_events', 'N/A')}")
                logger.info(f"   ⚡ 권장 throttle: {recommendations.get('recommended_throttle', 'N/A')}ms")
                logger.info(f"   📐 신뢰도: {recommendations.get('confidence', 'N/A')}%")
                
                if recommendations.get('risk_factors'):
                    logger.warning(f"   ⚠️ 위험요소: {', '.join(recommendations['risk_factors'])}")
                
                # 다음 실행을 위한 최적화 적용 (Deep Test의 경우만)
                if preset_name == "Deep Test" and recommendations.get('confidence', 0) > 70:
                    self._apply_gemini_recommendations(recommendations)
                    
                # 권장사항을 캐시에 저장
                self.gemini_controller.save_learning_data(current_performance)
                
            else:
                logger.warning("🤖 Gemini 분석 실패, 기본 로직 사용")
                
        except Exception as e:
            logger.error(f"Gemini 성능 분석 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _calculate_accuracy_score(self, actual_duration_minutes: float, preset_name: str) -> float:
        """실행 시간 정확도 점수 계산"""
        try:
            if preset_name == "Deep Test":
                target_minutes = 18.0
            elif preset_name == "Quick Test":
                target_minutes = 50.0
            elif preset_name == "Smoke Test":
                target_minutes = 35.0
            else:
                return 90.0  # 기본값
            
            # 목표 시간 대비 정확도 계산
            accuracy = max(0, 100 - abs(actual_duration_minutes - target_minutes) / target_minutes * 100)
            return round(accuracy, 1)
            
        except Exception as e:
            logger.error(f"정확도 계산 오류: {e}")
            return 75.0
    
    def _get_device_info(self) -> dict:
        """디바이스 정보 수집"""
        try:
            import subprocess
            from src.config import ADB_PATH
            
            device_info = {}
            
            # 디바이스 모델명
            try:
                result = run_hidden_subprocess([ADB_PATH, 'shell', 'getprop', 'ro.product.model'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    device_info['model'] = result.stdout.strip()
            except:
                device_info['model'] = 'Unknown'
            
            # Android 버전
            try:
                result = run_hidden_subprocess([ADB_PATH, 'shell', 'getprop', 'ro.build.version.release'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    device_info['android_version'] = result.stdout.strip()
            except:
                device_info['android_version'] = 'Unknown'
            
            # API 레벨
            try:
                result = run_hidden_subprocess([ADB_PATH, 'shell', 'getprop', 'ro.build.version.sdk'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    device_info['api_level'] = result.stdout.strip()
            except:
                device_info['api_level'] = 'Unknown'
            
            return device_info
            
        except Exception as e:
            logger.error(f"디바이스 정보 수집 오류: {e}")
            return {'model': 'Unknown', 'android_version': 'Unknown', 'api_level': 'Unknown'}
    
    def _apply_gemini_recommendations(self, recommendations: dict):
        """Gemini 권장사항을 다음 실행에 적용"""
        try:
            recommended_events = recommendations.get('recommended_events')
            recommended_throttle = recommendations.get('recommended_throttle')
            
            if recommended_events and 20000 <= recommended_events <= 24000:  # Deep Test 범위
                self.adaptive_events = recommended_events
                logger.info(f"🤖 Gemini 권장 이벤트 적용: {recommended_events}")
            
            if recommended_throttle and 100 <= recommended_throttle <= 200:  # 적절한 throttle 범위
                self.adaptive_throttle = recommended_throttle
                logger.info(f"🤖 Gemini 권장 throttle 적용: {recommended_throttle}ms")
            
        except Exception as e:
            logger.error(f"Gemini 권장사항 적용 오류: {e}")
    
    def start_network_monitoring(self):
        """네트워크 모니터링 시작"""
        try:
            if self.network_monitor and not self.network_monitor.monitoring_active:
                self.network_monitor.start_monitoring()
                logger.info("🛜 테스트 중 네트워크 모니터링 시작")
        except Exception as e:
            logger.error(f"네트워크 모니터링 시작 오류: {e}")
    
    def stop_network_monitoring(self):
        """네트워크 모니터링 중지"""
        try:
            if self.network_monitor and self.network_monitor.monitoring_active:
                self.network_monitor.stop_monitoring()
                logger.info("🛜 네트워크 모니터링 중지")
        except Exception as e:
            logger.error(f"네트워크 모니터링 중지 오류: {e}")
    
    def get_adaptive_performance_summary(self) -> Dict:
        """적응형 성능 요약 반환"""
        try:
            if not self.adaptive_tuner:
                return {"error": "적응형 튜너 없음"}
            
            preset_name = getattr(self.test_context, 'test_preset', '')
            if preset_name:
                return self.adaptive_tuner.get_preset_performance_summary(preset_name)
            else:
                return {"error": "프리셋 정보 없음"}
                
        except Exception as e:
            logger.error(f"적응형 성능 요약 생성 오류: {e}")
            return {"error": str(e)}
    
    def start_background_monitoring(self):
        """백그라운드 모니터링 시작"""
        try:
            if not self.test_context.app_package_name:
                logger.warning("패키지명이 없어 백그라운드 모니터링을 시작할 수 없습니다")
                return
            
            # ADB 클라이언트의 비동기 백그라운드 모니터링 시작
            self.background_monitor_thread = self.adb_client.async_background_monitor(
                self.test_context.app_package_name, 
                check_interval=3.0  # 3초마다 체크
            )
            
            logger.info(f"📱 백그라운드 모니터링 시작: {self.test_context.app_package_name}")
            
        except Exception as e:
            logger.error(f"백그라운드 모니터링 시작 오류: {e}")
    
    def stop_background_monitoring(self):
        """백그라운드 모니터링 중지"""
        try:
            # 이미 중지된 상태인지 확인
            monitoring_active = getattr(self.adb_client, '_monitoring_active', False)
            
            if hasattr(self, 'background_monitor_thread') and self.background_monitor_thread and monitoring_active:
                self.adb_client.stop_background_monitor()
                logger.info("📱 백그라운드 모니터링 중지됨")
            else:
                logger.debug("📱 백그라운드 모니터링이 이미 중지된 상태입니다")
            
        except Exception as e:
            logger.error(f"백그라운드 모니터링 중지 오류: {e}")
    
    def get_background_monitor_status(self) -> dict:
        """백그라운드 모니터 상태 반환"""
        try:
            if hasattr(self, 'background_monitor_thread') and self.background_monitor_thread:
                is_alive = self.background_monitor_thread.is_alive() if self.background_monitor_thread else False
                monitoring_active = getattr(self.adb_client, '_monitoring_active', False)
                
                return {
                    'monitoring': monitoring_active,
                    'thread_alive': is_alive,
                    'package_name': self.test_context.app_package_name
                }
            else:
                return {'monitoring': False, 'error': 'Monitor not started'}
                
        except Exception as e:
            logger.error(f"백그라운드 모니터 상태 확인 오류: {e}")
            return {'monitoring': False, 'error': str(e)}
