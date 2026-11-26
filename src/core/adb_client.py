#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB 클라이언트 래퍼 - CMD 팝업 방지 버전
"""
import os
import subprocess
import time
from typing import List, Optional, Tuple
from src.config import ADB_PATH, DEFAULT_TIMEOUT
from src.utils.logger import setup_logger
from src.utils.subprocess_utils import run_hidden_subprocess

logger = setup_logger(__name__)

class AdbClient:
    """ADB 명령어 실행을 위한 클라이언트"""
    
    def __init__(self, device_serial: Optional[str] = None):
        self.device_serial = device_serial
        
        # EXE 모드에서 ADB 경로 디버깅
        import sys
        if getattr(sys, 'frozen', False):
            logger.info(f"[EXE모드] ADB 경로: {ADB_PATH}")
            logger.info(f"[EXE모드] ADB 파일 존재 여부: {os.path.exists(ADB_PATH)}")
            if os.path.exists(ADB_PATH):
                try:
                    # ADB 버전 확인으로 실행 가능성 테스트
                    test_result = run_hidden_subprocess([ADB_PATH, "version"], 
                                                capture_output=True, 
                                                text=True, 
                                                timeout=3)
                    if test_result.returncode == 0:
                        logger.info(f"[EXE모드] ADB 실행 테스트 성공")
                    else:
                        logger.warning(f"[EXE모드] ADB 실행 테스트 실패: {test_result.stderr}")
                except Exception as e:
                    logger.warning(f"[EXE모드] ADB 실행 테스트 오류: {e}")
    

    
    def run_command(self, command: str, shell: bool = True, timeout: int = DEFAULT_TIMEOUT) -> str:
        """ADB 명령어 실행 (CMD 팝업 방지)"""
        if self.device_serial:
            full_command = f'"{ADB_PATH}" -s {self.device_serial} {command}'
        else:
            full_command = f'"{ADB_PATH}" {command}'
        
        logger.debug(f"ADB 명령어 실행: {full_command}")
        
        try:
            # shell 명령어에 파이프가 포함된 경우 특별 처리 (Windows 호환)
            if 'shell "' in command and '|' in command:
                # 이미 따옴표로 감싸진 shell 명령어는 그대로 처리
                result = run_hidden_subprocess(
                    full_command,
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='ignore'
                )
            else:
                # 일반 명령어 처리
                result = run_hidden_subprocess(
                    full_command,
                    capture_output=True,
                    text=True,
                    shell=shell,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='ignore'
                )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"ADB 명령어 실행 실패: {full_command}")
                logger.warning(f"오류 출력: {result.stderr}")
                return f"Error: {result.stderr.strip()}"
                
        except subprocess.TimeoutExpired:
            logger.error(f"ADB 명령어 시간 초과: {full_command}")
            return "Error: Timeout"
        except Exception as e:
            logger.error(f"ADB 명령어 실행 중 오류: {e}")
            return f"Error: {e}"
    
    def get_connected_devices(self) -> List[str]:
        """연결된 디바이스 목록 반환"""
        result = self.run_command("devices")
        if result.startswith("Error:"):
            return []
        
        devices = []
        lines = result.split('\n')[1:]  # 첫 번째 라인은 헤더
        for line in lines:
            if line.strip() and '\tdevice' in line:
                device_id = line.split('\t')[0]
                devices.append(device_id)
        
        return devices
    
    def reboot_device(self) -> bool:
        """디바이스 재부팅"""
        result = self.run_command("reboot")
        if result.startswith("Error:"):
            logger.error(f"디바이스 재부팅 실패: {result}")
            return False
        logger.info("디바이스 재부팅 명령 전송 완료")
        return True
    
    def connect(self) -> bool:
        """장치에 연결되어 있는지 확인"""
        try:
            devices = self.get_connected_devices()
            if devices:
                if not self.device_serial:
                    # 첫 번째 장치를 사용
                    self.device_serial = devices[0]
                logger.info(f"ADB 장치 연결 확인: {self.device_serial}")
                return True
            else:
                logger.warning("연결된 ADB 장치가 없습니다")
                return False
        except Exception as e:
            logger.error(f"ADB 연결 확인 중 오류: {e}")
            return False
    
    def get_installed_packages(self) -> List[str]:
        """설치된 패키지 목록 반환 (최적화됨, 타임아웃 적용, --user 0 fallback 포함)"""
        logger.debug(f"📱 패키지 목록 조회 시작 (디바이스: {self.device_serial})")
        
        # 패키지 조회용 짧은 타임아웃 (15초)
        package_timeout = 15
        max_retries = 2
        
        # 시도할 명령어들 (config에서 정의된 보안 수준별 fallback)
        from src.config import PACKAGE_LIST_COMMANDS
        commands_to_try = PACKAGE_LIST_COMMANDS
        
        result = None
        successful_command = None
        
        for cmd_index, command in enumerate(commands_to_try):
            logger.debug(f"명령어 시도 {cmd_index + 1}/{len(commands_to_try)}: {command}")
            
            for attempt in range(max_retries):
                try:
                    logger.debug(f"패키지 조회 시도 {attempt + 1}/{max_retries} (명령어: {command})")
                    
                    result = self.run_command(command, timeout=package_timeout)
                    if result.startswith("Error:"):
                        if attempt < max_retries - 1:
                            logger.warning(f"패키지 조회 실패 (시도 {attempt + 1}), 재시도...")
                            time.sleep(2)
                            continue
                        logger.warning(f"명령어 '{command}' 실패: {result}")
                        break  # 다음 명령어 시도
                    
                    # 성공한 경우
                    successful_command = command
                    if cmd_index > 0:  # fallback 명령어를 사용한 경우
                        logger.info(f"🔒 보안 강화 단말 감지: fallback 명령어 '{command}' 사용")
                    else:
                        logger.info(f"✅ 표준 패키지 조회 성공 (명령어: {command})")
                    break
                    
                except subprocess.TimeoutExpired:
                    if attempt < max_retries - 1:
                        logger.warning(f"패키지 조회 타임아웃 (시도 {attempt + 1}), 재시도...")
                        time.sleep(2)
                        continue
                    logger.warning(f"명령어 '{command}' 타임아웃 ({package_timeout}초 초과)")
                    break  # 다음 명령어 시도
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"패키지 조회 오류 (시도 {attempt + 1}): {e}, 재시도...")
                        time.sleep(2)
                        continue
                    logger.warning(f"명령어 '{command}' 오류: {e}")
                    break  # 다음 명령어 시도
            
            # 성공한 경우 루프 종료
            if successful_command:
                break
        
        # 모든 명령어가 실패한 경우
        if not successful_command or not result:
            logger.error("❌ 모든 패키지 조회 명령어 실패")
            return []
        
        packages = []
        # LG U+ AI 콜 에이전트 화이트리스트
        whitelisted_system_apps = ['com.lguplus.aicallagent']
        
        for line in result.split('\n'):
            if line.startswith('package:'):
                package_name = line.replace('package:', '').strip()
                
                # 화이트리스트에 있는 시스템 앱은 항상 포함
                if package_name in whitelisted_system_apps:
                    packages.append(package_name)
                    logger.info(f"화이트리스트 시스템 앱 추가: {package_name}")
                # 기본적인 필터링 (Google, Samsung 시스템 앱 등 제외)
                elif not any(skip in package_name for skip in [
                    'com.google.android', 'com.android', 'com.samsung.android',
                    'com.sec.android', 'com.qualcomm', 'com.mediatek'
                ]):
                    packages.append(package_name)
        
        # 성공한 명령어 정보와 함께 로그 출력
        command_info = ""
        if successful_command == "shell pm list packages --user 0":
            command_info = " (보안 강화 단말용 --user 0 옵션 사용)"
        elif successful_command == "shell pm list packages -3":
            command_info = " (서드파티 앱 전용 -3 옵션 사용)"
        elif successful_command == "shell pm list packages -u":
            command_info = " (비활성화 앱 포함 -u 옵션 사용)"
        elif successful_command == "shell pm list packages --user current":
            command_info = " (현재 사용자 전용 --user current 옵션 사용)"
        elif successful_command != "shell pm list packages":
            command_info = f" (fallback 명령어 사용: {successful_command})"
        
        logger.info(f"✅ 패키지 목록 조회 완료: {len(packages)}개 발견{command_info}")
        return sorted(packages)
    
    def force_stop_app(self, package_name: str) -> bool:
        """앱 강제 종료"""
        result = self.run_command(f"shell am force-stop {package_name}")
        return not result.startswith("Error:")
    
    def launch_app(self, package_name: str) -> bool:
        """앱 실행"""
        launch_cmd = f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        result = self.run_command(launch_cmd)
        
        if result.startswith("Error:"):
            logger.warning(f"앱 실행 실패: {result}")
            return False
        
        logger.info(f"앱 실행 성공: {package_name}")
        return True
    
    @property
    def adb_path(self) -> str:
        """ADB 실행 파일 경로 반환"""
        return ADB_PATH
    
    def set_device_serial(self, serial: str):
        """디바이스 시리얼 설정"""
        self.device_serial = serial
        logger.info(f"디바이스 시리얼 설정: {serial}")
    
    def run_adb_command(self, command, shell=False):
        """ADB 명령어를 실행하고 결과를 반환합니다. (원본 test.py 호환, CMD 팝업 방지)"""
        logger.info(f"ADB 명령어 실행 시작: {command}, shell={shell}")
        try:
            if shell:
                # adb shell 명령어는 하나의 문자열로 전달
                full_command = f'"{ADB_PATH}" shell {command}'
                logger.debug(f"Shell 명령어: {full_command}")
                # PowerShell 호환성을 위해 다양한 인코딩 시도
                result = None
                for encoding in ['utf-8', 'cp949', 'latin-1']:
                    try:
                        result = run_hidden_subprocess(full_command, capture_output=True, text=True, check=True, 
                                              encoding=encoding, shell=True)
                        break
                    except UnicodeDecodeError:
                        logger.debug(f"인코딩 {encoding} 실패, 다음 인코딩 시도")
                        continue
                
                if result is None:
                    # 모든 인코딩 실패 시 bytes로 처리 후 강제 디코딩
                    result = run_hidden_subprocess(full_command, capture_output=True, check=True, shell=True)
                    output = result.stdout.decode('utf-8', errors='ignore').strip()
                else:
                    output = result.stdout.strip()
            else:
                # 일반 adb 명령어는 리스트로 전달
                if self.device_serial:
                    command_list = [ADB_PATH, "-s", self.device_serial] + command.split()
                else:
                    command_list = [ADB_PATH] + command.split()
                logger.debug(f"명령어 리스트: {command_list}")
                result = run_hidden_subprocess(command_list, capture_output=True, text=True, check=True, encoding='utf-8')
                output = result.stdout.strip()
            
            logger.debug(f"ADB 명령어 성공: {len(output)} 문자 반환")
            return output
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ADB 명령어 실행 실패: {command}")
            logger.error(f"에러 코드: {e.returncode}")
            logger.error(f"에러 출력: {e.stderr}")
            return f"Error: {e.stderr if e.stderr else '명령어 실행 실패'}"
        except subprocess.TimeoutExpired:
            logger.error(f"ADB 명령어 시간 초과: {command}")
            return "Error: 시간 초과"
        except Exception as e:
            logger.error(f"ADB 명령어 실행 중 예외 발생: {e}")
            return f"Error: {str(e)}"
    
    def restart_app(self, package_name: str) -> bool:
        """앱 재시작 (원본 test.py 로직)"""
        try:
            logger.info(f"앱 재시작 시작: {package_name}")
            
            # 1. 앱 강제 종료
            kill_result = self.run_command(f"shell am force-stop {package_name}")
            if kill_result and kill_result.startswith("Error:"):
                logger.warning(f"앱 강제 종료 실패: {kill_result}")
            else:
                logger.info(f"앱 강제 종료 성공: {package_name}")
            
            time.sleep(1)
            
            # 2. 앱 시작
            start_result = self.run_command(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
            if start_result and start_result.startswith("Error:"):
                logger.warning(f"앱 시작 실패: {start_result}")
                return False
            else:
                logger.info(f"앱 시작 성공: {package_name}")
                return True
                
        except Exception as e:
            logger.error(f"앱 재시작 중 오류: {e}")
            return False
    
    def get_memory_info(self, package_name: str) -> Optional[float]:
        """메모리 사용량 반환 (MB) - 개선된 파싱"""
        try:
            result = self.run_command(f"shell dumpsys meminfo {package_name}")
            if result.startswith("Error:"):
                logger.debug(f"메모리 정보 조회 실패: {result}")
                return None
            
            # 여러 패턴으로 메모리 정보 추출
            import re
            
            # TOTAL PSS 패턴들 (더 많은 패턴 추가)
            patterns = [
                r'TOTAL PSS:\s*(\d+)KB',
                r'TOTAL\s+(\d+)\s+(\d+)\s+(\d+)',  # PSS, Private, Shared 순서
                r'Total PSS:\s*(\d+)',
                r'TOTAL.*?(\d+)\s*KB',
                r'App Summary\s*\n.*?TOTAL\s+(\d+)',  # App Summary 섹션
                r'Pss\s+Total\s+(\d+)',
                r'TOTAL\s+(\d+)\s+KB',
                # 새로운 패턴들 추가
                r'TOTAL\s+(\d+)',  # 단순 TOTAL 숫자
                r'Activities\s*\n.*?TOTAL\s+(\d+)',  # Activities 섹션
                r'App Summary\s*\n.*?Pss\s+Total\s+(\d+)',
                r'Native Heap\s+(\d+)',  # Native Heap 정보
                r'Dalvik Heap\s+(\d+)',  # Dalvik Heap 정보
            ]
            
            logger.debug(f"메모리 정보 원본 데이터: {result[:500]}...")  # 디버깅용
            
            for pattern in patterns:
                matches = re.findall(pattern, result, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    try:
                        if isinstance(match, tuple):
                            # 첫 번째 값이 PSS
                            mem_kb = int(match[0])
                        else:
                            mem_kb = int(match)
                        
                        if mem_kb > 0:  # 유효한 값인지 확인
                            mem_mb = mem_kb / 1024  # MB로 변환
                            logger.debug(f"메모리 사용량 추출 성공: {mem_mb:.1f}MB (원본: {mem_kb}KB)")
                            return mem_mb
                    except (ValueError, IndexError) as e:
                        logger.debug(f"메모리 값 파싱 실패: {match}, 오류: {e}")
                        continue
            
            # 패턴 매칭 실패 시 대안 방법 시도 - 라인별 파싱
            lines = result.split('\n')
            for line in lines:
                line = line.strip()
                # "TOTAL" 라인에서 숫자 추출
                if 'TOTAL' in line.upper():
                    numbers = re.findall(r'(\d+)', line)
                    if numbers:
                        try:
                            mem_kb = int(numbers[0])
                            if mem_kb > 100:  # 100KB 이상인 경우만 유효하다고 판단
                                mem_mb = mem_kb / 1024
                                logger.debug(f"라인별 파싱으로 메모리 추출: {mem_mb:.1f}MB (라인: {line})")
                                return mem_mb
                        except ValueError:
                            continue
            
            # 패턴 매칭 실패 시 대안 방법 시도
            logger.warning(f"메모리 정보 패턴 매칭 실패 - 패키지: {package_name}")
            logger.debug(f"전체 meminfo 출력: {result}")
            return 0.0
            
        except Exception as e:
            logger.debug(f"메모리 정보 조회 오류: {e}")
            return 0.0
    
    def get_main_process_pid(self, package_name: str) -> Optional[int]:
        """패키지의 메인 프로세스 PID 반환 (Windows 환경 최적화 - ps 명령어만 사용)"""
        try:
            # Windows 환경에서는 ps 명령어만 사용 (가장 안정적)
            pid = self._get_pid_via_ps(package_name)
            if pid:
                return pid
            
            logger.warning(f"PID를 찾을 수 없음: {package_name}")
            return None
            
        except Exception as e:
            logger.error(f"PID 조회 중 오류: {e}")
            return None
    
    def _get_pid_via_ps(self, package_name: str) -> Optional[int]:
        """ps 명령어를 통한 PID 조회 (Windows 환경 최적화 - 단순 ps 명령어, CMD 팝업 방지)"""
        try:
            logger.debug(f"PS 명령어로 PID 조회 시작: {package_name}")
            
            # Windows에서 안전한 단순 ps 명령어 사용 (CMD 팝업 방지)
            result = self.run_command('shell ps', timeout=8)
            
            if result.startswith("Error:") or not result.strip():
                logger.debug("PS 명령어 실패 또는 빈 결과")
                return None
            
            # Python에서 패키지명으로 필터링
            lines = result.strip().split('\n')
            filtered_lines = []
            
            for line in lines:
                if package_name in line and not line.strip().startswith('PID'):
                    filtered_lines.append(line)
            
            if not filtered_lines:
                logger.debug(f"패키지 '{package_name}'에 해당하는 프로세스 없음")
                return None
            
            # 첫 번째 매칭된 프로세스에서 PID 추출
            first_line = filtered_lines[0].strip()
            logger.debug(f"메인 프로세스 라인: {first_line}")
            
            # PID는 보통 두 번째 컬럼에 위치
            # 예: u0_a242      11509  1095 21838128 259956 0 0 S com.uplus.onphone
            parts = first_line.split()
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    logger.info(f"메인 프로세스 PID: {pid} (패키지: {package_name}, 방법: ps)")
                    
                    # 추가 프로세스가 있는 경우 로그에 기록
                    if len(filtered_lines) > 1:
                        logger.info(f"추가 프로세스 감지: {len(filtered_lines)-1}개")
                        for idx, line in enumerate(filtered_lines[1:], 2):
                            logger.debug(f"  프로세스 {idx}: {line.strip()}")
                    
                    return pid
                except ValueError as ve:
                    logger.debug(f"PID 파싱 실패: {parts[1]}, 오류: {ve}")
                    return None
            else:
                logger.debug(f"PS 출력 파싱 실패: 컬럼 수 부족 ({len(parts)})")
                return None
                        
        except Exception as e:
            logger.debug(f"ps 방법 실패: {e}")
            return None
    
    def _get_pid_via_pidof(self, package_name: str) -> Optional[int]:
        """pidof 명령어를 통한 PID 조회 (Windows 환경에서는 스킵)"""
        try:
            # Windows 환경에서는 pidof가 안정적이지 않으므로 건너뛰기
            logger.debug(f"pidof 방법 스킵 (Windows 환경): {package_name}")
            return None
            
        except Exception as e:
            logger.debug(f"pidof 방법 실패: {e}")
            return None
    
    def _get_pid_via_proc_scan(self, package_name: str) -> Optional[int]:
        """/proc 파일시스템 스캔을 통한 PID 조회 (Windows 환경에서는 스킵)"""
        try:
            # Windows 환경에서는 pgrep이 안정적이지 않으므로 건너뛰기
            logger.debug(f"pgrep 방법 스킵 (Windows 환경): {package_name}")
            return None
            
        except Exception as e:
            logger.debug(f"pgrep 방법 실패: {e}")
            return None

    def get_cpu_usage(self, package_name: str) -> Optional[float]:
        """CPU 사용률 반환 (%) - PID 기반 정확한 방식"""
        try:
            # 1. 메인 프로세스 PID 조회
            pid = self.get_main_process_pid(package_name)
            if not pid:
                logger.warning(f"PID를 찾을 수 없음: {package_name}")
                return None
            
            # 2. 해당 PID의 CPU 사용량 조회
            top_cmd = f"shell top -n 1 -p {pid}"
            result = self.run_command(top_cmd, timeout=10)
            
            if result.startswith("Error:"):
                logger.warning(f"top 명령어 실패: {result}")
                return None
            
            logger.debug(f"top 출력:\n{result}")
            
            # 3. CPU 사용률 파싱
            # 예상 출력:
            #   PID USER         PR  NI VIRT  RES  SHR S[%CPU] %MEM     TIME+ ARGS
            # 28433 u0_a242      10 -10  21G 333M 218M S 25.0   9.1   1:50.30 com.uplus.onpho+
            
            lines = result.strip().split('\n')
            for line in lines:
                # PID가 포함된 줄 찾기 (헤더 제외)
                if str(pid) in line and not line.strip().startswith('PID'):
                    logger.debug(f"CPU 분석 대상 라인: {line}")
                    
                    # 정규표현식으로 S 다음의 CPU 값 찾기
                    import re
                    
                    # 패턴 1: S 25.0 형태
                    pattern1 = r'S\s+(\d+(?:\.\d+)?)'
                    match1 = re.search(pattern1, line)
                    
                    if match1:
                        cpu_usage = float(match1.group(1))
                        logger.info(f"CPU 사용률: {cpu_usage}% (PID: {pid}, 패키지: {package_name})")
                        return cpu_usage
                    
                    # 패턴 2: S[25.0] 형태 또는 S25.0 형태
                    pattern2 = r'S\[?(\d+(?:\.\d+)?)\]?'
                    match2 = re.search(pattern2, line)
                    
                    if match2:
                        cpu_usage = float(match2.group(1))
                        logger.info(f"CPU 사용률 (패턴2): {cpu_usage}% (PID: {pid}, 패키지: {package_name})")
                        return cpu_usage
                    
                    # 백업 방식: 컬럼 기반 파싱
                    parts = line.split()
                    if len(parts) >= 9:
                        # S[%CPU] 컬럼은 보통 8번째 위치
                        try:
                            # 8번째 컬럼에서 S 제거하고 숫자만 추출
                            cpu_column = parts[8]
                            if 'S' in cpu_column:
                                cpu_str = cpu_column.replace('S', '').replace('[', '').replace(']', '')
                                if cpu_str:
                                    cpu_usage = float(cpu_str)
                                    if 0 <= cpu_usage <= 100:
                                        logger.info(f"CPU 사용률 (백업): {cpu_usage}% (PID: {pid})")
                                        return cpu_usage
                        except (ValueError, IndexError):
                            pass
                        
                        # 9번째 컬럼도 시도
                        if len(parts) >= 10:
                            try:
                                cpu_usage = float(parts[9])
                                if 0 <= cpu_usage <= 100:
                                    logger.info(f"CPU 사용률 (9번째): {cpu_usage}% (PID: {pid})")
                                    return cpu_usage
                            except ValueError:
                                pass
                    
                    logger.warning(f"CPU 사용률 파싱 실패: {line}")
                    return 0.0
            
            logger.warning(f"PID {pid}에 대한 CPU 정보를 찾을 수 없음")
            return 0.0
            
        except Exception as e:
            logger.error(f"CPU 사용률 조회 중 오류: {e}")
            return None
    
    def check_wireless_connection(self) -> Tuple[bool, str]:
        """무선 연결 상태 확인"""
        devices = self.get_connected_devices()
        for device in devices:
            if ':' in device:  # IP:PORT 형태는 무선 연결
                return True, device
        return False, ""

    def get_connection_mode(self) -> str:
        """현재 연결 방식 반환 (USB 또는 무선)"""
        try:
            is_wireless, wireless_device = self.check_wireless_connection()
            if is_wireless:
                return f"무선 ({wireless_device})"
            else:
                return "USB"
        except Exception:
            return "알 수 없음"
    
    def enable_wireless_debugging(self, port: int = 5555) -> bool:
        """무선 디버깅 활성화"""
        result = self.run_command(f"tcpip {port}")
        return not result.startswith("Error:")
    
    def connect_wireless(self, ip: str, port: int = 5555) -> bool:
        """무선 연결"""
        result = self.run_command(f"connect {ip}:{port}")
        return "connected" in result.lower()
    
    def disconnect_wireless(self, ip: str, port: int = 5555) -> bool:
        """무선 연결 해제"""
        result = self.run_command(f"disconnect {ip}:{port}")
        return not result.startswith("Error:")
    
    def get_app_version_info(self, package_name: str) -> dict:
        """앱의 버전 정보 조회 (버전코드, 버전네임)"""
        try:
            # dumpsys 명령으로 패키지 정보 조회
            result = self.run_command(f"shell dumpsys package {package_name}")
            
            if result.startswith("Error:"):
                logger.warning(f"패키지 정보 조회 실패: {package_name}")
                return {"version_code": "알 수 없음", "version_name": "알 수 없음"}
            
            version_code = "알 수 없음"
            version_name = "알 수 없음"
            
            # dumpsys 출력에서 버전 정보 추출
            lines = result.split('\n')
            for line in lines:
                line = line.strip()
                
                # versionCode 찾기
                if 'versionCode=' in line:
                    import re
                    # versionCode=123456789 형태에서 숫자 추출
                    match = re.search(r'versionCode=(\d+)', line)
                    if match:
                        version_code = match.group(1)
                        logger.debug(f"버전코드 발견: {version_code}")
                
                # versionName 찾기
                if 'versionName=' in line:
                    import re
                    # versionName=1.2.3 형태에서 버전명 추출
                    match = re.search(r'versionName=([^\s]+)', line)
                    if match:
                        version_name = match.group(1)
                        logger.debug(f"버전네임 발견: {version_name}")
                
                # 둘 다 찾았으면 더 이상 검색하지 않음
                if version_code != "알 수 없음" and version_name != "알 수 없음":
                    break
            
            logger.info(f"앱 버전 정보 - 패키지: {package_name}, 코드: {version_code}, 네임: {version_name}")
            
            return {
                "version_code": version_code,
                "version_name": version_name
            }
            
        except Exception as e:
            logger.error(f"앱 버전 정보 조회 중 오류: {e}")
            return {"version_code": "오류", "version_name": "오류"}
    
    def get_android_version(self) -> str:
        """Android 버전 정보 조회"""
        try:
            result = self.run_command("shell getprop ro.build.version.release")
            if result.startswith("Error:"):
                logger.warning(f"Android 버전 조회 실패: {result}")
                return "알 수 없음"
            
            version = result.strip()
            logger.debug(f"Android 버전: {version}")
            return version
        except Exception as e:
            logger.error(f"Android 버전 조회 중 오류: {e}")
            return "알 수 없음"
    
    def get_device_model(self) -> str:
        """디바이스 모델명 조회"""
        try:
            # 먼저 모델명 시도
            result = self.run_command("shell getprop ro.product.model")
            if not result.startswith("Error:") and result.strip():
                model = result.strip()
                logger.debug(f"디바이스 모델: {model}")
                return model
            
            # 모델명이 없으면 제품명 시도
            result = self.run_command("shell getprop ro.product.name")
            if not result.startswith("Error:") and result.strip():
                name = result.strip()
                logger.debug(f"디바이스 제품명: {name}")
                return name
            
            logger.warning("디바이스 모델/제품명 조회 실패")
            return "알 수 없음"
        except Exception as e:
            logger.error(f"디바이스 모델 조회 중 오류: {e}")
            return "알 수 없음"
    
    def get_device_info(self) -> dict:
        """디바이스 정보 종합 조회"""
        try:
            info = {
                "model": self.get_device_model(),
                "android_version": self.get_android_version(),
                "serial": self.device_serial or "알 수 없음"
            }
            
            # API 레벨도 추가로 조회
            api_result = self.run_command("shell getprop ro.build.version.sdk")
            if not api_result.startswith("Error:") and api_result.strip():
                info["api_level"] = api_result.strip()
            else:
                info["api_level"] = "알 수 없음"
            
            logger.info(f"디바이스 정보 조회 완료: {info}")
            return info
        except Exception as e:
            logger.error(f"디바이스 정보 조회 중 오류: {e}")
            return {
                "model": "알 수 없음",
                "android_version": "알 수 없음", 
                "serial": "알 수 없음",
                "api_level": "알 수 없음"
            }
    
    def get_current_foreground_app(self) -> Optional[str]:
        """현재 포그라운드에 있는 앱의 패키지명 반환 (CMD 팝업 방지)"""
        try:
            # Windows 호환: dumpsys 결과를 받아서 Python에서 필터링
            result = self.run_command("shell dumpsys activity activities", timeout=5)
            
            if result.startswith("Error:") or not result.strip():
                # 백업 방법: dumpsys window 사용
                result = self.run_command("shell dumpsys window windows", timeout=5)
            
            if result.startswith("Error:"):
                logger.debug("포그라운드 앱 조회 실패")
                return None
            
            # Python에서 필터링 수행
            import re
            lines = result.split('\n')
            target_lines = []
            
            # mResumedActivity 또는 mFocusedActivity가 포함된 라인 찾기
            for line in lines:
                if 'mResumedActivity' in line or 'mFocusedActivity' in line:
                    target_lines.append(line)
            
            # 백업 패턴도 확인
            if not target_lines:
                for line in lines:
                    if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                        target_lines.append(line)
            
            if not target_lines:
                logger.debug("포그라운드 앱 패턴을 찾을 수 없음")
                return None
            
            # 패키지명 추출
            # 여러 패턴으로 패키지명 추출 시도
            patterns = [
                r'([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+',  # 패키지명/액티비티명 패턴
                r'u0\s+([a-zA-Z0-9_.]+)',  # u0 다음 패키지명
                r'pid=\d+\s+([a-zA-Z0-9_.]+)'  # pid 다음 패키지명
            ]
            
            for target_line in target_lines:
                for pattern in patterns:
                    matches = re.findall(pattern, target_line)
                    for match in matches:
                        if '.' in match and not match.startswith('android'):  # 유효한 패키지명인지 확인
                            logger.debug(f"포그라운드 앱 감지: {match}")
                            return match
            
            logger.debug(f"패키지명 추출 실패: {target_lines}")
            return None
            
        except Exception as e:
            logger.debug(f"포그라운드 앱 조회 중 오류: {e}")
            return None
    
    def is_app_in_foreground(self, package_name: str) -> bool:
        """지정된 앱이 포그라운드에 있는지 확인"""
        try:
            current_app = self.get_current_foreground_app()
            is_foreground = current_app == package_name
            
            if not is_foreground:
                logger.debug(f"앱이 백그라운드로 이동: {package_name} (현재: {current_app})")
            
            return is_foreground
            
        except Exception as e:
            logger.debug(f"앱 포그라운드 상태 확인 중 오류: {e}")
            return False
    
    def bring_app_to_foreground(self, package_name: str) -> bool:
        """앱을 포그라운드로 가져오기 (앱 스위칭 시뮬레이션)"""
        try:
            logger.info(f"앱을 포그라운드로 복원: {package_name}")
            
            # 방법 1: am start로 앱의 메인 액티비티 실행
            result = self.run_command(f"shell am start -n {package_name}/.MainActivity")
            if not result.startswith("Error:"):
                logger.info(f"메인 액티비티로 앱 복원 성공: {package_name}")
                return True
            
            # 방법 2: monkey 명령으로 앱 실행
            result = self.run_command(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
            if not result.startswith("Error:"):
                logger.info(f"Monkey로 앱 복원 성공: {package_name}")
                return True
            
            # 방법 3: am start로 런처 카테고리 실행
            result = self.run_command(f"shell am start -c android.intent.category.LAUNCHER -a android.intent.action.MAIN -p {package_name}")
            if not result.startswith("Error:"):
                logger.info(f"런처 카테고리로 앱 복원 성공: {package_name}")
                return True
            
            logger.warning(f"앱을 포그라운드로 복원 실패: {package_name}")
            return False
            
        except Exception as e:
            logger.error(f"앱 포그라운드 복원 중 오류: {e}")
            return False
    
    def monitor_app_focus(self, package_name: str, restore_if_lost: bool = True) -> bool:
        """앱 포커스 모니터링 및 자동 복원"""
        try:
            is_focused = self.is_app_in_foreground(package_name)
            
            if not is_focused and restore_if_lost:
                logger.warning(f"앱이 포커스를 잃음 - 자동 복원 시도: {package_name}")
                success = self.bring_app_to_foreground(package_name)
                if success:
                    # 복원 후 잠시 대기
                    time.sleep(2)
                    # 복원 확인
                    return self.is_app_in_foreground(package_name)
                return False
            
            return is_focused
            
        except Exception as e:
            logger.error(f"앱 포커스 모니터링 중 오류: {e}")
            return False
    
    def press_recent_apps_key(self) -> bool:
        """최근 앱 키 누르기 (앱 스위처 열기)"""
        try:
            result = self.run_command("shell input keyevent KEYCODE_APP_SWITCH")
            return not result.startswith("Error:")
        except Exception as e:
            logger.error(f"최근 앱 키 누르기 실패: {e}")
            return False
    
    def press_home_key(self) -> bool:
        """홈 키 누르기"""
        try:
            result = self.run_command("shell input keyevent KEYCODE_HOME")
            return not result.startswith("Error:")
        except Exception as e:
            logger.error(f"홈 키 누르기 실패: {e}")
            return False
    
    def press_back_key(self) -> bool:
        """뒤로 가기 키 누르기"""
        try:
            result = self.run_command("shell input keyevent KEYCODE_BACK")
            return not result.startswith("Error:")
        except Exception as e:
            logger.error(f"뒤로 가기 키 누르기 실패: {e}")
            return False
    
    def is_app_running(self, package_name: str) -> bool:
        """앱이 실행 중인지 확인"""
        try:
            pid = self.get_main_process_pid(package_name)
            return pid is not None and pid > 0
        except Exception as e:
            logger.error(f"앱 실행 상태 확인 중 오류: {e}")
            return False
    
    def get_app_pid(self, package_name: str) -> Optional[int]:
        """앱의 PID 가져오기 (get_main_process_pid의 별칭)"""
        return self.get_main_process_pid(package_name)
    
    def is_app_in_background(self, package_name: str) -> bool:
        """앱이 백그라운드에 있는지 확인"""
        try:
            # 실행 중이지만 포그라운드에 없으면 백그라운드
            is_running = self.is_app_running(package_name)
            is_foreground = self.is_app_in_foreground(package_name)
            
            return is_running and not is_foreground
            
        except Exception as e:
            logger.error(f"백그라운드 상태 확인 중 오류: {e}")
            return False
    
    def get_current_activity(self) -> str:
        """현재 활성화된 액티비티 가져오기 (CMD 팝업 방지)"""
        try:
            # Python에서 필터링하는 안전한 방식 사용 (get_current_foreground_app과 일관성)
            result = self.run_command('shell dumpsys activity activities', timeout=5)
            
            if not result.startswith("Error:") and result.strip():
                # Python에서 mResumedActivity 라인 찾기
                import re
                lines = result.split('\n')
                for line in lines:
                    if 'mResumedActivity' in line:
                        # mResumedActivity: ActivityRecord{...} package_name/.ActivityName ...
                        match = re.search(r'ActivityRecord\{[^}]*\s+([^/\s]+)/([^/\s]+)', line)
                        if match:
                            package = match.group(1)
                            activity = match.group(2)
                            return f"{package}/{activity}"
            
            # 대안: dumpsys window 사용
            result = self.run_command('shell dumpsys window windows', timeout=5)
            if not result.startswith("Error:") and result.strip():
                import re
                lines = result.split('\n')
                for line in lines:
                    if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                        # Window{...} package_name/activity_name 형태 파싱
                        match = re.search(r'([a-zA-Z0-9_.]+)/([a-zA-Z0-9_.]+)', line)
                        if match:
                            return f"{match.group(1)}/{match.group(2)}"
            
            return ""
            
        except Exception as e:
            logger.debug(f"현재 액티비티 조회 실패: {e}")
            return ""
    
    def check_if_home_screen(self) -> bool:
        """현재 홈 화면에 있는지 확인"""
        try:
            current_activity = self.get_current_activity()
            
            # 홈 화면 관련 패키지/액티비티 패턴
            home_patterns = [
                'com.android.launcher',
                'com.sec.android.app.launcher',  # Samsung
                'com.lge.launcher',              # LG
                'com.miui.home',                 # Xiaomi
                'com.google.android.apps.nexuslauncher',  # Pixel
                'com.huawei.android.launcher',   # Huawei
                '/Launcher',
                '/HomeActivity',
                'launcher3',
                'trebuchet'
            ]
            
            for pattern in home_patterns:
                if pattern.lower() in current_activity.lower():
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"홈 화면 확인 실패: {e}")
            return False
    
    def async_background_monitor(self, package_name: str, check_interval: float = 3.0):
        """비동기 백그라운드 모니터링 (비행기모드 감지와 유사한 방식)"""
        import threading
        
        def monitor_loop():
            consecutive_background_count = 0
            max_background_tolerance = 2  # 2회 연속 백그라운드 감지 시 복귀 시도
            
            while getattr(self, '_monitoring_active', True):
                try:
                    # 홈 화면에 있는지 확인
                    if self.check_if_home_screen():
                        logger.info(f"홈 화면 감지 - 앱 포그라운드 복귀 시도: {package_name}")
                        self.bring_app_to_foreground(package_name)
                        time.sleep(2)  # 복귀 후 대기
                        consecutive_background_count = 0
                        continue
                    
                    # 백그라운드 상태 확인
                    if self.is_app_in_background(package_name):
                        consecutive_background_count += 1
                        logger.info(f"백그라운드 상태 감지 ({consecutive_background_count}/{max_background_tolerance}): {package_name}")
                        
                        if consecutive_background_count >= max_background_tolerance:
                            logger.warning(f"연속 백그라운드 감지 - 포그라운드 복귀 시도: {package_name}")
                            
                            # 포그라운드로 복귀 시도
                            if self.bring_app_to_foreground(package_name):
                                logger.info(f"앱 포그라운드 복귀 성공: {package_name}")
                                consecutive_background_count = 0
                                time.sleep(2)  # 복귀 후 안정화 대기
                            else:
                                logger.warning(f"앱 포그라운드 복귀 실패: {package_name}")
                                time.sleep(1)  # 실패 시 짧은 대기
                    else:
                        # 포그라운드에 있으면 카운터 리셋
                        if consecutive_background_count > 0:
                            logger.info(f"앱이 다시 포그라운드에 있음: {package_name}")
                            consecutive_background_count = 0
                    
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"백그라운드 모니터링 중 오류: {e}")
                    time.sleep(check_interval)
        
        # 모니터링 활성화 플래그 설정
        self._monitoring_active = True
        
        # 백그라운드에서 모니터링 시작
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        logger.info(f"백그라운드 모니터링 시작: {package_name} (간격: {check_interval}초)")
        return monitor_thread
    
    def stop_background_monitor(self):
        """백그라운드 모니터링 중지"""
        if getattr(self, '_monitoring_active', False):
            self._monitoring_active = False
            logger.info("백그라운드 모니터링 중지됨")
        else:
            logger.debug("백그라운드 모니터링이 이미 중지된 상태입니다")