#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey 테스트 관리자
monkey_runner.py에서 분리된 테스트 관리 관련 기능들
"""
import time
import datetime
import threading
from typing import Dict, Any, Optional, Callable

from src.core.adb_client import AdbClient
from src.core.test_context import TestContext
from src.core.monkey_test_executor import MonkeyTestExecutor
from src.ui.ui_utils import calculate_precise_duration
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class MonkeyTestManager:
    """Monkey 테스트 관리를 담당하는 클래스"""
    
    def __init__(self, adb_client: AdbClient, test_context: TestContext):
        self.adb_client = adb_client
        self.test_context = test_context
        self.test_executor = MonkeyTestExecutor(adb_client, test_context)
        
        # 콜백 함수들
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        
        # 시간 추적
        self.test_start_time = None
        self.estimated_total_seconds = 0
        self.actual_elapsed_seconds = 0
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """진행 상황 콜백 설정"""
        self.progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[bool, str], None]):
        """완료 콜백 설정"""
        self.completion_callback = callback
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """상태 콜백 설정"""
        self.status_callback = callback
    
    def start_test(self) -> bool:
        """테스트 시작"""
        try:
            logger.info("🚀 Monkey 테스트 시작 준비")
            
            # 사전 검증
            if not self._validate_test_environment():
                return False
            
            # 테스트 데이터 초기화
            self.test_context.reset_test_data()
            self.test_context.test_running = True
            
            # 시간 계산
            self._calculate_estimated_time()
            
            # 실제 테스트 실행 (별도 스레드에서)
            test_thread = threading.Thread(target=self._execute_test_with_timing, daemon=True)
            test_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"테스트 시작 실패: {e}")
            self._emergency_cleanup()
            return False
    
    def _validate_test_environment(self) -> bool:
        """테스트 환경 검증"""
        try:
            # ADB 연결 확인
            if not self.adb_client:
                logger.error("ADB 클라이언트가 없습니다")
                return False
            
            devices = self.adb_client.get_connected_devices()
            if not devices:
                logger.error("연결된 디바이스가 없습니다")
                return False
            
            # 패키지명 확인
            if not self.test_context.app_package_name:
                logger.error("테스트할 앱 패키지명이 없습니다")
                return False
            
            # 앱 설치 확인
            installed_packages = self.adb_client.get_installed_packages()
            if self.test_context.app_package_name not in installed_packages:
                logger.error(f"앱이 설치되어 있지 않습니다: {self.test_context.app_package_name}")
                return False
            
            logger.info("✅ 테스트 환경 검증 완료")
            return True
            
        except Exception as e:
            logger.error(f"테스트 환경 검증 실패: {e}")
            return False
    
    def _calculate_estimated_time(self):
        """예상 테스트 시간 계산"""
        try:
            preset_data = self.test_context.get_test_config()
            self.estimated_total_seconds, time_breakdown = calculate_precise_duration(
                preset_data["events"], 
                preset_data["repeats"], 
                preset_data["throttle"]
            )
            
            logger.info(f"예상 테스트 시간: {self.estimated_total_seconds}초 ({self.estimated_total_seconds/60:.1f}분)")
            logger.info(f"시간 세부사항: {time_breakdown}")
            
        except Exception as e:
            logger.warning(f"예상 시간 계산 실패: {e}")
            self.estimated_total_seconds = 300  # 기본값 5분
    
    def _execute_test_with_timing(self):
        """정밀한 시간 추적과 함께 테스트 실행"""
        self.test_start_time = time.time()
        
        logger.info(f"{'='*80}")
        logger.info(f"🚀 테스트 실행 시작!")
        logger.info(f"{'='*80}")
        
        # 상태 업데이트
        self._safe_callback(self.status_callback, "테스트 실행 중...")
        
        # 실제 테스트 실행
        success = self.test_executor.run_single_test_cycle()
        
        # 테스트 완료 처리
        self._finalize_test(success)
    
    def _finalize_test(self, success: bool):
        """테스트 완료 처리"""
        test_end_time = time.time()
        if self.test_start_time is not None:
            self.actual_elapsed_seconds = test_end_time - self.test_start_time
        else:
            self.actual_elapsed_seconds = 0
        
        # 시간 정확도 분석
        accuracy_percentage = 100.0
        if self.estimated_total_seconds > 0:
            accuracy_percentage = (self.actual_elapsed_seconds / self.estimated_total_seconds) * 100
        
        logger.info(f"{'='*80}")
        logger.info(f"🎯 테스트 완료!")
        logger.info(f"   예상 시간: {self.estimated_total_seconds}초")
        logger.info(f"   실제 시간: {int(self.actual_elapsed_seconds)}초")
        logger.info(f"   시간 정확도: {accuracy_percentage:.1f}%")
        logger.info(f"   성공 여부: {'성공' if success else '실패'}")
        logger.info(f"{'='*80}")
        
        # 테스트 결과 생성
        self._generate_test_report(success)
        
        # 완료 콜백 호출
        result_message = "테스트 성공" if success else "테스트 실패"
        self._safe_callback(self.completion_callback, success, result_message)
        
        # 정리
        self.test_context.test_running = False
    
    def _generate_test_report(self, success: bool):
        """테스트 리포트 생성"""
        try:
            preset_data = self.test_context.get_test_config()
            
            # 기본 리포트 정보
            report_summary = {
                "test_success": success,
                "package_name": self.test_context.app_package_name,
                "test_date": datetime.datetime.now().isoformat(),
                "estimated_time": self.estimated_total_seconds,
                "actual_time": self.actual_elapsed_seconds,
                "settings": preset_data
            }
            
            # 디바이스 정보 추가
            device_info = self._collect_device_info()
            report_summary.update(device_info)
            
            # TestContext에 리포트 업데이트
            if not hasattr(self.test_context, 'current_test_report') or not self.test_context.current_test_report:
                self.test_context.current_test_report = {"summary": {}, "details": {}}
            
            self.test_context.current_test_report["summary"].update(report_summary)
            
            logger.info("✅ 테스트 리포트 생성 완료")
            
        except Exception as e:
            logger.error(f"테스트 리포트 생성 오류: {e}")
    
    def _collect_device_info(self) -> Dict[str, Any]:
        """디바이스 정보 수집"""
        device_info = {
            "device_model": "Unknown",
            "android_version": "Unknown",
            "connection_type": "Unknown"
        }
        
        try:
            if self.adb_client:
                devices = self.adb_client.get_connected_devices()
                if not devices:
                    return device_info
                # 디바이스 모델
                device_model = self.adb_client.run_command(
                    "shell getprop ro.product.model", timeout=5
                ).strip()
                if device_model:
                    device_info["device_model"] = device_model
                
                # 안드로이드 버전
                android_version = self.adb_client.run_command(
                    "shell getprop ro.build.version.release", timeout=5
                ).strip()
                if android_version:
                    device_info["android_version"] = android_version
                
                # 연결 방식 확인
                devices_output = self.adb_client.run_command("devices", timeout=5)
                if "device" in devices_output:
                    lines = devices_output.strip().split('\n')[1:]
                    for line in lines:
                        if "device" in line:
                            device_id = line.split('\t')[0]
                            if ':' in device_id and '.' in device_id:
                                device_info["connection_type"] = "무선 (Wireless)"
                            else:
                                device_info["connection_type"] = "USB"
                            break
                            
        except Exception as e:
            logger.warning(f"디바이스 정보 수집 오류: {e}")
        
        return device_info
    
    def _safe_callback(self, callback: Optional[Callable], *args):
        """콜백 함수를 안전하게 호출"""
        if not callback:
            return
        
        try:
            # 콜백을 별도 스레드에서 실행하여 메인 스레드 블로킹 방지
            callback_thread = threading.Thread(
                target=lambda: callback(*args), 
                daemon=True
            )
            callback_thread.start()
            callback_thread.join(timeout=1.0)  # 최대 1초 대기
            
            if callback_thread.is_alive():
                logger.warning("콜백 함수 응답 지연, 건너뛰기")
                
        except Exception as e:
            logger.warning(f"콜백 함수 실행 중 오류: {e}")
    
    def _emergency_cleanup(self):
        """비상 정리 작업"""
        try:
            logger.warning("비상 정리 작업 수행")
            self.test_context.test_running = False
            self.test_executor.logcat_active = False
            self.test_executor.monitoring_active = False
            
        except Exception as e:
            logger.error(f"비상 정리 작업 오류: {e}")
    
    def stop_test(self):
        """테스트 중지"""
        logger.info("테스트 중지 요청")
        self.test_context.test_running = False
        self.test_executor.stop_test()
    
    def get_test_status(self) -> Dict[str, Any]:
        """현재 테스트 상태 반환"""
        return {
            "running": self.test_context.test_running,
            "start_time": self.test_start_time,
            "estimated_duration": self.estimated_total_seconds,
            "elapsed_time": time.time() - self.test_start_time if self.test_start_time else 0
        }
