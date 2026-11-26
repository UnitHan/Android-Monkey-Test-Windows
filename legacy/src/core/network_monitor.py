#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네트워크 상태 모니터링 및 자동 복구 시스템
몽키 테스트 중 비행기 모드나 데이터 OFF 감지 시 자동으로 복구하는 기능
"""
import logging
import threading
import time
import subprocess
from typing import Optional, Callable
from enum import Enum
from src.utils.subprocess_utils import run_hidden_subprocess

logger = logging.getLogger(__name__)


class NetworkState(Enum):
    """네트워크 상태 열거형"""
    NORMAL = "normal"
    AIRPLANE_MODE = "airplane_mode"  
    DATA_DISABLED = "data_disabled"
    WIFI_DISABLED = "wifi_disabled"
    UNKNOWN = "unknown"


class NetworkMonitor:
    """네트워크 상태 모니터링 및 자동 복구 클래스"""
    
    def __init__(self, adb_client, device_serial: str):
        self.adb_client = adb_client
        self.device_serial = device_serial
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.check_interval = 10  # 10초마다 체크
        self.recovery_callback: Optional[Callable] = None
        
        # 복구 시도 관련
        self.max_recovery_attempts = 3
        self.recovery_attempts = {}  # 각 문제별 복구 시도 횟수
        
    def start_monitoring(self):
        """네트워크 모니터링 시작"""
        if self.monitoring_active:
            logger.warning("네트워크 모니터링이 이미 활성화되어 있습니다")
            return
            
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_network, daemon=True)
        self.monitor_thread.start()
        logger.info("🛜 네트워크 상태 모니터링 시작")
    
    def stop_monitoring(self):
        """네트워크 모니터링 중지"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            self.monitor_thread = None
        logger.info("🛜 네트워크 상태 모니터링 중지")
    
    def set_recovery_callback(self, callback: Callable):
        """복구 완료 시 호출될 콜백 함수 설정"""
        self.recovery_callback = callback
    
    def _monitor_network(self):
        """네트워크 상태 모니터링 루프"""
        logger.info("네트워크 모니터링 루프 시작")
        
        while self.monitoring_active:
            try:
                # 네트워크 상태 확인
                network_state = self._check_network_state()
                
                if network_state != NetworkState.NORMAL:
                    logger.warning(f"🚨 네트워크 문제 감지: {network_state.value}")
                    self._handle_network_issue(network_state)
                
                # 다음 체크까지 대기
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"네트워크 모니터링 중 오류: {e}")
                time.sleep(self.check_interval * 2)  # 오류 시 더 오래 대기
    
    def _check_network_state(self) -> NetworkState:
        """현재 네트워크 상태 확인"""
        try:
            # 1. 비행기 모드 확인
            if self._is_airplane_mode_enabled():
                return NetworkState.AIRPLANE_MODE
            
            # 2. 모바일 데이터 상태 확인
            if not self._is_mobile_data_enabled():
                return NetworkState.DATA_DISABLED
            
            # 3. WiFi 상태 확인 (선택적)
            # if not self._is_wifi_enabled():
            #     return NetworkState.WIFI_DISABLED
            
            return NetworkState.NORMAL
            
        except Exception as e:
            logger.error(f"네트워크 상태 확인 오류: {e}")
            return NetworkState.UNKNOWN
    
    def _is_airplane_mode_enabled(self) -> bool:
        """비행기 모드 활성화 여부 확인"""
        try:
            cmd = ["adb", "-s", self.device_serial, "shell", 
                   "settings", "get", "global", "airplane_mode_on"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                value = result.stdout.strip()
                return value == "1"
            else:
                logger.warning(f"비행기 모드 상태 확인 실패: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"비행기 모드 확인 오류: {e}")
            return False
    
    def _is_mobile_data_enabled(self) -> bool:
        """모바일 데이터 활성화 여부 확인"""
        try:
            cmd = ["adb", "-s", self.device_serial, "shell", 
                   "settings", "get", "global", "mobile_data"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                value = result.stdout.strip()
                return value == "1"
            else:
                # 다른 방법으로 시도
                cmd2 = ["adb", "-s", self.device_serial, "shell", 
                        "dumpsys", "telephony.registry", "|", "grep", "mDataConnectionState"]
                result2 = run_hidden_subprocess(cmd2, capture_output=True, text=True, timeout=5, shell=True)
                
                if result2.returncode == 0:
                    # 데이터 연결 상태가 2 (CONNECTED)인지 확인
                    return "mDataConnectionState=2" in result2.stdout
                
                logger.warning(f"모바일 데이터 상태 확인 실패")
                return True  # 확인 실패 시 정상으로 가정
                
        except Exception as e:
            logger.error(f"모바일 데이터 확인 오류: {e}")
            return True  # 확인 실패 시 정상으로 가정
    
    def _is_wifi_enabled(self) -> bool:
        """WiFi 활성화 여부 확인"""
        try:
            cmd = ["adb", "-s", self.device_serial, "shell", 
                   "settings", "get", "global", "wifi_on"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                value = result.stdout.strip()
                return value == "1"
            else:
                logger.warning(f"WiFi 상태 확인 실패: {result.stderr}")
                return True  # 확인 실패 시 정상으로 가정
                
        except Exception as e:
            logger.error(f"WiFi 확인 오류: {e}")
            return True  # 확인 실패 시 정상으로 가정
    
    def _handle_network_issue(self, network_state: NetworkState):
        """네트워크 문제 처리 및 복구 시도"""
        state_key = network_state.value
        
        # 복구 시도 횟수 확인
        attempts = self.recovery_attempts.get(state_key, 0)
        if attempts >= self.max_recovery_attempts:
            logger.warning(f"최대 복구 시도 횟수 초과: {state_key} ({attempts}회)")
            return
        
        # 복구 시도
        success = False
        if network_state == NetworkState.AIRPLANE_MODE:
            success = self._recover_airplane_mode()
        elif network_state == NetworkState.DATA_DISABLED:
            success = self._recover_mobile_data()
        elif network_state == NetworkState.WIFI_DISABLED:
            success = self._recover_wifi()
        
        # 복구 시도 횟수 업데이트
        self.recovery_attempts[state_key] = attempts + 1
        
        if success:
            logger.info(f"✅ 네트워크 복구 성공: {state_key}")
            # 복구 성공 시 시도 횟수 리셋
            self.recovery_attempts[state_key] = 0
            
            # 콜백 호출
            if self.recovery_callback:
                try:
                    self.recovery_callback(network_state, True)
                except Exception as e:
                    logger.error(f"복구 콜백 호출 오류: {e}")
        else:
            logger.error(f"❌ 네트워크 복구 실패: {state_key} (시도 {attempts + 1}회)")
    
    def _recover_airplane_mode(self) -> bool:
        """비행기 모드 해제"""
        try:
            logger.info("✈️ 비행기 모드 해제 시도...")
            
            # 방법 1: connectivity 명령어 사용
            cmd = ["adb", "-s", self.device_serial, "shell", 
                   "cmd", "connectivity", "airplane-mode", "disable"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                time.sleep(3)  # 설정 적용 대기
                
                # 복구 확인
                if not self._is_airplane_mode_enabled():
                    logger.info("✅ 비행기 모드 해제 성공 (connectivity 명령어)")
                    return True
            
            # 방법 2: settings 명령어 사용
            cmd2 = ["adb", "-s", self.device_serial, "shell", 
                    "settings", "put", "global", "airplane_mode_on", "0"]
            result2 = run_hidden_subprocess(cmd2, capture_output=True, text=True, timeout=10)
            
            if result2.returncode == 0:
                # 브로드캐스트로 변경사항 알림
                cmd3 = ["adb", "-s", self.device_serial, "shell", 
                        "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", 
                        "--ez", "state", "false"]
                run_hidden_subprocess(cmd3, capture_output=True, text=True, timeout=5)
                
                time.sleep(3)  # 설정 적용 대기
                
                # 복구 확인
                if not self._is_airplane_mode_enabled():
                    logger.info("✅ 비행기 모드 해제 성공 (settings 명령어)")
                    return True
            
            logger.error("❌ 비행기 모드 해제 실패")
            return False
            
        except Exception as e:
            logger.error(f"비행기 모드 해제 오류: {e}")
            return False
    
    def _recover_mobile_data(self) -> bool:
        """모바일 데이터 활성화"""
        try:
            logger.info("📶 모바일 데이터 활성화 시도...")
            
            # 방법 1: svc 명령어 사용
            cmd = ["adb", "-s", self.device_serial, "shell", "svc", "data", "enable"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                time.sleep(3)  # 설정 적용 대기
                
                # 복구 확인
                if self._is_mobile_data_enabled():
                    logger.info("✅ 모바일 데이터 활성화 성공 (svc 명령어)")
                    return True
            
            # 방법 2: settings 명령어 사용
            cmd2 = ["adb", "-s", self.device_serial, "shell", 
                    "settings", "put", "global", "mobile_data", "1"]
            result2 = run_hidden_subprocess(cmd2, capture_output=True, text=True, timeout=10)
            
            if result2.returncode == 0:
                time.sleep(3)  # 설정 적용 대기
                
                # 복구 확인
                if self._is_mobile_data_enabled():
                    logger.info("✅ 모바일 데이터 활성화 성공 (settings 명령어)")
                    return True
            
            logger.error("❌ 모바일 데이터 활성화 실패")
            return False
            
        except Exception as e:
            logger.error(f"모바일 데이터 활성화 오류: {e}")
            return False
    
    def _recover_wifi(self) -> bool:
        """WiFi 활성화"""
        try:
            logger.info("📶 WiFi 활성화 시도...")
            
            # svc 명령어 사용
            cmd = ["adb", "-s", self.device_serial, "shell", "svc", "wifi", "enable"]
            result = run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                time.sleep(3)  # 설정 적용 대기
                
                # 복구 확인
                if self._is_wifi_enabled():
                    logger.info("✅ WiFi 활성화 성공")
                    return True
            
            logger.error("❌ WiFi 활성화 실패")
            return False
            
        except Exception as e:
            logger.error(f"WiFi 활성화 오류: {e}")
            return False
    
    def force_recovery_all(self):
        """모든 네트워크 설정 강제 복구"""
        logger.info("🔧 모든 네트워크 설정 강제 복구 시도")
        
        # 복구 시도 횟수 리셋
        self.recovery_attempts.clear()
        
        # 모든 네트워크 설정 복구
        airplane_success = self._recover_airplane_mode()
        data_success = self._recover_mobile_data()
        wifi_success = self._recover_wifi()
        
        if airplane_success and data_success and wifi_success:
            logger.info("✅ 모든 네트워크 설정 복구 완료")
            return True
        else:
            logger.warning(f"⚠️ 일부 네트워크 설정 복구 실패 - 비행기모드: {airplane_success}, 데이터: {data_success}, WiFi: {wifi_success}")
            return False
    
    def get_network_status_summary(self) -> dict:
        """현재 네트워크 상태 요약 반환"""
        try:
            return {
                "airplane_mode": self._is_airplane_mode_enabled(),
                "mobile_data": self._is_mobile_data_enabled(),
                "wifi": self._is_wifi_enabled(),
                "overall_state": self._check_network_state().value,
                "recovery_attempts": self.recovery_attempts.copy()
            }
        except Exception as e:
            logger.error(f"네트워크 상태 요약 생성 오류: {e}")
            return {"error": str(e)}


def create_network_monitor(adb_client, device_serial: str) -> NetworkMonitor:
    """네트워크 모니터 인스턴스 생성 팩토리 함수"""
    return NetworkMonitor(adb_client, device_serial)
