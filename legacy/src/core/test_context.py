#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테스트 컨텍스트 관리
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import datetime

@dataclass
class TestContext:
    """테스트 실행 컨텍스트"""
    device_serial: Optional[str] = None
    is_wireless_mode: bool = False
    app_package_name: Optional[str] = None
    test_running: bool = False
    logcat_active: bool = False
    monitoring_active: bool = False
    
    # 디바이스 정보 (고정값)
    device_model: str = "LM-G710N"  # LG G7 ThinQ
    android_version: str = "Android 9"
    connection_mode: str = "USB"
    
    # 테스트 설정
    events: int = 1000
    repeats: int = 3
    throttle: int = 50
    seed: int = 1000
    preset_name: str = "Standard Test"
    
    # 결과 데이터
    current_test_report: Dict[str, Any] = field(default_factory=dict)
    current_performance_data: List[Dict[str, Any]] = field(default_factory=list)
    
    def reset_test_data(self):
        """테스트 데이터 초기화"""
        self.current_test_report = {
            "summary": {},
            "details": [],
            "issues": [],
            "logs": {}
        }
        self.current_performance_data = []
        self.test_running = False
        self.logcat_active = False
        self.monitoring_active = False
    
    def update_device_info(self, adb_client):
        """ADB 클라이언트로부터 실제 디바이스 정보 업데이트"""
        try:
            if adb_client:
                device_info = adb_client.get_device_info()
                self.device_model = f"{device_info.get('model', '알 수 없음')}"
                self.android_version = f"{device_info.get('android_version', '알 수 없음')}"
                self.connection_mode = adb_client.get_connection_mode()
                self.device_serial = adb_client.device_serial or "알 수 없음"
        except Exception as e:
            print(f"디바이스 정보 업데이트 오류: {e}")
    
    def get_test_summary(self) -> Dict[str, Any]:
        """테스트 요약 정보 반환"""        
        return {
            "test_target": self.app_package_name or "N/A",
            "test_tool": "Android Monkey",
            "test_period": datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            "preset": f"{self.preset_name} ({self.events} events x {self.repeats}회)",
            "total_events": self.events * self.repeats,
            "device": f"{self.device_model} ({self.device_serial})",
            "device_model": self.device_model,
            "android_version": self.android_version,
            "connection_mode": self.connection_mode,
            "device_serial": self.device_serial,
            "execution_time": "00분"  # 기본값
        }
    
    def get_test_config(self) -> Dict[str, Any]:
        """현재 테스트 설정 반환"""
        return {
            "events": self.events,
            "repeats": self.repeats,
            "throttle": self.throttle,
            "seed": self.seed,
            "preset_name": self.preset_name
        }
    
    def set_preset_config(self, preset_name: str, config: Dict[str, Any]):
        """프리셋 설정 적용"""
        self.preset_name = preset_name
        self.events = config.get("events", self.events)
        self.repeats = config.get("repeats", self.repeats)
        self.throttle = config.get("throttle", self.throttle)
        self.seed = config.get("seed", self.seed)
    
    def set_custom_config(self, events: int, repeats: int, throttle: int, seed: int):
        """사용자 정의 설정 적용"""
        self.preset_name = "Custom"
        self.events = events
        self.repeats = repeats
        self.throttle = throttle
        self.seed = seed
