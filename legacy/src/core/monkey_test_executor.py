#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey 테스트 실행기
monkey_runner.py에서 분리된 테스트 실행 관련 기능들
"""
import os
import re
import time
import threading
import subprocess
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable
from src.utils.subprocess_utils import run_hidden_subprocess, popen_hidden_subprocess

from src.core.adb_client import AdbClient
from src.core.test_context import TestContext
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class MonkeyTestExecutor:
    """Monkey 테스트 실행을 담당하는 클래스"""
    
    def __init__(self, adb_client: AdbClient, test_context: TestContext):
        self.adb_client = adb_client
        self.test_context = test_context
        self.logcat_active = False
        self.monitoring_active = False
        
    def run_single_test_cycle(self) -> bool:
        """단일 테스트 사이클 실행"""
        try:
            preset_data = self.test_context.get_test_config()
            package_name = self.test_context.app_package_name
            
            if not package_name:
                logger.error("패키지명이 설정되지 않았습니다")
                return False
                
            events = preset_data["events"]
            repeats = preset_data["repeats"] 
            throttle = preset_data["throttle"]
            seed = preset_data["seed"]
            
            logger.info(f"테스트 설정: {events}개 이벤트, {repeats}회 반복, {throttle}ms 간격")
            
            # 로그 수집 컨테이너
            all_crash_logs = []
            all_anr_logs = []
            all_logcats = []
            current_performance_data = []
            
            test_success = True
            
            for i in range(1, repeats + 1):
                logger.info(f"🚀 테스트 회차 {i}/{repeats} 시작!")
                
                # 테스트 중단 확인
                if not self.test_context.test_running:
                    logger.info(f"테스트가 중단되었습니다. 반복 {i}에서 종료.")
                    test_success = False
                    break
                
                # 앱 재시작
                restart_success = self._restart_app_before_test(package_name)
                if not restart_success:
                    logger.warning(f"반복 {i} 앱 재시작 실패, 테스트 계속 진행")
                
                # Monkey 명령어 실행
                monkey_success = self._execute_monkey_command(
                    package_name, events, throttle, seed, i,
                    all_crash_logs, all_anr_logs, all_logcats, current_performance_data
                )
                
                if not monkey_success:
                    logger.error(f"반복 {i} Monkey 명령 실행 실패")
                    test_success = False
                    break
                    
            # 모니터링 정리
            self.logcat_active = False
            self.monitoring_active = False
            
            # 결과 저장
            self._save_test_results(all_crash_logs, all_anr_logs, all_logcats, current_performance_data)
            
            return test_success
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
            self.logcat_active = False
            self.monitoring_active = False
            return False
    
    def _restart_app_before_test(self, package_name: str) -> bool:
        """테스트 전 앱 재시작"""
        try:
            logger.debug(f"앱 재시작 시작: {package_name}")
            
            # 앱 강제 종료
            self.adb_client.run_command(f"shell am force-stop {package_name}", timeout=5)
            time.sleep(0.5)
            
            # 앱 시작
            launch_result = self.adb_client.run_command(
                f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1", 
                timeout=10
            )
            
            if "Events injected: 1" in launch_result:
                logger.debug(f"앱 재시작 성공: {package_name}")
                time.sleep(1)  # 앱 로딩 대기
                return True
            else:
                logger.warning(f"앱 재시작 실패: {package_name}")
                return False
                
        except Exception as e:
            logger.error(f"앱 재시작 중 오류: {e}")
            return False
    
    def _execute_monkey_command(self, package_name: str, events: int, throttle: int, 
                              seed: int, iteration: int, all_crash_logs: List, 
                              all_anr_logs: List, all_logcats: List, 
                              current_performance_data: List) -> bool:
        """Monkey 명령어 실행"""
        try:
            if not self.adb_client.adb_path or not self.adb_client.device_serial:
                logger.error("ADB 경로 또는 디바이스 시리얼이 없습니다")
                return False
                
            # Monkey 명령어 구성
            full_monkey_command = [
                self.adb_client.adb_path, "-s", self.adb_client.device_serial, "shell", "monkey",
                "-p", package_name,
                "--throttle", str(throttle),
                "-s", str(seed),
                "--ignore-crashes", "--ignore-timeouts", "--ignore-security-exceptions",
                "--monitor-native-crashes", "--kill-process-after-error",
                "--pct-touch", "25", "--pct-motion", "20", "--pct-nav", "15", 
                "--pct-majornav", "10", "--pct-syskeys", "5", "--pct-appswitch", "3", 
                "--pct-anyevent", "22", "--pct-trackball", "0", "--pct-pinchzoom", "0", 
                "--pct-rotation", "0",
                "--bugreport",
                "-v", "-v", str(events)
            ]
            
            logger.info(f"Monkey 실행 시작 - 반복 {iteration}")
            
            # 로그캣 모니터링 시작
            self.logcat_active = True
            logcat_process = self._start_logcat_monitoring(
                iteration, package_name, all_crash_logs, all_anr_logs, all_logcats
            )
            
            # 성능 모니터링 시작
            self.monitoring_active = True
            performance_thread = threading.Thread(
                target=self._monitor_performance, 
                args=(package_name, iteration, current_performance_data)
            )
            performance_thread.daemon = True
            performance_thread.start()
            
            # Monkey 실행
            startup_info = None
            if os.name == 'nt':  # Windows
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = subprocess.SW_HIDE
            
            monkey_process = popen_hidden_subprocess(
                full_monkey_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                startupinfo=startup_info
            )
            
            # Monkey 실행 완료 대기
            stdout, stderr = monkey_process.communicate(timeout=300)  # 5분 타임아웃
            
            # 모니터링 정리
            self.logcat_active = False
            self.monitoring_active = False
            
            if logcat_process:
                try:
                    logcat_process.terminate()
                    logcat_process.wait(timeout=2)
                except:
                    pass
            
            # Monkey 결과 분석
            if monkey_process.returncode == 0:
                logger.info(f"반복 {iteration} Monkey 실행 성공")
                return True
            else:
                logger.error(f"반복 {iteration} Monkey 실행 실패 (코드: {monkey_process.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"반복 {iteration} Monkey 실행 타임아웃")
            return False
        except Exception as e:
            logger.error(f"반복 {iteration} Monkey 실행 중 오류: {e}")
            return False
    
    def _start_logcat_monitoring(self, iteration: int, package_name: str,
                               all_crash_logs: List, all_anr_logs: List, 
                               all_logcats: List) -> Optional[subprocess.Popen]:
        """로그캣 모니터링 시작"""
        try:
            if not self.adb_client.adb_path or not self.adb_client.device_serial:
                logger.error("ADB 경로 또는 디바이스 시리얼이 없습니다")
                return None
            
            # Windows에서 콘솔 창 숨김
            startupinfo = None
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
            # 로그캣 클리어
            run_hidden_subprocess([
                self.adb_client.adb_path, "-s", self.adb_client.device_serial, 
                "logcat", "-c"
            ], timeout=5, check=False, startupinfo=startupinfo)
            
            # 로그캣 시작
            logcat_process = popen_hidden_subprocess([
                self.adb_client.adb_path, "-s", self.adb_client.device_serial, "logcat"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', startupinfo=startupinfo)
            
            # 로그 읽기 스레드 시작
            logcat_thread = threading.Thread(
                target=self._read_logcat,
                args=(logcat_process, iteration, package_name, all_crash_logs, all_anr_logs, all_logcats)
            )
            logcat_thread.daemon = True
            logcat_thread.start()
            
            return logcat_process
            
        except Exception as e:
            logger.error(f"로그캣 모니터링 시작 오류: {e}")
            return None
    
    def _read_logcat(self, logcat_process: subprocess.Popen, iteration: int, 
                   package_name: str, all_crash_logs: List, all_anr_logs: List, 
                   all_logcats: List):
        """로그캣 읽기 (별도 스레드에서 실행)"""
        try:
            if not logcat_process.stdout:
                logger.error("로그캣 stdout이 없습니다")
                return
                
            while self.logcat_active and logcat_process.poll() is None:
                line = logcat_process.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                all_logcats.append(line)
                
                # 크래시 감지
                if any(keyword in line.lower() for keyword in ["fatal exception", "crash", "segmentation fault"]):
                    all_crash_logs.append(f"[반복 {iteration}] {line}")
                
                # ANR 감지
                if any(keyword in line.lower() for keyword in ["anr", "application not responding"]):
                    all_anr_logs.append(f"[반복 {iteration}] {line}")
                    
        except Exception as e:
            logger.error(f"로그캣 읽기 오류: {e}")
    
    def _monitor_performance(self, package_name: str, iteration: int, 
                           performance_data: List):
        """성능 모니터링 (별도 스레드에서 실행)"""
        try:
            while self.monitoring_active:
                # CPU 사용률 수집 - adb_client 메서드 사용
                cpu_usage = self.adb_client.get_cpu_usage(package_name)
                if cpu_usage is None:
                    cpu_usage = 0.0
                
                # 메모리 사용률 수집 - adb_client 메서드 사용
                memory_mb = self.adb_client.get_memory_info(package_name)
                if memory_mb is None:
                    memory_mb = 0.0
                
                # 배터리 정보 수집
                battery_info = self.adb_client.run_command(
                    "shell dumpsys battery", timeout=3
                )
                
                performance_data.append({
                    "timestamp": time.time(),
                    "iteration": iteration,
                    "cpu_usage": cpu_usage,
                    "memory_mb": memory_mb,
                    "battery_info": battery_info
                })
                
                time.sleep(5)  # 5초 간격으로 수집
                
        except Exception as e:
            logger.error(f"성능 모니터링 오류: {e}")
    
    def _save_test_results(self, crash_logs: List, anr_logs: List, 
                         logcat_logs: List, performance_data: List):
        """테스트 결과 저장"""
        try:
            # TestContext에 결과 저장
            self.test_context.current_test_report = {
                "summary": {
                    "total_crashes": len(crash_logs),
                    "total_anrs": len(anr_logs),
                    "total_logs": len(logcat_logs)
                },
                "details": {
                    "crashes": crash_logs,
                    "anrs": anr_logs,
                    "logs": logcat_logs[:1000]  # 최근 1000개만 저장
                },
                "performance": performance_data
            }
            
            logger.info(f"테스트 결과 저장 완료: 크래시 {len(crash_logs)}건, ANR {len(anr_logs)}건")
            
        except Exception as e:
            logger.error(f"테스트 결과 저장 오류: {e}")
    
    def stop_test(self):
        """테스트 중지"""
        logger.info("테스트 중지 요청")
        self.test_context.test_running = False
        self.logcat_active = False
        self.monitoring_active = False
