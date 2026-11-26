#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 포그라운드 상태 모니터링 및 자동 복구
"""
import asyncio
import threading
import subprocess
import time
import logging
from typing import Optional, Callable
import re
from src.utils.subprocess_utils import run_hidden_subprocess

logger = logging.getLogger(__name__)

class AppForegroundMonitor:
    """앱이 백그라운드로 이동했을 때 즉시 포그라운드로 복구하는 모니터"""
    
    def __init__(self, adb_path: str, package_name: str):
        self.adb_path = adb_path
        self.package_name = package_name
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 2.0  # 2초마다 체크 (덜 빈번하게)
        self.recovery_callback: Optional[Callable] = None
        self.recovery_count = 0
        self.last_recovery_time = 0
        self.last_foreground_check = 0  # 마지막으로 포그라운드 확인한 시간
        
    def set_recovery_callback(self, callback: Callable[[str], None]):
        """백그라운드 감지 시 호출할 콜백 설정"""
        self.recovery_callback = callback
    
    def start_monitoring(self):
        """앱 상태 모니터링 시작"""
        if self.monitoring:
            logger.warning("이미 모니터링이 실행 중입니다")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"🔍 앱 포그라운드 모니터링 시작: {self.package_name}")
        logger.info(f"   - 체크 간격: {self.check_interval}초")
        logger.info(f"   - 감지 방식: dumpsys window windows")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        logger.info(f"🔍 포그라운드 모니터링 중지 시작: {self.package_name}")
        
        # 1. 모니터링 플래그 비활성화
        self.monitoring = False
        
        # 2. 모니터링 스레드 정리
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.info("모니터링 스레드 종료 대기 중...")
            self.monitor_thread.join(timeout=5)  # 5초 대기
            
            if self.monitor_thread.is_alive():
                logger.warning("모니터링 스레드가 정상적으로 종료되지 않음")
            else:
                logger.info("✅ 모니터링 스레드 정상 종료됨")
        
        # 3. 스레드 참조 해제
        self.monitor_thread = None
        
        logger.info(f"🔍 앱 포그라운드 모니터링 완전 중지됨: {self.package_name}")
        logger.info(f"   - 총 복구 횟수: {self.recovery_count}")
        logger.info(f"   - 최종 모니터링 상태: {self.monitoring}")
    
    def _monitor_loop(self):
        """모니터링 메인 루프"""
        try:
            logger.info(f"모니터링 루프 시작: {self.package_name}")
            loop_count = 0
            
            while self.monitoring:
                loop_count += 1
                
                # 주기적으로 모니터링 상태 확인
                if loop_count % 30 == 0:  # 30회마다 (약 1분)
                    logger.debug(f"모니터링 상태 체크 - 루프 {loop_count}회, 복구 {self.recovery_count}회")
                
                try:
                    if self._is_app_in_background():
                        self._recover_to_foreground()
                except Exception as check_error:
                    logger.warning(f"백그라운드 체크 오류: {check_error}")
                
                # monitoring 플래그를 다시 확인하여 즉시 종료 가능하도록
                if not self.monitoring:
                    break
                    
                time.sleep(self.check_interval)
                
        except Exception as e:
            logger.error(f"모니터링 루프 오류: {e}")
        finally:
            self.monitoring = False
            logger.info(f"모니터링 루프 종료: {self.package_name}")
    
    
    def _is_app_in_background(self) -> bool:
        """앱이 백그라운드에 있는지 확인 - 더 보수적인 접근"""
        try:
            # 1단계: 현재 포커스된 앱 확인
            current_focus = self._get_current_focused_app()
            
            # 우리 앱이 포커스되어 있으면 포그라운드
            if current_focus and self.package_name in current_focus:
                self.last_foreground_check = time.time()
                return False
            
            # 2단계: 최근에 포그라운드였다면 잠시 대기 (일시적 전환 무시)
            current_time = time.time()
            if current_time - self.last_foreground_check < 3.0:
                return False  # 3초 이내라면 백그라운드로 판단하지 않음
            
            # 3단계: 프로세스가 실행 중인지 확인
            if not self._is_app_process_running():
                return True  # 프로세스가 없으면 백그라운드
            
            # 4단계: 실제 백그라운드인지 최종 확인
            return self._detailed_background_check()
                
        except Exception as e:
            logger.error(f"앱 상태 확인 오류: {e}")
            return False  # 오류 시 백그라운드로 판단하지 않음
    
    def _get_current_focused_app(self) -> str:
        """현재 포커스된 앱 패키지명 반환"""
        try:
            cmd = [
                self.adb_path, 'shell', 
                'dumpsys', 'window', 'windows', '|', 'grep', '-E', 'mCurrentFocus|mFocusedApp'
            ]
            
            # Windows에서는 파이프 사용 시 shell=True 필요
            result = run_hidden_subprocess(
                ' '.join(cmd),
                shell=True,
                capture_output=True, 
                text=True, 
                timeout=3
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return ""
                
        except Exception as e:
            logger.debug(f"포커스 앱 확인 오류: {e}")
            return ""
    
    def _is_app_process_running(self) -> bool:
        """앱 프로세스가 실행 중인지 확인"""
        try:
            cmd = [
                self.adb_path, 'shell', 
                'ps', '|', 'grep', self.package_name
            ]
            
            result = run_hidden_subprocess(
                ' '.join(cmd),
                shell=True,
                capture_output=True, 
                text=True, 
                timeout=3
            )
            
            return result.returncode == 0 and self.package_name in result.stdout
                
        except Exception as e:
            logger.debug(f"프로세스 확인 오류: {e}")
            return True  # 오류 시 실행 중으로 가정
    
    def _detailed_background_check(self) -> bool:
        """상세한 백그라운드 상태 확인"""
        try:
            # dumpsys activity로 앱 상태 확인
            cmd = [
                self.adb_path, 'shell', 
                'dumpsys', 'activity', 'activities', '|', 'grep', '-A5', '-B5', self.package_name
            ]
            
            result = run_hidden_subprocess(
                ' '.join(cmd),
                shell=True,
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # 확실히 포그라운드 상태를 나타내는 키워드들
                foreground_indicators = [
                    'mresumedactivity',
                    'mfocusedactivity', 
                    'visible=true',
                    'state=resumed'
                ]
                
                for indicator in foreground_indicators:
                    if indicator in output and self.package_name in output:
                        return False  # 포그라운드에 있음
                
                # 확실히 백그라운드 상태를 나타내는 키워드들
                background_indicators = [
                    'state=paused',
                    'state=stopped',
                    'visible=false'
                ]
                
                for indicator in background_indicators:
                    if indicator in output and self.package_name in output:
                        return True  # 백그라운드에 있음
            
            # 판단할 수 없으면 백그라운드로 가정하지 않음
            return False
                
        except Exception as e:
            logger.debug(f"상세 백그라운드 체크 오류: {e}")
            return False
    
    def _recover_to_foreground(self):
        """앱을 포그라운드로 복구"""
        try:
            current_time = time.time()
            
            # 너무 빈번한 복구 방지 (5초 이내 중복 방지)
            if current_time - self.last_recovery_time < 5.0:
                return
            
            # 복구 전 한 번 더 확인 (false positive 방지)
            if not self._detailed_background_check():
                logger.debug("복구 직전 재확인: 실제로는 포그라운드에 있음")
                return
            
            logger.warning(f"🚨 앱 백그라운드 감지! 포그라운드로 복구 중: {self.package_name}")
            
            # 1. 먼저 현재 활동 확인
            current_activity = self._get_current_activity()
            
            # 2. 앱을 포그라운드로 가져오기
            recovery_success = self._bring_app_to_foreground()
            
            if recovery_success:
                self.recovery_count += 1
                self.last_recovery_time = current_time
                self.last_foreground_check = current_time  # 복구 후 포그라운드 시간 업데이트
                
                logger.info(f"✅ 포그라운드 복구 성공 (총 {self.recovery_count}회)")
                logger.info(f"   - 이전 활동: {current_activity}")
                
                # 콜백 호출
                if self.recovery_callback:
                    self.recovery_callback(f"백그라운드에서 복구됨 (#{self.recovery_count})")
            else:
                logger.error("❌ 포그라운드 복구 실패")
                
        except Exception as e:
            logger.error(f"포그라운드 복구 중 오류: {e}")
    
    def _get_current_activity(self) -> str:
        """현재 활성 액티비티 확인"""
        try:
            cmd = [
                self.adb_path, 'shell',
                'dumpsys', 'activity', 'activities'
            ]
            
            result = run_hidden_subprocess(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=3
            )
            
            if result.returncode == 0:
                # 최상위 액티비티 찾기
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'mResumedActivity' in line or 'mFocusedActivity' in line:
                        return line.strip()
                        
                return "Unknown Activity"
            else:
                return "Activity Check Failed"
                
        except Exception as e:
            return f"Error: {e}"
    
    def _bring_app_to_foreground(self) -> bool:
        """앱을 포그라운드로 가져오기"""
        try:
            # 방법 1: monkey 명령으로 홈키 후 앱 실행
            commands = [
                # 홈 화면으로 이동
                [self.adb_path, 'shell', 'input', 'keyevent', 'KEYCODE_HOME'],
                # 잠시 대기
                ['timeout', '0.2'],  # Windows에서는 timeout 명령 사용
                # 앱 실행
                [self.adb_path, 'shell', 'monkey', '-p', self.package_name, '-c', 'android.intent.category.LAUNCHER', '1']
            ]
            
            for i, cmd in enumerate(commands):
                if cmd[0] == 'timeout':
                    time.sleep(0.2)
                    continue
                
                result = run_hidden_subprocess(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode != 0:
                    logger.warning(f"복구 명령 {i+1} 실패: {result.stderr}")
                    
                    # 대안 방법: am start 사용
                    if i == len(commands) - 1:  # 마지막 명령이 실패한 경우
                        alt_cmd = [
                            self.adb_path, 'shell', 'am', 'start', 
                            '-n', f'{self.package_name}/.MainActivity'  # 기본 액티비티 가정
                        ]
                        
                        alt_result = run_hidden_subprocess(
                            alt_cmd, 
                            capture_output=True, 
                            text=True, 
                            timeout=5
                        )
                        
                        if alt_result.returncode == 0:
                            logger.info("대안 방법으로 앱 실행 성공")
                            return True
            
            # 복구 후 잠시 대기하여 앱이 완전히 로드되도록 함
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"앱 포그라운드 복구 실패: {e}")
            return False
    
    def get_status(self) -> dict:
        """현재 모니터링 상태 반환"""
        return {
            'monitoring': self.monitoring,
            'package_name': self.package_name,
            'check_interval': self.check_interval,
            'recovery_count': self.recovery_count,
            'last_recovery_time': self.last_recovery_time,
            'last_foreground_check': self.last_foreground_check
        }
    
    def force_check(self) -> dict:
        """수동으로 앱 상태 확인"""
        is_background = self._is_app_in_background()
        current_activity = self._get_current_activity()
        
        result = {
            'is_background': is_background,
            'current_activity': current_activity,
            'package_name': self.package_name,
            'timestamp': time.time()
        }
        
        logger.info(f"🔍 수동 상태 확인 결과:")
        logger.info(f"   - 백그라운드 상태: {is_background}")
        logger.info(f"   - 현재 액티비티: {current_activity}")
        
        return result
