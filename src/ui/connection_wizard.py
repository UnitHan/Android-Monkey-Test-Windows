#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB 연결 마법사 (원본 복원)
"""
import os
import sys
import tkinter as tk
from tkinter import ttk
from src.utils.gui_utils import messagebox
import threading
import time
import subprocess
from typing import TYPE_CHECKING, Optional
from PIL import Image, ImageTk
from src.core.adb_client import AdbClient
from src.utils.subprocess_utils import run_hidden_subprocess, popen_hidden_subprocess
from src.config import ADB_PATH
from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from src.ui.main_app import MonkeyTestApp

logger = setup_logger(__name__)

class ConnectionWizard(tk.Toplevel):
    """ADB 연결 마법사"""
    
    def __init__(self, master: "MonkeyTestApp"):
        logger.info("ConnectionWizard 초기화 시작")
        super().__init__(master)
        self.master: "MonkeyTestApp" = master
        self.title("ADB 연결 마법사")
        
        # 아이콘 설정 - EXE 환경 고려
        try:
            icon_found = False
            
            # EXE 환경에서 아이콘 파일 찾기
            if getattr(sys, 'frozen', False):
                # PyInstaller 환경
                possible_icon_paths = []
                
                if hasattr(sys, '_MEIPASS'):
                    # 임시 디렉토리에서 찾기
                    meipass_path = getattr(sys, '_MEIPASS')
                    possible_icon_paths.extend([
                        os.path.join(meipass_path, "icon.ico"),
                        os.path.join(meipass_path, "icon.png")
                    ])
                
                # 실행 파일과 같은 폴더에서 찾기
                exe_dir = os.path.dirname(sys.executable)
                possible_icon_paths.extend([
                    os.path.join(exe_dir, "icon.ico"),
                    os.path.join(exe_dir, "icon.png")
                ])
            else:
                # 개발 환경
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                possible_icon_paths = [
                    os.path.join(base_dir, "icon.ico"),
                    os.path.join(base_dir, "icon.png")
                ]
            
            # 아이콘 파일 찾기 및 적용
            for icon_path in possible_icon_paths:
                if os.path.exists(icon_path):
                    try:
                        if icon_path.endswith('.ico'):
                            self.iconbitmap(icon_path)
                            logger.info(f"연결 마법사 ICO 아이콘 적용 성공: {icon_path}")
                            icon_found = True
                            break
                        else:
                            # PNG 파일인 경우
                            pil_image = Image.open(icon_path)
                            # 아이콘 크기 조정 (32x32)
                            pil_image = pil_image.resize((32, 32), Image.Resampling.LANCZOS)
                            photo_image = ImageTk.PhotoImage(pil_image)
                            # 타입 체크를 위한 안전한 캐스팅
                            self.iconphoto(True, photo_image)  # type: ignore
                            # 참조 유지를 위해 인스턴스 변수에 저장
                            self._icon_image = photo_image
                            logger.info(f"연결 마법사 PNG 아이콘 적용 성공: {icon_path}")
                            icon_found = True
                            break
                    except Exception as e:
                        logger.warning(f"아이콘 로드 실패 {icon_path}: {e}")
                        continue
            
            if not icon_found:
                logger.warning("연결 마법사 아이콘 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            logger.error(f"연결 마법사 아이콘 설정 실패: {e}")
        
        self.geometry("400x350")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.current_step = 0
        self.steps = []
        self.device_ip = tk.StringVar()
        self.pairing_code = tk.StringVar()
        self.wireless_mode_selected = tk.BooleanVar(value=False)
        
        # 연결 결과
        self.connected_device = None
        self.is_wireless_mode = False
        
        try:
            self.create_widgets()
            self.show_step(0)
            logger.info("ConnectionWizard 초기화 완료")
        except Exception as e:
            logger.error(f"ConnectionWizard 초기화 중 오류: {e}")
            raise
    
    def create_widgets(self):
        """위젯 생성"""
        # Step 0: 시작 및 ADB 확인
        frame0 = ttk.Frame(self, padding="10")
        ttk.Label(frame0, text="ADB 연결을 시작합니다.", font=("Inter", 12, "bold")).pack(pady=10)
        ttk.Label(frame0, text="1. 스마트폰 '개발자 옵션'에서 'USB 디버깅'을 활성화해주세요.").pack(anchor="w")
        ttk.Label(frame0, text="2. PC와 스마트폰을 USB 케이블로 연결해주세요.").pack(anchor="w")
        ttk.Label(frame0, text="3. 스마트폰 화면에 뜨는 'USB 디버깅 허용' 팝업에서 '허용'을 눌러주세요.").pack(anchor="w")
        self.status_label0 = ttk.Label(frame0, text="상태: 대기 중", foreground="blue")
        self.status_label0.pack(pady=10)
        ttk.Button(frame0, text="ADB 연결 확인", command=self.check_adb_connection).pack(pady=5)
        self.steps.append(frame0)
        
        # Step 1: 유선/무선 선택
        frame1 = ttk.Frame(self, padding="10")
        ttk.Label(frame1, text="어떤 방식으로 연결하시겠습니까?", font=("Inter", 12, "bold")).pack(pady=10)
        ttk.Radiobutton(frame1, text="유선 (USB 케이블)", variable=self.wireless_mode_selected, 
                       value=False, command=self.select_connection_type).pack(anchor="w", pady=5)
        ttk.Radiobutton(frame1, text="무선 (Wi-Fi)", variable=self.wireless_mode_selected, 
                       value=True, command=self.select_connection_type).pack(anchor="w", pady=5)
        self.steps.append(frame1)
        
        # Step 2: 무선 연결 설정
        frame2 = ttk.Frame(self, padding="10")
        ttk.Label(frame2, text="무선 연결 설정", font=("Inter", 12, "bold")).pack(pady=10)
        ttk.Label(frame2, text="1. 스마트폰과 PC가 동일한 Wi-Fi 네트워크에 연결되어 있는지 확인해주세요.").pack(anchor="w")
        ttk.Label(frame2, text="2. 스마트폰의 IP 주소와 ADB 포트(보통 5555)를 입력해주세요:").pack(anchor="w")
        ttk.Label(frame2, text="예: 192.168.1.100:5555").pack(anchor="w")
        ttk.Entry(frame2, textvariable=self.device_ip, width=30).pack(pady=5)
        ttk.Button(frame2, text="무선 연결 시도", command=self.attempt_wireless_connection).pack(pady=5)
        self.status_label2 = ttk.Label(frame2, text="상태: 대기 중", foreground="blue")
        self.status_label2.pack(pady=10)
        
        self.pairing_frame = ttk.Frame(frame2)
        ttk.Label(self.pairing_frame, text="Android 11+ 기기: 페어링 코드 입력").pack(pady=5)
        ttk.Entry(self.pairing_frame, textvariable=self.pairing_code, width=20).pack(pady=5)
        ttk.Button(self.pairing_frame, text="페어링 연결", command=self.perform_adb_pair).pack(pady=5)
        self.pairing_frame.pack_forget()  # 초기에는 숨김
        self.steps.append(frame2)
        
        # 하단 버튼 프레임
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side="bottom", fill="x", pady=10)
        
        self.prev_button = ttk.Button(self.button_frame, text="이전", command=self.prev_step, state="disabled")
        self.prev_button.pack(side="left", padx=10)
        
        self.next_button = ttk.Button(self.button_frame, text="다음", command=self.next_step, state="disabled")
        self.next_button.pack(side="right", padx=10)
    
    def show_step(self, step_index):
        """지정된 단계 표시"""
        logger.debug(f"연결 마법사 단계 변경: {step_index}")
        for i, frame in enumerate(self.steps):
            if i == step_index:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self.current_step = step_index
        self.update_buttons()
    
    def update_buttons(self):
        """버튼 상태 업데이트"""
        if self.current_step == 0:
            self.prev_button.config(state="disabled")
            self.next_button.config(state="disabled")
        elif self.current_step == 1:
            self.prev_button.config(state="normal")
            self.next_button.config(state="disabled")
        elif self.current_step == 2:
            self.prev_button.config(state="normal")
            self.next_button.config(state="disabled")
    
    def prev_step(self):
        """이전 단계로 이동"""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    def next_step(self):
        """다음 단계로 이동"""
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)
        elif self.current_step == len(self.steps) - 1:
            self.on_connection_success()
    
    def check_adb_connection(self):
        """ADB 연결 확인"""
        logger.info("ADB 연결 상태 확인 시작")
        self.status_label0.config(text="상태: 연결 확인 중...", foreground="orange")
        threading.Thread(target=self._check_adb_connection_thread, daemon=True).start()
    
    def _check_adb_connection_thread(self):
        """ADB 연결 확인 스레드"""
        logger.info("ADB 연결 확인 스레드 시작")
        try:
            adb_client = AdbClient()
            devices = adb_client.get_connected_devices()
            
            if devices and len(devices) > 0:
                device_id = devices[0]
                logger.info(f"ADB 장치 연결 성공: {device_id}")
                self.connected_device = device_id
                self.is_wireless_mode = ':' in device_id  # IP:PORT 형태면 무선
                
                self.after(0, lambda: self._safe_config(self.status_label0, text=f"상태: 장치 연결됨 ({device_id})", foreground="green"))
                self.after(0, lambda: self._safe_config(self.next_button, state="normal"))
                self.after(100, lambda: self._safe_show_step(1))  # 다음 단계로 자동 전환
            else:
                logger.warning(f"ADB 장치 연결 실패: {devices}")
                self.after(0, lambda: self._safe_config(self.status_label0, text="상태: 장치 연결 실패. USB 디버깅 및 허용 확인.", foreground="red"))
                self.after(0, lambda: messagebox.showerror("연결 오류", 
                    "ADB 장치 연결에 실패했습니다. 다음 사항을 확인해주세요:\n\n"
                    "1. USB 디버깅 활성화\n"
                    "2. PC에서 USB 디버깅 허용\n"
                    "3. ADB 드라이버 설치"))
        except Exception as e:
            error_msg = str(e)
            logger.error(f"ADB 연결 확인 중 오류: {error_msg}")
            self.after(0, lambda msg=error_msg: self._safe_config(self.status_label0, text=f"상태: 연결 확인 중 오류 발생: {msg}", foreground="red"))
    
    def select_connection_type(self):
        """연결 방식 선택"""
        logger.info(f"연결 방식 선택: {'무선' if self.wireless_mode_selected.get() else '유선'}")
        if self.wireless_mode_selected.get():
            logger.info("무선 연결 설정 단계로 이동")
            self.next_button.config(state="normal")
            self.after(100, lambda: self.show_step(2))
        else:
            logger.info("유선 연결 선택, 바로 메인 창으로 이동")
            self.on_connection_success()
    
    def attempt_wireless_connection(self):
        """무선 연결 시도"""
        logger.info("무선 연결 시도 시작")
        ip_port = self.device_ip.get().strip()
        if not ip_port:
            messagebox.showwarning("입력 오류", "스마트폰 IP 주소와 포트를 입력해주세요.")
            return
        
        self._safe_config(self.status_label2, text=f"상태: {ip_port} 연결 시도 중...", foreground="orange")
        threading.Thread(target=self._attempt_wireless_connection_thread, 
                        args=(ip_port,), daemon=True).start()
    
    def _attempt_wireless_connection_thread(self, ip_port):
        """무선 연결 스레드"""
        logger.info(f"무선 연결 스레드 시작: {ip_port}")
        try:
            # 1. 먼저 USB로 연결된 디바이스에서 TCP 모드 활성화
            self.after(0, lambda: self._safe_config(self.status_label2, text="상태: TCP 모드 활성화 중...", foreground="orange"))
            # ADB 클라이언트를 통해 TCP 모드 활성화
            adb_client = AdbClient()
            wireless_enabled = adb_client.enable_wireless_debugging(5555)
            if wireless_enabled:
                logger.info("TCP 모드 활성화 성공")
                time.sleep(2)
            else:
                logger.warning("TCP 모드 활성화 실패, 계속 진행")
            
            # 2. 기존 연결 해제
            self.after(0, lambda: self._safe_config(self.status_label2, text=f"상태: {ip_port} 연결 시도 중...", foreground="orange"))
            run_hidden_subprocess([ADB_PATH, "disconnect", ip_port], 
                         capture_output=True, timeout=5, encoding='utf-8', errors='ignore')
            time.sleep(1)
            # 3. 무선 연결 시도
            result = run_hidden_subprocess([ADB_PATH, "connect", ip_port], 
                                  capture_output=True, text=True, timeout=10, 
                                  encoding='utf-8', errors='ignore')
            output = result.stdout.strip() if result.stdout else ""
            if "connected to" in output:
                logger.info(f"무선 연결 성공: {ip_port}")
                self.connected_device = ip_port
                self.is_wireless_mode = True
                self.after(0, lambda: self._safe_config(self.status_label2, text=f"상태: {ip_port} 연결 성공!", foreground="green"))
                self.after(0, lambda: self.pairing_frame.pack(pady=10))
                self.after(0, lambda: self._safe_config(self.next_button, state="normal"))
            else:
                logger.warning(f"무선 연결 실패: {output}")
                self.after(0, lambda: self._safe_config(self.status_label2, text=f"상태: {ip_port} 연결 실패. IP/포트 및 Wi-Fi 확인.", foreground="red"))
                self.after(0, lambda: self.pairing_frame.pack_forget())
        except Exception as e:
            error_msg = str(e)
            logger.error(f"무선 연결 오류: {error_msg}")
            self.after(0, lambda msg=error_msg: self._safe_config(self.status_label2, text=f"오류 발생: {msg}", foreground="red"))

    def _safe_config(self, widget, **kwargs):
        try:
            if widget and widget.winfo_exists():
                widget.config(**kwargs)
        except Exception:
            pass

    def _safe_show_step(self, step_idx):
        try:
            self.show_step(step_idx)
        except Exception:
            pass
    
    def perform_adb_pair(self):
        """ADB 페어링"""
        ip_port = self.device_ip.get().strip()
        pairing_code = self.pairing_code.get().strip()
        
        if not ip_port or not pairing_code:
            messagebox.showwarning("입력 오류", "IP/포트와 페어링 코드를 모두 입력해주세요.")
            return
        
        self.status_label2.config(text=f"상태: {ip_port} 페어링 시도 중...", foreground="orange")
        threading.Thread(target=self._perform_adb_pair_thread, 
                        args=(ip_port, pairing_code), daemon=True).start()
    
    def _perform_adb_pair_thread(self, ip_port, pairing_code):
        """페어링 스레드"""
        try:
            process = popen_hidden_subprocess([ADB_PATH, "pair", ip_port], 
                                     stdin=subprocess.PIPE, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, 
                                     text=True, encoding='utf-8', errors='ignore')
            stdout, stderr = process.communicate(input=f"{pairing_code}\n", timeout=10)
            
            if "Successfully paired" in stdout:
                logger.info(f"페어링 성공: {ip_port}")
                self.after(0, lambda: self.status_label2.config(
                    text=f"상태: {ip_port} 페어링 성공!", foreground="green"))
                time.sleep(1)
                self.after(100, self.attempt_wireless_connection)
            else:
                logger.warning(f"페어링 실패: {stderr}")
                self.after(0, lambda: self.status_label2.config(
                    text=f"상태: 페어링 실패. 코드 또는 IP/포트 확인.", foreground="red"))
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"페어링 오류: {error_msg}")
            self.after(0, lambda msg=error_msg: self.status_label2.config(
                text=f"페어링 오류: {msg}", foreground="red"))
    
    def on_connection_success(self):
        """연결 성공"""
        logger.info("연결 성공, 메인 창으로 전환")
        
        try:
            # 연결 정보 검증
            if not self.connected_device:
                logger.error("연결된 디바이스 정보가 없습니다")
                messagebox.showerror("오류", "연결된 디바이스 정보가 없습니다.")
                return
                
            # 마스터에 연결 정보 전달
            if hasattr(self.master, 'set_connection_info'):
                logger.info("메인 앱에 연결 정보 전달 중...")
                self.master.set_connection_info(self.connected_device, self.is_wireless_mode)
                
                # 메인 앱 UI 초기화
                if hasattr(self.master, 'init_main_app'):
                    logger.info("메인 앱 UI 초기화 시작...")
                    self.master.init_main_app()
                    logger.info("메인 앱 초기화 완료")
                else:
                    logger.error("메인 앱에 init_main_app 메서드가 없습니다")
            else:
                logger.error("메인 앱에 set_connection_info 메서드가 없습니다")
                messagebox.showerror("오류", "메인 앱 초기화에 실패했습니다.")
                return
                
        except Exception as e:
            logger.error(f"메인 앱 초기화 중 오류: {e}")
            logger.exception("상세 오류 정보:")
            messagebox.showerror("초기화 오류", f"메인 앱 초기화에 실패했습니다:\n{e}")
            return
        
        # ConnectionWizard 창 닫기 (메인 앱 초기화 완료 후)
        try:
            logger.info("ConnectionWizard 창 닫는 중...")
            # 모달 해제 (여러 번 호출해도 안전)
            try:
                self.grab_release()
            except:
                pass
            # 포커스 해제
            try:
                self.master.focus_set()
            except:
                pass
            # 창 파괴
            self.destroy()
            logger.info("ConnectionWizard 창 닫기 완료")
        except Exception as e:
            logger.error(f"ConnectionWizard 창 닫기 중 오류: {e}")
            # 강제로 창 숨기기
            try:
                self.withdraw()
                self.quit()
            except:
                pass
            # 메인 앱에 포커스 주기
            try:
                self.master.lift()
                self.master.focus_force()
            except:
                pass
    
    def on_closing(self):
        """창 닫기"""
        logger.info("연결 마법사 창 닫기 요청")
        
        # 연결 마법사를 닫으면 메인 앱으로 돌아가기
        try:
            # 모달 해제
            self.grab_release()
            # 메인 창으로 포커스 이동
            self.master.focus_set()
            self.master.lift()
            # 마법사 창 닫기
            self.destroy()
            logger.info("연결 마법사 창 정상 닫힘")
            
            # 메인 앱에 연결 실패 상태 알리기 (선택적)
            if hasattr(self.master, 'on_connection_wizard_closed'):
                self.master.on_connection_wizard_closed()
                
        except Exception as e:
            logger.error(f"연결 마법사 창 닫기 중 오류: {e}")
            # 강제 종료
            try:
                self.withdraw()
            except:
                pass
