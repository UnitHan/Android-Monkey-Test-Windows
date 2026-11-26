#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey Testing GUI 애플리케이션 (원본 기능 복구)
메인 GUI 클래스 - 원본의 모든 기능 포함
"""
import sys
import logging
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
from pathlib import Path
import atexit
import os
import glob
import re
from PIL import Image, ImageTk

# matplotlib 설정 - GUI 초기화 전에 설정
try:
    import matplotlib
    # GUI 백엔드 설정 (메인 스레드에서만)
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    
    # 안전한 종료를 위한 설정
    try:
        import matplotlib._pylab_helpers
        import atexit
        
        # 기존 atexit 콜백 제거하여 RuntimeError 방지
        try:
            if hasattr(matplotlib._pylab_helpers, 'Gcf'):
                atexit.unregister(matplotlib._pylab_helpers.Gcf.destroy_all)
        except (ValueError, AttributeError):
            pass  # 이미 제거되었거나 등록되지 않음
            
        # 안전한 종료 함수 등록
        def safe_matplotlib_cleanup():
            try:
                if hasattr(matplotlib._pylab_helpers, 'Gcf'):
                    matplotlib._pylab_helpers.Gcf.destroy_all()
            except Exception:
                pass  # 종료 시 오류 무시
                
        atexit.register(safe_matplotlib_cleanup)
        
    except ImportError:
        pass  # _pylab_helpers 모듈이 없는 경우
    
    logger = logging.getLogger(__name__)
    logger.debug("matplotlib 설정 완료 - 안전한 종료 설정됨")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("matplotlib import 실패")

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 로컬 모듈 import
from src.core.adb_client import AdbClient
from src.core.test_context import TestContext
from src.core.monkey_runner import MonkeyRunner
from src.core.report_generator import ReportGenerator
from src.utils.chart_generator import ChartGenerator
from src.utils.font_manager import get_font_manager
from src.utils.app_search_manager import get_app_search_manager
from src.ui.connection_wizard import ConnectionWizard

# 분리된 핸들러들 import
from src.ui.progress_bar_manager import ProgressBarManager
from src.ui.app_info_handler import AppInfoHandler
from src.ui.chart_handler import ChartHandler
from src.ui.package_handler import PackageHandler
from src.ui.test_handler import TestHandler
from src.ui.ui_helpers import UIHelpers
from src.ui.gui_builder import GUIBuilder

# 새로 분리된 UI 컴포넌트들 import
from src.ui.app_info_display import AppInfoDisplay
from src.ui.button_manager import ButtonManager

logger = logging.getLogger(__name__)

class MonkeyTestApp(tk.Tk):
    """메인 GUI 애플리케이션 (원본 기능 복구)"""
    
    def __init__(self):
        logger.info("MonkeyTestApp 초기화 시작")
        super().__init__()
        
        # 기본 설정
        self.title("Monkey 테스트 자동화")
        
        # 아이콘 설정 - EXE 환경 고려
        self._setup_app_icon()
        
        # 핵심 객체들
        self.test_context = TestContext()
        self.adb_client: Optional[AdbClient] = None
        self.monkey_runner: Optional[MonkeyRunner] = None
        self.report_generator: Optional[ReportGenerator] = None
        
        # 원본 UI 변수들 (완전 복원)
        self.app_packages = []
        self.selected_app_package = tk.StringVar()
        self.selected_preset = tk.StringVar(value="Quick Test")
        self.custom_events = tk.StringVar(value="3000")
        self.custom_seed = tk.StringVar(value="1000")
        self.custom_repeats = tk.StringVar(value="5")
        self.custom_throttle = tk.StringVar(value="200")
        self.estimated_time_label_text = tk.StringVar(value="예상 소요 시간: 약 0분")
        self.search_package_var = tk.StringVar()
        
        # 테스트 상태
        self.test_running = False
        self.is_testing = False  # test_handler에서 사용
        self.current_performance_data = []
        self.monitoring_active = False
        self.logcat_active = False
        
        # 연결 모니터링 관련
        self.connection_monitoring = False
        self.connection_monitor_thread = None
        self.last_connection_status = True
        self.reconnection_attempts = 0
        self.max_reconnection_attempts = 3
        
        # 콘솔 로그 관련
        self.console_visible = False
        self.console_frame = None
        self.console_text = None
        self.main_content_frame = None
        self.original_width = 900
        
        # 콘솔 로그 버퍼링
        self.console_log_buffer = []
        self.console_handler = None
        self.max_buffer_lines = 10000  # 버퍼 크기를 10,000줄로 증가
        
        # 앱 정보
        self.current_app_info = None
        self.app_icon_image = None
        
        # 차트 데이터 저장용 변수 초기화
        self.current_chart_data = None
        
        # GUI 관련 속성 (타입 어노테이션)
        self.device_status_label: Optional[ttk.Label] = None
        self.notebook: Optional[ttk.Notebook] = None
        self.main_container: Optional[ttk.Frame] = None
        
        # UI 위젯들
        self.app_combobox: Optional[ttk.Button] = None  # Button으로 변경
        self.package_combobox: Optional[ttk.Button] = None  # app_combobox 별칭
        self.refresh_button: Optional[ttk.Button] = None
        self.package_status_label: Optional[ttk.Label] = None
        self.app_icon_label: Optional[ttk.Label] = None
        self.app_name_label: Optional[ttk.Label] = None
        self.app_developer_label: Optional[ttk.Label] = None
        self.app_category_label: Optional[ttk.Label] = None
        self.app_version_label: Optional[ttk.Label] = None
        self.store_version_label: Optional[ttk.Label] = None
        self.update_status_label: Optional[ttk.Label] = None
        self.start_button: Optional[ttk.Button] = None
        self.report_notebook: Optional[ttk.Notebook] = None
        self.summary_text: Optional[tk.Text] = None
        self.log_text: Optional[tk.Text] = None  # summary_text 별칭
        self.detail_tree: Optional[ttk.Treeview] = None
        self.issue_text: Optional[tk.Text] = None
        
        # 사용자 정의 입력 필드들
        self.entry_events: Optional[ttk.Entry] = None
        self.entry_seed: Optional[ttk.Entry] = None
        self.entry_repeats: Optional[ttk.Entry] = None
        self.entry_throttle: Optional[ttk.Entry] = None
        self.estimated_time_label: Optional[ttk.Label] = None
        
        # 차트 관련 속성
        self.chart_generator = ChartGenerator()
        self.chart_canvases = {}
        self.current_charts = {}
        
        # 로그 관련 속성
        self.log_queue = queue.Queue()
        self.log_window = None
        
        # 핸들러들 초기화
        self.app_info_handler = AppInfoHandler(self)
        self.chart_handler = ChartHandler(self)
        self.progress_manager = ProgressBarManager(self)
        self.package_handler = PackageHandler(self)
        self.test_handler = TestHandler(self)
        self.ui_helpers = UIHelpers(self)
        self.gui_builder = GUIBuilder(self)
        
        # 새로 분리된 UI 컴포넌트들 초기화
        self.app_info_display = AppInfoDisplay(self)
        self.button_manager = ButtonManager(self)
        
        try:
            # 디렉토리 생성
            from src.config import LOGS_DIR, MONKEY_LOG_DIR, PERFORMANCE_LOG_DIR, WINDOW_SIZE
            LOGS_DIR.mkdir(exist_ok=True)
            MONKEY_LOG_DIR.mkdir(exist_ok=True)
            PERFORMANCE_LOG_DIR.mkdir(exist_ok=True)
            
            # 기본 창 설정 - 화면 중앙에 위치
            self.geometry(WINDOW_SIZE)
            self._center_window()
            self.withdraw()  # 초기에는 메인 창 숨김
            
            # 콘솔 로그 핸들러 항상 설정 (창이 닫혀있어도 버퍼링)
            self.setup_console_handler()
            
            # 연결 마법사 실행
            self.connection_wizard = ConnectionWizard(self)
            self.connection_wizard.focus_set()
            self.connection_wizard.grab_set()  # 모달로 설정
            logger.info("MonkeyTestApp 초기화 완료, ConnectionWizard 실행")
        except Exception as e:
            logger.error(f"MonkeyTestApp 초기화 중 오류: {e}")
            raise
    
    def _center_window(self):
        """창을 화면 중앙에 위치시킴"""
        try:
            # 창 업데이트를 위해 잠시 대기
            self.update_idletasks()
            
            # 화면 크기 가져오기
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            # 창 크기 가져오기
            window_width = self.winfo_reqwidth()
            window_height = self.winfo_reqheight()
            
            # config.py에서 창 크기 정보 가져오기
            from src.config import WINDOW_SIZE
            if 'x' in WINDOW_SIZE:
                window_width = int(WINDOW_SIZE.split('x')[0])
                window_height = int(WINDOW_SIZE.split('x')[1])
            
            # 중앙 위치 계산
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # 창 위치 설정
            self.geometry(f"{window_width}x{window_height}+{x}+{y}")
            logger.info(f"메인 창을 화면 중앙에 위치시킴: {x}+{y}")
            
        except Exception as e:
            logger.warning(f"창 중앙 위치 설정 실패: {e}")
    
    def set_connection_info(self, device_serial: str, is_wireless: bool):
        """연결 정보 설정"""
        self.test_context.device_serial = device_serial
        self.test_context.is_wireless_mode = is_wireless
        self.adb_client = AdbClient(device_serial)
        
        # 다른 컴포넌트들 초기화
        self.monkey_runner = MonkeyRunner(self.adb_client, self.test_context)
        self.report_generator = ReportGenerator(self.test_context)
        
        # 초기 연결 상태 설정
        connection_mode = self.adb_client.get_connection_mode() if self.adb_client else "알 수 없음"
        
        logger.info(f"연결 정보 설정 완료: {device_serial} ({'무선' if is_wireless else '유선'})")
    
    def init_main_app(self):
        """ADB 연결 성공 후 메인 앱 초기화"""
        logger.info("메인 앱 위젯 초기화 시작")
        try:
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.setup_widget_styles()  # 위젯 생성 전에 스타일 먼저 설정
            self.create_main_widgets()  # 원본처럼 직접 위젯 생성
            self.setup_logging()
            self.load_app_packages()
            self.setup_fonts()
            
            # 창 크기 제한 설정 (시각화를 위한 최소 크기 보장)
            from src.config import MIN_WINDOW_SIZE
            self.minsize(MIN_WINDOW_SIZE[0], MIN_WINDOW_SIZE[1])
            
            # 연결 모니터링 시작
            self.start_connection_monitoring()
            
            # 초기 연결 상태 표시
            self._update_connection_status()
            
            self.deiconify()  # 메인 창 표시
            logger.info("메인 앱 위젯 초기화 완료")
        except Exception as e:
            logger.error(f"메인 앱 위젯 초기화 중 오류: {e}")
            raise
    
    def on_connection_wizard_closed(self):
        """연결 마법사가 닫혔을 때 호출되는 메서드"""
        logger.info("연결 마법사가 닫혔습니다 - 연결 없이 진행")
        
        # 사용자가 연결 마법사를 닫았으므로 프로그램도 종료
        try:
            logger.info("사용자가 연결 마법사를 닫음 - 프로그램 종료")
            self.quit()
            self.destroy()
        except Exception as e:
            logger.error(f"프로그램 종료 중 오류: {e}")
    
    def create_main_widgets(self):
        """메인 위젯 생성 (원본 복원)"""
        logger.info("메인 위젯 생성 시작")
        
        # 메인 컨테이너 프레임 (콘솔 로그와 함께 사용할 수 있도록)
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill="both", expand=True)
        
        # 메인 콘텐츠 프레임을 상하로 분할
        self.main_content_frame = ttk.Frame(self.main_container)
        self.main_content_frame.pack(side="left", fill="both", expand=True)
        
        # 상단 제어 프레임 (고정 크기, 컴팩트화)
        control_frame = ttk.LabelFrame(self.main_content_frame, text="테스트 설정", padding="8")
        control_frame.pack(side="top", fill="x", padx=10, pady=(8, 3))
        
        # 앱 선택
        app_select_frame = ttk.Frame(control_frame)
        app_select_frame.pack(fill="x", pady=5)
        ttk.Label(app_select_frame, text="테스트할 앱 선택:").pack(side="left", padx=5)
        
        # 디바이스 상태 라벨 추가
        self.device_status_label = ttk.Label(app_select_frame, text="🔌 연결 확인 중...", foreground="orange")
        self.device_status_label.pack(side="right", padx=5)
        
        # 패키지 상태 라벨 (package_handler에서 사용)
        self.package_status_label = ttk.Label(app_select_frame, text="", foreground="gray")
        self.package_status_label.pack(side="left", padx=5)
        
        # Button + Menu 조합으로 안정적인 앱 선택기 구현
        self.selected_app_package.set("테스트할 앱을 선택하세요")
        
        # 앱 선택 버튼 생성 (Combobox 대체)
        self.app_combobox = ttk.Button(app_select_frame, 
                                      textvariable=self.selected_app_package, 
                                      command=self._show_app_selection_menu,
                                      width=40)
        
        # 버튼 스타일 설정
        try:
            style = ttk.Style()
            style.configure("AppSelect.TButton", 
                          background="white",
                          relief="sunken",
                          anchor="w")  # 왼쪽 정렬
            self.app_combobox.configure(style="AppSelect.TButton")
        except Exception as e:
            logger.warning(f"Button 스타일 설정 실패: {e}")
        
        self.app_combobox.pack(side="left", fill="x", expand=True, padx=5)
        
        # 새로고침 버튼을 변수로 저장 (package_handler에서 참조)
        self.refresh_button = self.button_manager.create_refresh_button(app_select_frame)
        
        # package_handler에서 참조할 수 있도록 별칭 생성
        self.package_combobox = self.app_combobox
        
        # 앱 정보 표시 프레임 (분리된 컴포넌트 사용)
        self.app_info_display.create_app_info_frame(control_frame)
        
        # 디버깅용: 앱 정보 프레임 위치 확인
        def check_frame_positions():
            try:
                if hasattr(self.app_info_display, 'app_info_frame'):
                    frame = self.app_info_display.app_info_frame
                    logger.debug(f"🔍 앱 정보 프레임 위치: x={frame.winfo_x()}, y={frame.winfo_y()}, width={frame.winfo_width()}, height={frame.winfo_height()}")
                    logger.debug(f"🔍 앱 정보 프레임 표시 상태: {frame.winfo_viewable()}")
            except Exception as e:
                logger.debug(f"🔍 프레임 위치 확인 오류: {e}")
        
        self.after(1000, check_frame_positions)  # 1초 후 위치 확인
        
        # 패키지명 검색 프레임
        search_frame = ttk.Frame(control_frame)
        search_frame.pack(fill="x", pady=5)
        ttk.Label(search_frame, text="패키지명 검색:").pack(side="left", padx=5)
        
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_package_var, width=30, style="White.TEntry")
        
        # Entry 배경색 강제 설정
        try:
            self.search_entry.configure(background="white")
            self.search_entry.tk.call("ttk::style", "configure", "White.TEntry", "-fieldbackground", "white")
        except Exception as e:
            logger.warning(f"Entry 추가 스타일 설정 실패: {e}")
        
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.search_entry.bind("<Return>", self.search_and_select_package)
        
        ttk.Button(search_frame, text="검색 & 선택", command=self.search_and_select_package).pack(side="left", padx=5)
        ttk.Button(search_frame, text="앱 실행", command=self.launch_selected_app).pack(side="left", padx=5)
        
        # 프리셋 선택
        preset_frame = ttk.LabelFrame(control_frame, text="테스트 프리셋", padding="6")
        preset_frame.pack(fill="x", pady=6)
        
        # 디버깅용: 프리셋 프레임 위치도 확인
        def check_preset_frame_position():
            try:
                logger.debug(f"🔍 프리셋 프레임 위치: x={preset_frame.winfo_x()}, y={preset_frame.winfo_y()}, width={preset_frame.winfo_width()}, height={preset_frame.winfo_height()}")
                logger.debug(f"🔍 프리셋 프레임 표시 상태: {preset_frame.winfo_viewable()}")
            except Exception as e:
                logger.debug(f"🔍 프리셋 프레임 위치 확인 오류: {e}")
        
        self.after(1200, check_preset_frame_position)  # 1.2초 후 위치 확인
        
        # 그리드 컬럼 가중치 설정 (2열 구조)
        preset_frame.columnconfigure(0, weight=1)
        preset_frame.columnconfigure(1, weight=1)
        
        # 프리셋 설명 추가 (간소화 - 공간 절약)
        description_text = """빠른 검증: Smoke/Quick  |  심화 테스트: Standard/Deep/Extreme"""
        
        desc_label = ttk.Label(preset_frame, text=description_text, 
                              font=("Noto Sans KR", 8), foreground="gray", 
                              justify="left", anchor="w")
        desc_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=5)
        
        from src.config import PRESETS
        
        # 수평 배치를 위한 프리셋 순서 정의
        preset_names = list(PRESETS.keys())
        preset_names = [name for name in preset_names if name != "재현테스트"]  # 재현테스트 제외
        
        # 첫 번째 행: Smoke Test와 Quick Test를 나란히 배치
        row_index = 1
        if "Smoke Test" in preset_names:
            config = PRESETS["Smoke Test"]
            description = f"Smoke Test - {config['events']}개 이벤트 x {config['repeats']}회 반복 (Throttle: {config['throttle']}ms, Random Seed) → {config['est_time']}"
            rb = ttk.Radiobutton(preset_frame, text=description,
                                variable=self.selected_preset, value="Smoke Test", 
                                command=self.update_custom_preset_fields)
            rb.grid(row=row_index, column=0, sticky="w", pady=1, padx=5)
        
        if "Quick Test" in preset_names:
            config = PRESETS["Quick Test"]
            description = f"Quick Test - {config['events']}개 이벤트 x {config['repeats']}회 반복 (Throttle: {config['throttle']}ms, Random Seed) → {config['est_time']}"
            rb = ttk.Radiobutton(preset_frame, text=description,
                                variable=self.selected_preset, value="Quick Test", 
                                command=self.update_custom_preset_fields)
            rb.grid(row=row_index, column=1, sticky="w", pady=1, padx=5)
        
        # 두 번째 행: Standard Test와 Deep Test를 나란히 배치
        row_index = 2
        if "Standard Test" in preset_names:
            config = PRESETS["Standard Test"]
            description = f"Standard Test - {config['events']}개 이벤트 x {config['repeats']}회 반복 (Throttle: {config['throttle']}ms, Random Seed) → {config['est_time']}"
            rb = ttk.Radiobutton(preset_frame, text=description,
                                variable=self.selected_preset, value="Standard Test", 
                                command=self.update_custom_preset_fields)
            rb.grid(row=row_index, column=0, sticky="w", pady=1, padx=5)
        
        if "Deep Test" in preset_names:
            config = PRESETS["Deep Test"]
            description = f"Deep Test - {config['events']}개 이벤트 x {config['repeats']}회 반복 (Throttle: {config['throttle']}ms, Random Seed) → {config['est_time']}"
            rb = ttk.Radiobutton(preset_frame, text=description,
                                variable=self.selected_preset, value="Deep Test", 
                                command=self.update_custom_preset_fields)
            rb.grid(row=row_index, column=1, sticky="w", pady=1, padx=5)
        
        # 세 번째 행: Extreme Test (단독 배치)
        row_index = 3
        if "Extreme Test" in preset_names:
            config = PRESETS["Extreme Test"]
            description = f"Extreme Test - {config['events']}개 이벤트 x {config['repeats']}회 반복 (Throttle: {config['throttle']}ms, Random Seed) → {config['est_time']}"
            rb = ttk.Radiobutton(preset_frame, text=description,
                                variable=self.selected_preset, value="Extreme Test", 
                                command=self.update_custom_preset_fields)
            rb.grid(row=row_index, column=0, columnspan=2, sticky="w", pady=1, padx=5)
        
        # 네 번째 행: 사용자 지정과 재현테스트를 같은 행에 배치
        row_index = 4
        custom_radio_frame = ttk.Frame(preset_frame)
        custom_radio_frame.grid(row=row_index, column=0, columnspan=2, sticky="ew", pady=2, padx=5)
        
        # 왼쪽: 사용자 지정 라디오버튼
        ttk.Radiobutton(custom_radio_frame, text="사용자 지정 (Random Seed)", 
                       variable=self.selected_preset, value="Custom", 
                       command=self.update_custom_preset_fields).pack(side="left")
        
        # 오른쪽: 재현테스트 라디오버튼
        ttk.Radiobutton(custom_radio_frame, text="재현테스트", 
                       variable=self.selected_preset, value="재현테스트", 
                       command=self.update_custom_preset_fields).pack(side="left", padx=(50, 0))
        
        # 사용자 지정 입력 필드 프레임 (재현테스트와 사용자 지정 공통)
        self.custom_input_frame = ttk.Frame(preset_frame)
        self.custom_input_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=2, padx=20)
        
        # 첫 번째 줄: 이벤트 수, 반복 횟수, Throttle
        input_line1 = ttk.Frame(self.custom_input_frame)
        input_line1.pack(fill="x", pady=2)
        
        ttk.Label(input_line1, text="이벤트 수:").pack(side="left", padx=(0, 2))
        self.entry_events = ttk.Entry(input_line1, textvariable=self.custom_events, width=8, style="White.TEntry")
        try:
            self.entry_events.configure(background="white")
        except:
            pass
        self.entry_events.pack(side="left", padx=(0, 20))
        self.entry_events.bind("<KeyRelease>", self.update_estimated_time)
        
        ttk.Label(input_line1, text="반복 횟수:").pack(side="left", padx=(0, 2))
        self.entry_repeats = ttk.Entry(input_line1, textvariable=self.custom_repeats, width=8, style="White.TEntry")
        try:
            self.entry_repeats.configure(background="white")
        except:
            pass
        self.entry_repeats.pack(side="left", padx=(0, 20))
        self.entry_repeats.bind("<KeyRelease>", self.update_estimated_time)
        
        ttk.Label(input_line1, text="Throttle(ms):").pack(side="left", padx=(0, 2))
        self.entry_throttle = ttk.Entry(input_line1, textvariable=self.custom_throttle, width=8, style="White.TEntry")
        try:
            self.entry_throttle.configure(background="white")
        except:
            pass
        self.entry_throttle.pack(side="left")
        self.entry_throttle.bind("<KeyRelease>", self.update_estimated_time)
        
        # 두 번째 줄: Seed 입력 (재현테스트용) + 예상 시간
        input_line2 = ttk.Frame(self.custom_input_frame)
        input_line2.pack(fill="x", pady=2)
        
        ttk.Label(input_line2, text="※ 재현테스트용 Seed 값 입력:").pack(side="left", padx=(0, 10))
        ttk.Label(input_line2, text="Seed:").pack(side="left", padx=(0, 2))
        self.entry_seed = ttk.Entry(input_line2, textvariable=self.custom_seed, width=8, style="White.TEntry")
        try:
            self.entry_seed.configure(background="white")
        except:
            pass
        self.entry_seed.pack(side="left", padx=(0, 20))
        
        self.estimated_time_label = ttk.Label(input_line2, textvariable=self.estimated_time_label_text, 
                                             foreground="blue")
        self.estimated_time_label.pack(side="left", padx=10)
        
        # Gemini AI 로고 추가 (프리셋 프레임 오른쪽 하단)
        logger.info("🔍 Gemini 로고 추가 시도...")
        self.add_gemini_logo(preset_frame)
        
        self.update_custom_preset_fields()  # 초기 상태 설정
        
        # 버튼 프레임 (분리된 컴포넌트 사용)
        self.button_manager.create_button_frame(control_frame)
        
        # 버튼 참조를 위한 별칭 (기존 코드 호환성)
        self.start_button = self.button_manager.start_button
        
        # 리포트 섹션 (노트북 탭) - 더 큰 영역 할당
        self.report_notebook = ttk.Notebook(self.main_content_frame)
        self.report_notebook.pack(side="bottom", fill="both", expand=True, padx=10, pady=(3, 8))
        
        # 요약 탭 - 높이 최적화 (시각화 영역 확보를 위해 줄임)
        self.summary_tab = ttk.Frame(self.report_notebook)
        self.report_notebook.add(self.summary_tab, text="요약")
        
        # 한글 폰트 적용 - font_manager에서 폰트 패밀리 가져오기
        korean_font_family = get_font_manager().get_font_family()
        gui_font = (korean_font_family or "Noto Sans KR", 10) if korean_font_family else ("맑은 고딕", 10)
        
        self.summary_text = tk.Text(self.summary_tab, wrap="word", height=12, font=gui_font)
        self.summary_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.summary_text.config(state="disabled")  # 읽기 전용
        
        # UI helpers에서 사용할 수 있도록 별칭 추가
        self.log_text = self.summary_text
          # 상세 결과 탭 (테이블) - Seed 컬럼 추가
        self.detail_tab = ttk.Frame(self.report_notebook)
        self.report_notebook.add(self.detail_tab, text="결과 상세")
        self.detail_tree = ttk.Treeview(self.detail_tab,
                               columns=("repeat", "time", "seed", "events", "crash", "anr", "timeout", "mem_peak", "cpu_peak"),
                               show="headings")
        self.detail_tree.heading("repeat", text="반복")
        self.detail_tree.heading("time", text="실행 시간")
        self.detail_tree.heading("seed", text="Seed")
        self.detail_tree.heading("events", text="이벤트 수")
        self.detail_tree.heading("crash", text="Crash")
        self.detail_tree.heading("anr", text="ANR")
        self.detail_tree.heading("timeout", text="Timeout")
        self.detail_tree.heading("mem_peak", text="메모리 피크")
        self.detail_tree.heading("cpu_peak", text="CPU 피크")
        self.detail_tree.column("repeat", width=50, anchor="center")
        self.detail_tree.column("time", width=100, anchor="center")
        self.detail_tree.column("seed", width=60, anchor="center")
        self.detail_tree.column("events", width=80, anchor="center")
        self.detail_tree.column("crash", width=60, anchor="center")
        self.detail_tree.column("anr", width=60, anchor="center")
        self.detail_tree.column("timeout", width=80, anchor="center")
        self.detail_tree.column("mem_peak", width=100, anchor="center")
        self.detail_tree.column("cpu_peak", width=80, anchor="center")
        self.detail_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 이슈 요약 탭
        self.issue_tab = ttk.Frame(self.report_notebook)
        self.report_notebook.add(self.issue_tab, text="이슈 요약 및 권고사항")
        self.issue_text = tk.Text(self.issue_tab, wrap="word", font=gui_font)
        self.issue_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.issue_text.config(state="disabled")
        
        # 시각화 탭 제거됨 (사용자 요청에 따라)
        
        logger.info("메인 위젯 생성 완료")
    
    def update_custom_preset_fields(self):
        """프리셋 선택에 따라 사용자 지정 입력 필드의 활성화/비활성화 상태를 변경합니다."""
        # 현재 선택된 패키지 보존 (안전장치)
        current_package_selection = None
        if hasattr(self, 'selected_app_package') and self.selected_app_package:
            current_package_selection = self.selected_app_package.get()
            logger.debug(f"🔍 현재 선택된 패키지: {current_package_selection}")
            if current_package_selection in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", "업데이트 실패"]:
                current_package_selection = None
                logger.debug(f"🔍 유효하지 않은 패키지 선택으로 인해 None으로 설정")
        
        selected_preset = self.selected_preset.get()
        logger.debug(f"🔍 선택된 프리셋: {selected_preset}")
        is_custom = (selected_preset == "Custom")
        is_reproduce = (selected_preset == "재현테스트")
        
        # 사용자 지정과 재현테스트 모두에서 입력 필드 활성화
        input_enabled = is_custom or is_reproduce
        state = "normal" if input_enabled else "disabled"
        
        # 입력 필드 상태 설정
        if self.entry_events:
            self.entry_events.config(state=state)
        if self.entry_repeats:
            self.entry_repeats.config(state=state)
        if self.entry_throttle:
            self.entry_throttle.config(state=state)
        
        # 재현테스트에서만 기본값 로드
        if is_reproduce:
            from src.config import PRESETS
            preset_config = PRESETS["재현테스트"]
            self.custom_events.set(preset_config["events"])
            self.custom_repeats.set(preset_config["repeats"])
            self.custom_throttle.set(preset_config["throttle"])
        
        # Seed 입력 필드는 재현테스트일 때만 활성화
        if self.entry_seed:
            seed_state = "normal" if is_reproduce else "disabled" 
            self.entry_seed.config(state=seed_state)
        
        # 패키지 선택 복원 (필요한 경우)
        logger.debug(f"🔍 복원 전 현재 콤보박스 값: {self.selected_app_package.get()}")
        if (current_package_selection and 
            hasattr(self, 'selected_app_package') and 
            self.selected_app_package.get() != current_package_selection):
            logger.debug(f"🔍 패키지 선택 복원 시도: {current_package_selection}")
            self.selected_app_package.set(current_package_selection)
            logger.debug(f"🔍 프리셋 변경 후 패키지 선택 복원: {current_package_selection}")
        else:
            logger.debug(f"🔍 패키지 복원 불필요 - current: {current_package_selection}, combo: {self.selected_app_package.get()}")
        
        self.update_estimated_time()
    
    def _show_app_selection_menu(self):
        """앱 선택 다이얼로그 표시 (메뉴 대신 바로 검색 창 열기)"""
        if not self.app_packages:
            messagebox.showinfo("정보", "먼저 앱 목록을 새로고침해주세요.")
            return
        
        # 바로 검색 다이얼로그 열기
        self._open_app_search_dialog()
    
    def _select_app_from_menu(self, package_name: str):
        """메뉴에서 앱 선택"""
        try:
            self.selected_app_package.set(package_name)
            logger.debug(f"메뉴에서 앱 선택됨: {package_name}")
            # 앱 선택 이벤트 호출
            self.on_app_selected()
        except Exception as e:
            logger.error(f"앱 선택 오류: {e}")
    
    def _open_app_search_dialog(self):
        """앱 검색 다이얼로그 열기 (가운데 위치, 앱 아이콘 표시)"""
        try:
            # 검색 다이얼로그 창 생성
            dialog = tk.Toplevel(self)
            dialog.title("앱 검색 및 선택")
            dialog.resizable(True, True)
            dialog.grab_set()  # 모달 창으로 설정
            dialog.transient(self)  # 부모 창과 연결
            
            # 창 크기 설정 (버튼 영역까지 충분히 보이도록 크기 증가)
            dialog_width = 600
            dialog_height = 600  # 500 → 600으로 증가
            
            # 화면 중앙에 위치시키기
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()
            x = (screen_width - dialog_width) // 2
            y = (screen_height - dialog_height) // 2
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            
            # 앱 아이콘 설정
            try:
                if hasattr(self, '_icon_image'):
                    dialog.iconphoto(True, self._icon_image)  # type: ignore
                else:
                    # 아이콘 파일 직접 로드
                    import sys
                    import os
                    from PIL import Image, ImageTk
                    
                    if getattr(sys, 'frozen', False):
                        # EXE 환경
                        if hasattr(sys, '_MEIPASS'):
                            icon_path = os.path.join(getattr(sys, '_MEIPASS'), "icon.ico")  # type: ignore
                        else:
                            icon_path = os.path.join(os.path.dirname(sys.executable), "icon.ico")
                    else:
                        # 개발 환경
                        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                        icon_path = os.path.join(base_dir, "icon.ico")
                    
                    if os.path.exists(icon_path):
                        if icon_path.endswith('.ico'):
                            dialog.iconbitmap(icon_path)
                        else:
                            pil_image = Image.open(icon_path)
                            icon_img = ImageTk.PhotoImage(pil_image)
                            dialog.iconphoto(True, icon_img)  # type: ignore
            except Exception as e:
                logger.warning(f"다이얼로그 아이콘 설정 실패: {e}")
            
            # 제목 프레임 (앱 정보와 함께)
            title_frame = ttk.Frame(dialog)
            title_frame.pack(fill="x", padx=15, pady=(15, 10))
            
            title_label = ttk.Label(title_frame, text="📱 설치된 앱 목록", 
                                   font=("맑은 고딕", 12, "bold"))
            title_label.pack(side="left")
            
            count_label = ttk.Label(title_frame, text=f"총 {len(self.app_packages)}개 앱", 
                                   font=("맑은 고딕", 9), foreground="gray")
            count_label.pack(side="right")
            
            # 검색 프레임 (더 큰 입력창)
            search_frame = ttk.LabelFrame(dialog, text="🔍 검색", padding="10")
            search_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, 
                                   font=("맑은 고딕", 11), width=50)
            search_entry.pack(fill="x")
            search_entry.focus_set()
            
            # 안내 텍스트
            hint_label = ttk.Label(search_frame, text="앱 이름이나 패키지명을 입력하여 검색하세요 (1글자부터 검색)", 
                                 font=("맑은 고딕", 8), foreground="gray")
            hint_label.pack(anchor="w", pady=(2, 0))
            
            # 목록 프레임 (더 세련된 디자인)
            list_frame = ttk.LabelFrame(dialog, text="📋 앱 목록", padding="10")
            list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
            
            # 리스트박스와 스크롤바 (더 큰 폰트, 적절한 높이)
            listbox = tk.Listbox(list_frame, font=("맑은 고딕", 10), height=12)  # 15 → 12로 줄임
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
            
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # 앱 검색 관리자 가져오기
            app_search_manager = get_app_search_manager()
            
            # 설치된 패키지 목록 업데이트
            app_search_manager.set_installed_packages(self.app_packages)
            
            # 검색 상태 변수들을 dialog에 저장
            dialog.current_results = []  # 현재 검색 결과
            
            def update_app_list(search_query: str = ""):
                """앱 목록 업데이트 (검색어에 따라)"""
                try:
                    # 검색 수행
                    if search_query.strip():
                        search_results = app_search_manager.search(search_query.strip(), limit=100)
                        count_text = f"검색 결과: {len(search_results)}개"
                    else:
                        search_results = app_search_manager.search("", limit=50)  # 기본 인기 앱들
                        count_text = f"총 {len(self.app_packages)}개 앱"
                    
                    # 목록 업데이트
                    listbox.delete(0, tk.END)
                    dialog.current_results.clear()
                    
                    for display_name, package_name in search_results:
                        listbox.insert(tk.END, display_name)
                        dialog.current_results.append((display_name, package_name))
                    
                    count_label.config(text=count_text)
                    
                    # 결과가 없으면 메시지 표시
                    if not search_results and search_query.strip():
                        listbox.insert(tk.END, "검색 결과가 없습니다.")
                        
                except Exception as e:
                    logger.error(f"앱 목록 업데이트 실패: {e}")
                    listbox.delete(0, tk.END)
                    listbox.insert(tk.END, f"오류 발생: {e}")
            
            # 초기 앱 목록 표시
            update_app_list()
            
            # 검색 필터링 함수 (실시간 검색)
            def filter_apps(*args):
                search_text = search_var.get()
                update_app_list(search_text)
            
            search_var.trace("w", filter_apps)
            
            # 버튼 프레임 (더 큰 버튼들)
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill="x", padx=15, pady=(0, 15))
            
            def select_and_close():
                selection = listbox.curselection()
                if selection:
                    selected_index = selection[0]
                    # 검색 결과가 없거나 선택된 인덱스가 범위를 벗어나면 오류 메시지
                    if (not dialog.current_results or 
                        selected_index < 0 or 
                        selected_index >= len(dialog.current_results)):
                        messagebox.showwarning("선택 오류", "올바른 앱을 선택해주세요.")
                        return
                    
                    # 선택된 앱 정보 가져오기
                    selected_display_name, selected_package = dialog.current_results[selected_index]
                    
                    # 앱 선택 적용
                    self._select_app_from_menu(selected_package)
                    dialog.destroy()
                else:
                    messagebox.showwarning("선택 필요", "선택할 앱을 클릭해주세요.")
            
            def cancel_and_close():
                dialog.destroy()
            
            # 버튼들 (더 큰 크기와 아이콘)
            ttk.Button(button_frame, text="✅ 선택", command=select_and_close, 
                      width=12).pack(side="right", padx=(10, 0))
            ttk.Button(button_frame, text="❌ 취소", command=cancel_and_close, 
                      width=12).pack(side="right")
            
            # 현재 선택된 앱 표시 (있는 경우)
            current_selection = self.selected_app_package.get()
            if (current_selection and 
                current_selection not in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", "업데이트 실패"]):
                
                current_frame = ttk.Frame(dialog)
                current_frame.pack(fill="x", padx=15, pady=(0, 5))
                
                # 현재 선택된 앱의 표시명 생성 (새 검색 매니저 사용)
                current_display_name = app_search_manager.get_display_name(current_selection)
                
                ttk.Label(current_frame, text="현재 선택:", 
                         font=("맑은 고딕", 9), foreground="blue").pack(side="left")
                ttk.Label(current_frame, text=current_display_name, 
                         font=("맑은 고딕", 9, "bold"), foreground="blue").pack(side="left", padx=(5, 0))
                
                # 리스트에서 현재 선택된 항목 강조
                try:
                    # 현재 검색 결과에서 해당 패키지 찾기
                    for i, (display_name, package_name) in enumerate(dialog.current_results):
                        if package_name == current_selection:
                            listbox.selection_set(i)
                            listbox.see(i)
                            break
                except (ValueError, tk.TclError):
                    pass
            
            # 이벤트 바인딩
            listbox.bind("<Double-Button-1>", lambda e: select_and_close())
            search_entry.bind("<Return>", lambda e: select_first_result())
            dialog.bind("<Escape>", lambda e: cancel_and_close())
            
            def select_first_result():
                """검색 결과의 첫 번째 항목 선택"""
                if listbox.size() > 0:
                    listbox.selection_set(0)
                    select_and_close()
                else:
                    messagebox.showinfo("검색 결과 없음", "검색 결과가 없습니다.")
            
        except Exception as e:
            logger.error(f"앱 검색 다이얼로그 오류: {e}")
            messagebox.showerror("오류", f"검색 다이얼로그를 열 수 없습니다: {e}")
    
    def update_estimated_time(self, event=None):
        """사용자 지정 프리셋의 예상 소요 시간을 업데이트합니다."""
        selected_preset = self.selected_preset.get()
        
        if selected_preset in ["Custom", "재현테스트"]:
            try:
                events = int(self.custom_events.get())
                repeats = int(self.custom_repeats.get())
                throttle = int(self.custom_throttle.get())
                from src.ui.ui_utils import calculate_estimated_time
                estimated = calculate_estimated_time(events, repeats, throttle)
                self.estimated_time_label_text.set(f"예상 소요 시간: {estimated}")
            except ValueError:
                self.estimated_time_label_text.set("예상 소요 시간: 유효하지 않은 입력")
        else:
            from src.config import PRESETS
            if selected_preset in PRESETS:
                self.estimated_time_label_text.set(f"예상 소요 시간: {PRESETS[selected_preset]['est_time']}")
            else:
                self.estimated_time_label_text.set("예상 소요 시간: -")

    def search_and_select_package(self, event=None):
        """패키지명으로 검색하고 선택"""
        search_text = self.search_package_var.get().strip().lower()
        if not search_text:
            return
        
        # 앱 패키지 목록에서 검색
        for package in self.app_packages:
            if search_text in package.lower():
                self.selected_app_package.set(package)
                self.on_app_selected()
                return
        
        # 찾지 못한 경우
        messagebox.showwarning("검색 결과", f"'{search_text}'를 포함하는 패키지를 찾을 수 없습니다.")

    def launch_selected_app(self):
        """선택된 앱 실행"""
        package_name = self.selected_app_package.get()
        if not package_name or package_name == "테스트할 앱을 선택하세요":
            messagebox.showwarning("경고", "먼저 실행할 앱을 선택해주세요.")
            return
        
        try:
            if self.adb_client:
                self.adb_client.launch_app(package_name)
                messagebox.showinfo("성공", f"앱 '{package_name}'을(를) 실행했습니다.")
            else:
                messagebox.showerror("오류", "ADB 클라이언트가 초기화되지 않았습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"앱 실행 중 오류가 발생했습니다: {e}")

    def start_test_thread(self):
        """테스트 시작 (패키지 핸들러 위임)"""
        if hasattr(self, 'test_handler'):
            # 프로그래스바 시작
            self.progress_manager.start_progress(100, "테스트 준비 중...")
            
            self.test_handler.start_test_thread()
        else:
            messagebox.showerror("오류", "테스트 핸들러가 초기화되지 않았습니다.")

    def on_app_selected(self, event=None):
        """앱이 선택되었을 때 호출되는 이벤트 핸들러 (분리된 컴포넌트 사용)"""
        selected_package = self.selected_app_package.get().strip()
        logger.debug(f"🔍 on_app_selected 호출됨: {selected_package}")
        self.app_info_display.on_app_selected(selected_package)

    def fetch_app_info_async(self, package_name: str):
        """앱 정보 조회를 분리된 컴포넌트에 위임"""
        self.app_info_display.fetch_app_info_async(package_name)

    def update_app_info_ui(self, app_name: str, developer_info: str, category_info: str, version_info: str, icon_data: Optional[bytes] = None):
        """앱 정보 UI 업데이트를 분리된 컴포넌트에 위임"""
        self.app_info_display.update_app_info_ui(app_name, developer_info, category_info, version_info, icon_data)

    def disconnect_wireless(self):
        """무선 연결 종료를 분리된 컴포넌트에 위임"""
        self.button_manager.disconnect_wireless()

    def reboot_device(self):
        """장치 재부팅을 분리된 컴포넌트에 위임"""
        self.button_manager.reboot_device()

    def _run_monkey_test(self, package_name):
        """Monkey 테스트 실행 (원본과 100% 동일)"""
        logger.info(f"Monkey 테스트 시작: 패키지={package_name}")
        
        try:
            # 테스트 컨텍스트 설정
            self.test_context.app_package_name = package_name
            
            # MonkeyRunner 콜백 설정
            if self.monkey_runner:
                self.monkey_runner.set_status_callback(self.update_status_message)
                self.monkey_runner.set_completion_callback(self.on_test_completion)
                self.monkey_runner.set_progress_update_callback(self.update_test_progress)
                
                # 프리셋 기반으로 결정된 반복 모드 사용
                repeat_mode = getattr(self, 'current_repeat_mode', False)
                
                # 테스트 시작 시 성능그래프 버튼 비활성화
                if hasattr(self, 'button_manager') and self.button_manager:
                    self.button_manager.disable_performance_graph_button()
                
                # 시각화 탭이 비활성화되어 있어 진행 중 메시지 표시 생략
                
                # 테스트 시작
                success = self.monkey_runner.start_test(repeat_mode=repeat_mode)
                
                if not success:
                    raise Exception("MonkeyRunner 시작 실패")
                    
                logger.info(f"MonkeyRunner 시작 완료 (반복 모드: {'활성화' if repeat_mode else '비활성화'})")
                
            else:
                raise Exception("MonkeyRunner가 초기화되지 않았습니다")
                
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
            self.after(0, lambda error=e: self.on_test_completion(False, f"테스트 오류: {error}"))
    
    def on_test_completion(self, success: bool, message: str):
        """테스트 완료 콜백"""
        logger.info(f"테스트 완료: success={success}, message={message}")
        
        try:
            # 특별한 UI 업데이트 시그널 처리
            if message == "UI_UPDATE_SUMMARY":
                self.update_report_display()
                return
            elif message == "UI_UPDATE_DETAILS":
                self.update_report_display()
                return
            elif message == "UI_UPDATE_CHARTS":
                # 실시간 차트 업데이트 비활성화 (테스트 완료 후에만 차트 표시)
                logger.info("실시간 차트 업데이트 신호 수신 - 테스트 완료 후 처리 예정")
                return
            
            # 백그라운드 프로세스 완전 정리
            if hasattr(self, 'monkey_runner') and self.monkey_runner:
                try:
                    logger.info("MonkeyRunner 백그라운드 프로세스 정리 시작")
                    # 포그라운드 모니터링 강제 중지
                    self.monkey_runner.stop_foreground_monitoring()
                    logger.info("✅ 포그라운드 모니터링 완전 중지됨")
                except Exception as cleanup_error:
                    logger.warning(f"MonkeyRunner 정리 중 오류: {cleanup_error}")
            
            # UI 상태 복원
            self.test_running = False
            if hasattr(self, 'button_manager'):
                self.button_manager.update_test_button_state(False)
            
            # 프로그래스바 완료 처리
            if success is not None:
                if success:
                    self.progress_manager.complete_progress("테스트 완료!")
                else:
                    self.progress_manager.complete_progress("테스트 실패")
            
            # 리포트 표시 업데이트
            self.update_report_display()
            
            # 차트 데이터 업데이트 (성공한 경우)
            if success:
                logger.info("테스트 완료 - 최종 차트 생성 예약")
                # 실시간 차트 업데이트 대신 테스트 완료 후 최종 차트 표시
                if hasattr(self, 'chart_handler'):
                    # UI 스레드에서 안전하게 실행하기 위해 after 사용
                    self.after(100, self._generate_final_charts)
                else:
                    self.update_charts_from_test_data()
            
            # 결과 메시지 표시 (None이 아닌 경우만)
            if success is not None:
                if success:
                    # 테스트 성공 시 HTML/Excel 버튼만 활성화 (차트 버튼은 차트 생성 완료 후 활성화)
                    if hasattr(self, 'button_manager') and self.button_manager:
                        self.button_manager.enable_report_buttons()
                        logger.info("🔴 테스트 완료 - HTML/Excel 버튼 활성화, 차트 버튼은 차트 생성 완료 후 활성화")
                    
                    self._show_custom_messagebox("테스트 완료", f"테스트가 성공적으로 완료되었습니다.\n\n{message}", "info")
                else:
                    self._show_custom_messagebox("테스트 실패", f"테스트가 실패했습니다.\n\n{message}", "error")
                
        except Exception as e:
            logger.error(f"테스트 완료 처리 중 오류: {e}")

    def _generate_final_charts(self):
        """테스트 완료 후 최종 차트 생성 (UI 스레드에서 안전하게 실행)"""
        try:
            logger.info("최종 차트 생성 시작")
            
            # 시각화 탭이 비활성화되어 있어 차트 생성 생략
            logger.info("시각화 탭이 비활성화되어 있어 최종 차트 생성을 건너뜁니다")
            
        except Exception as e:
            logger.error(f"최종 차트 생성 오류: {e}")

    def update_status_message(self, message: str):
        """상태 메시지 업데이트"""
        logger.info(f"상태 업데이트: {message}")
        # 상태는 로그로만 기록 (UI 상태 레이블은 별도로 관리)

    def update_test_progress(self, current_step: int, total_steps: int, status_text: str = ""):
        """테스트 진행 상태 업데이트"""
        try:
            if hasattr(self, 'progress_manager'):
                # 총 단계 수가 변경된 경우 프로그래스바 재설정
                if total_steps != self.progress_manager.max_value:
                    self.progress_manager.max_value = total_steps
                    if self.progress_manager.progress_bar:
                        self.progress_manager.progress_bar.configure(maximum=total_steps)
                
                # 진행 상태 업데이트
                self.progress_manager.update_progress(current_step, status_text)
                
        except Exception as e:
            logger.error(f"테스트 진행 상태 업데이트 실패: {e}")

    def set_progress_indeterminate(self, text: str = "처리 중..."):
        """프로그래스바를 불확정 모드로 설정"""
        try:
            if hasattr(self, 'progress_manager'):
                self.progress_manager.set_indeterminate_mode(text)
        except Exception as e:
            logger.error(f"불확정 모드 설정 실패: {e}")

    def set_progress_determinate(self):
        """프로그래스바를 확정 모드로 설정"""
        try:
            if hasattr(self, 'progress_manager'):
                self.progress_manager.set_determinate_mode()
        except Exception as e:
            logger.error(f"확정 모드 설정 실패: {e}")

    def setup_fonts(self):
        """폰트 설정"""
        try:
            # 커스텀 Noto Sans KR 폰트 설정
            from src.utils.custom_font_setup import replace_arial_with_noto_sans_kr
            if replace_arial_with_noto_sans_kr():
                logger.info("✅ Noto Sans KR 폰트 설정 완료")
            else:
                # 기본 폰트 매니저 사용
                font_manager = get_font_manager()
                font_manager.apply_all_fonts(self)
                logger.info("✅ 기본 폰트 설정 완료")
        except Exception as e:
            logger.warning(f"폰트 설정 실패: {e}")
            # 기본 폰트 매니저 사용
            try:
                font_manager = get_font_manager()
                font_manager.apply_all_fonts(self)
                logger.info("✅ 대체 폰트 설정 완료")
            except Exception as e2:
                logger.error(f"대체 폰트 설정도 실패: {e2}")
    
    def setup_widget_styles(self):
        """위젯 스타일 설정 (배경색 등)"""
        try:
            style = ttk.Style()
            
            # 테마를 기본으로 설정
            try:
                style.theme_use('clam')  # clam 테마는 커스터마이징이 잘 됨
            except:
                try:
                    style.theme_use('alt')  # 대체 테마
                except:
                    pass  # 기본 테마 사용
            
            # Combobox 스타일 (흰색 배경 강제 적용)
            style.configure("White.TCombobox", 
                          fieldbackground="white",
                          background="white",
                          bordercolor="#d0d0d0",
                          arrowcolor="black",
                          focuscolor="none",
                          selectbackground="white",
                          selectforeground="black",
                          insertcolor="black")
            
            # Combobox의 내부 필드 스타일도 별도 설정
            style.map("White.TCombobox",
                     fieldbackground=[('readonly', 'white'),
                                    ('focus', 'white'),
                                    ('!focus', 'white')],
                     background=[('readonly', 'white'),
                               ('focus', 'white'),
                               ('!focus', 'white')],
                     selectbackground=[('readonly', 'white'),
                                     ('focus', '#e3f2fd'),
                                     ('!focus', 'white')])
            
            # Entry 스타일 (흰색 배경 강제 적용)
            style.configure("White.TEntry", 
                          fieldbackground="white",
                          background="white",
                          bordercolor="#d0d0d0",
                          focuscolor="none",
                          insertcolor="black",
                          selectbackground="#e3f2fd",
                          selectforeground="black")
            
            # Entry의 상태별 스타일 맵핑
            style.map("White.TEntry",
                     fieldbackground=[('focus', 'white'),
                                    ('!focus', 'white'),
                                    ('disabled', '#f0f0f0')],
                     background=[('focus', 'white'),
                               ('!focus', 'white'),
                               ('disabled', '#f0f0f0')])
            
            logger.info("✅ 위젯 스타일 설정 완료")
        except Exception as e:
            logger.warning(f"위젯 스타일 설정 실패: {e}")
    
    def setup_gui(self):
        """GUI 구성 요소 초기화"""
        # 메인 컨테이너 프레임 생성
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill="both", expand=True)
        
        # 메인 노트북 (탭 컨테이너) 생성
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 각 탭 생성 (GUIBuilder 사용)
        self.gui_builder.create_test_config_tab()
        # 시각화 탭 제거됨 (사용자 요청에 따라)
        self.gui_builder.create_report_tab()
        self.gui_builder.create_log_tab()
        
        # 상태바 생성
        self.gui_builder.create_status_bar()
        
        # 초기 버튼 상태 설정 (테스트 완료 전까지 리포트 버튼들 비활성화)
        if hasattr(self, 'button_manager') and self.button_manager:
            self.button_manager.disable_report_buttons()
            self.button_manager.disable_performance_graph_button()
            logger.info("초기 버튼 상태 설정 완료 - 리포트 버튼들 비활성화")
        
        logger.info("✅ GUI 구성 요소 초기화 완료")
    
    def setup_logging(self):
        """로깅 설정 (UIHelpers 사용)"""
        self.ui_helpers.setup_logging()
    
    def load_app_packages(self):
        """연결된 장치에서 설치된 앱 패키지 목록을 가져옵니다."""
        logger.info("앱 패키지 목록 로딩 시작")
        if not self.test_context.device_serial:
            logger.warning("DEVICE_SERIAL이 설정되지 않음")
            messagebox.showwarning("장치 없음", "ADB 장치가 연결되지 않았습니다.")
            return
        
        # 기존 목록 초기화 (Button은 별도 초기화 불필요)
        self.app_packages = []
        self.selected_app_package.set("앱 목록 로딩 중...")
        
        def _load_packages_thread():
            logger.info("앱 패키지 로딩 스레드 시작")
            try:
                if self.adb_client:
                    packages = self.adb_client.get_installed_packages()
                    if packages:
                        logger.info(f"총 {len(packages)}개의 패키지 발견")
                        self.after(100, lambda: self._update_package_list(packages))
                    else:
                        logger.error("패키지 목록 조회 실패")
                        self.after(100, lambda: messagebox.showerror("오류", "앱 패키지 목록을 가져오는 데 실패했습니다"))
                        self.after(100, lambda: self.selected_app_package.set("연결 실패"))
                else:
                    logger.error("ADB 클라이언트가 초기화되지 않음")
                    self.after(100, lambda: messagebox.showerror("오류", "ADB 클라이언트가 초기화되지 않았습니다"))
                    self.after(100, lambda: self.selected_app_package.set("클라이언트 오류"))
            except Exception as e:
                logger.error(f"앱 패키지 목록 로딩 중 오류: {e}")
                self.after(100, lambda: messagebox.showerror("오류", f"앱 패키지 목록 로딩 중 오류 발생: {e}"))
                self.after(100, lambda: self.selected_app_package.set("오류 발생"))
        
        threading.Thread(target=_load_packages_thread, daemon=True).start()

    def _update_package_list(self, packages):
        """메인 스레드에서 패키지 목록을 업데이트합니다."""
        logger.info(f"패키지 목록 업데이트 시작: {len(packages)}개 패키지")
        self.app_packages = packages
        
        if not packages:
            logger.warning("설치된 앱이 없음")
            messagebox.showinfo("정보", "장치에 설치된 앱이 없습니다.")
            self.selected_app_package.set("앱 없음")
            return
        
        try:
            if self.app_combobox:
                # 현재 선택된 패키지 기억
                current_selection = self.selected_app_package.get()
                logger.info(f"현재 선택된 패키지: {current_selection}")
                
                # 선택 복원 또는 기본값 설정 (Button은 패키지 목록을 내부에 저장하지 않음)
                if (current_selection and 
                    current_selection in self.app_packages and 
                    current_selection not in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", "업데이트 실패"]):
                    # 이전 선택 복원
                    self.selected_app_package.set(current_selection)
                    logger.info(f"이전 선택 패키지 복원: {current_selection}")
                else:
                    # 기본 선택 텍스트 설정
                    self.selected_app_package.set("테스트할 앱을 선택하세요")
                    logger.info("기본 선택 텍스트로 설정")
                
                logger.info(f"패키지 목록 업데이트 완료: {len(self.app_packages)}개 앱 로드됨")
            
        except Exception as e:
            logger.error(f"패키지 목록 업데이트 오류: {e}")
            messagebox.showerror("오류", f"패키지 목록 업데이트 중 오류가 발생했습니다: {e}")
            self.selected_app_package.set("업데이트 실패")
    
    def setup_console_handler(self):
        """콘솔 로그 핸들러 설정"""
        try:
            # 기존 핸들러가 있으면 제거
            if self.console_handler:
                # 모든 로거에서 제거
                for logger_name in ['', 'src', 'src.ui', 'src.core', 'src.utils']:
                    target_logger = logging.getLogger(logger_name)
                    if self.console_handler in target_logger.handlers:
                        target_logger.removeHandler(self.console_handler)
            
            # 새 핸들러 생성
            class ConsoleLogHandler(logging.Handler):
                def __init__(self, main_app):
                    super().__init__()
                    self.main_app = main_app
                
                def emit(self, record):
                    try:
                        msg = self.format(record)
                        # 모든 로그를 버퍼에 저장
                        self.main_app.add_console_log_to_buffer(msg)
                    except:
                        pass
            
            self.console_handler = ConsoleLogHandler(self)
            self.console_handler.setLevel(logging.DEBUG)  # DEBUG 레벨로 변경하여 더 많은 로그 수집
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            self.console_handler.setFormatter(formatter)
            
            # 여러 로거에 핸들러 추가 (더 포괄적인 로그 수집)
            loggers_to_add = [
                logging.getLogger(),  # 루트 로거
                logging.getLogger('src'),
                logging.getLogger('src.ui'),
                logging.getLogger('src.core'),
                logging.getLogger('src.utils'),
                logging.getLogger('__main__')
            ]
            
            for target_logger in loggers_to_add:
                if self.console_handler not in target_logger.handlers:
                    target_logger.addHandler(self.console_handler)
            
            logger.info("콘솔 로그 핸들러 설정 완료 - 포괄적 로그 수집 활성화")
        except Exception as e:
            logger.error(f"콘솔 로그 핸들러 설정 실패: {e}")
    
    def add_console_log_to_buffer(self, message):
        """콘솔 로그를 버퍼에 추가"""
        try:
            # 메시지가 이미 있는지 확인 (중복 방지)
            if message and message not in self.console_log_buffer[-10:]:  # 최근 10개와 비교하여 중복 방지
                self.console_log_buffer.append(message)
                
                # 버퍼 크기 제한
                if len(self.console_log_buffer) > self.max_buffer_lines:
                    self.console_log_buffer = self.console_log_buffer[-self.max_buffer_lines:]
                
                # 콘솔이 열려있으면 실시간 표시
                if hasattr(self, 'console_visible') and self.console_visible and hasattr(self, 'console_text') and self.console_text:
                    self.display_log_in_console(message)
                    
        except Exception as e:
            # 버퍼링 실패해도 프로그램은 계속 실행
            pass
    
    def toggle_console_log(self):
        """콘솔 로그 창 토글"""
        if self.console_visible:
            self.hide_console()
        else:
            self.show_console()
    
    def show_console(self):
        """콘솔 로그 창 표시"""
        if self.console_visible:
            return
            
        # 창 크기를 확장
        current_geometry = self.geometry()
        width_match = current_geometry.split('x')[0]
        height_match = current_geometry.split('x')[1].split('+')[0] if '+' in current_geometry else current_geometry.split('x')[1]
        
        self.original_width = int(width_match)
        new_width = self.original_width + 500  # 500px 확장
        
        # 창 크기 변경
        self.geometry(f"{new_width}x{height_match}")
        
        # 콘솔 프레임 생성
        self.console_frame = ttk.LabelFrame(self.main_container, text="콘솔 로그", padding="5")
        self.console_frame.pack(side="right", fill="both", expand=False, padx=5, pady=5)
        self.console_frame.config(width=480)
        
        # 콘솔 텍스트 위젯 생성
        console_text_frame = ttk.Frame(self.console_frame)
        console_text_frame.pack(fill="both", expand=True)
        
        # 텍스트 위젯과 스크롤바
        self.console_text = tk.Text(console_text_frame, wrap=tk.WORD, 
                                   font=("Consolas", 9), bg="black", fg="white",
                                   state=tk.DISABLED)
        
        # 색상 태그 설정
        self.console_text.tag_config("red", foreground="#FF6B6B")
        self.console_text.tag_config("orange", foreground="#FFD93D")
        self.console_text.tag_config("blue", foreground="#6BCF7F")
        self.console_text.tag_config("black", foreground="white")
        
        console_scrollbar = ttk.Scrollbar(console_text_frame, orient="vertical", 
                                        command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scrollbar.set)
        
        self.console_text.pack(side="left", fill="both", expand=True)
        console_scrollbar.pack(side="right", fill="y")
        
        # 콘솔 제어 버튼들
        console_controls = ttk.Frame(self.console_frame)
        console_controls.pack(side="bottom", fill="x", pady=5)
        
        ttk.Button(console_controls, text="새로고침", command=self.refresh_console_logs).pack(side="left", padx=2)
        ttk.Button(console_controls, text="파일 로그 보기", command=self.load_existing_logs).pack(side="left", padx=2)
        ttk.Button(console_controls, text="지우기", command=self.clear_console).pack(side="left", padx=2)
        ttk.Button(console_controls, text="맨 아래로", command=self.scroll_to_bottom).pack(side="left", padx=2)
        ttk.Button(console_controls, text="숨기기", command=self.hide_console).pack(side="right", padx=2)
        
        self.console_visible = True
        
        # 버퍼에 있는 모든 로그를 콘솔에 표시
        self.load_buffered_logs()
        
        logger.info("콘솔 로그 창이 열렸습니다")

    def load_buffered_logs(self):
        """버퍼에 있는 모든 로그들을 콘솔에 표시"""
        if not self.console_text:
            logger.warning("콘솔 텍스트 위젯이 없습니다")
            return
            
        try:
            logger.info(f"콘솔 로그 로드 시작 - 버퍼에 {len(self.console_log_buffer)}개 로그")
            
            self.console_text.config(state='normal')
            self.console_text.delete(1.0, tk.END)  # 기존 내용 지우기
            
            # 버퍼에 있는 모든 로그 표시
            if self.console_log_buffer:
                self.console_text.insert(tk.END, f"=== 현재 세션 로그 ({len(self.console_log_buffer)}개) ===\n")
                
                # 모든 버퍼 로그를 순서대로 표시
                for i, log_message in enumerate(self.console_log_buffer):
                    # 로그 레벨에 따른 색상 적용
                    if "ERROR" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "red")
                    elif "WARNING" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "orange")
                    elif "INFO" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "blue")
                    else:
                        self.console_text.insert(tk.END, log_message + "\n")
                
                self.console_text.insert(tk.END, f"\n=== 총 {len(self.console_log_buffer)}개 로그 로드 완료 ===\n")
            else:
                self.console_text.insert(tk.END, "INFO - 현재 세션에 표시할 로그가 없습니다.\n")
                self.console_text.insert(tk.END, "INFO - 테스트를 실행하면 실시간 로그가 여기에 표시됩니다.\n")
                self.console_text.insert(tk.END, "TIP - 로그가 수집되지 않는다면 '파일 로그 보기'를 시도해보세요.\n")
            
            self.console_text.config(state='disabled')
            self.console_text.see(tk.END)
            
            logger.info(f"콘솔 로그 로드 완료 - {len(self.console_log_buffer)}개 로그 표시")
            
        except Exception as e:
            logger.error(f"버퍼된 로그 로드 실패: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            try:
                self.console_text.config(state='normal')
                self.console_text.insert(tk.END, f"로그 로드 오류: {e}\n")
                self.console_text.config(state='disabled')
            except:
                pass
    
    def hide_console(self):
        """콘솔 로그 창 숨기기"""
        if not self.console_visible:
            return
            
        # 로그 핸들러는 제거하지 않고 유지 (버퍼링 지속)
        
        # 콘솔 프레임 제거
        if self.console_frame:
            self.console_frame.destroy()
            self.console_frame = None
            self.console_text = None
        
        # 창 크기를 원래대로 복원
        current_geometry = self.geometry()
        height_match = current_geometry.split('x')[1].split('+')[0] if '+' in current_geometry else current_geometry.split('x')[1]
        
        self.geometry(f"{self.original_width}x{height_match}")
        
        self.console_visible = False
        logger.info("콘솔 로그 창이 닫혔습니다 - 로그 버퍼링은 계속됩니다")
    
    def clear_console(self):
        """콘솔 로그 지우기 (버퍼도 함께 지움)"""
        # 콘솔 텍스트 위젯 지우기
        if self.console_text:
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete(1.0, tk.END)
            self.console_text.config(state=tk.DISABLED)
        
        # 버퍼도 지우기
        self.console_log_buffer.clear()
        logger.info("콘솔 로그와 버퍼가 지워졌습니다")
    
    def scroll_to_bottom(self):
        """콘솔 로그를 맨 아래로 스크롤"""
        if self.console_text:
            self.console_text.see(tk.END)
    
    def refresh_console_logs(self):
        """콘솔 로그 새로고침 - 현재 세션의 모든 로그 표시"""
        try:
            if not self.console_text:
                logger.warning("콘솔 텍스트 위젯이 없습니다")
                return
            
            logger.info(f"콘솔 새로고침 시작 - 버퍼에 {len(self.console_log_buffer)}개 로그")
            
            # 콘솔 지우기
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete(1.0, tk.END)
            
            # 현재 세션의 모든 버퍼 로그 표시
            if self.console_log_buffer:
                self.console_text.insert(tk.END, f"=== 현재 세션 로그 ({len(self.console_log_buffer)}개) ===\n")
                
                # 모든 버퍼 로그를 순서대로 표시
                for i, log_message in enumerate(self.console_log_buffer):
                    # 로그 레벨에 따른 색상 적용
                    if "ERROR" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "red")
                    elif "WARNING" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "orange")
                    elif "INFO" in log_message:
                        self.console_text.insert(tk.END, log_message + "\n", "blue")
                    else:
                        self.console_text.insert(tk.END, log_message + "\n")
                
                self.console_text.insert(tk.END, f"\n=== 총 {len(self.console_log_buffer)}개 로그 표시 완료 ===\n")
            else:
                self.console_text.insert(tk.END, "INFO - 현재 세션에 표시할 로그가 없습니다.\n")
                self.console_text.insert(tk.END, "INFO - 테스트를 실행하면 실시간 로그가 여기에 표시됩니다.\n")
                self.console_text.insert(tk.END, "INFO - 로그가 수집되지 않는 경우 '파일 로그 보기'를 사용해보세요.\n")
            
            self.console_text.config(state=tk.DISABLED)
            self.console_text.see(tk.END)
            
            logger.info(f"콘솔 로그 새로고침 완료 - {len(self.console_log_buffer)}개 로그 표시")
            
        except Exception as e:
            logger.error(f"콘솔 로그 새로고침 실패: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            if self.console_text:
                try:
                    self.console_text.config(state=tk.NORMAL)
                    self.console_text.insert(tk.END, f"새로고침 오류: {e}\n")
                    self.console_text.config(state=tk.DISABLED)
                except:
                    pass
    
    def load_existing_logs(self):
        """monkey_test.log 파일에서 최근 로그들을 로드 (최적화된 버전)"""
        try:
            from src.config import LOGS_DIR
            import os
            from pathlib import Path
            
            # EXE 환경에서 로그 파일을 찾기 위한 여러 경로 시도
            possible_log_paths = []
            
            # 1. 기본 config 경로
            possible_log_paths.append(LOGS_DIR / "monkey_test.log")
            
            # 2. EXE 실행 파일과 같은 위치의 logs 폴더
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
                possible_log_paths.append(exe_dir / "logs" / "monkey_test.log")
                possible_log_paths.append(exe_dir / "monkey_test.log")
                
            # 3. 실행 디렉토리의 logs 폴더
            current_dir = Path(os.getcwd())
            possible_log_paths.append(current_dir / "logs" / "monkey_test.log")
            possible_log_paths.append(current_dir / "monkey_test.log")
            
            # 4. 사용자 AppData 폴더
            user_data_dir = Path.home() / "AppData" / "Local" / "MonkeyTest" / "logs"
            possible_log_paths.append(user_data_dir / "monkey_test.log")
            
            monkey_log_file = None
            
            # 존재하는 첫 번째 로그 파일 찾기
            for log_path in possible_log_paths:
                self.display_log_in_console(f"INFO - 로그 파일 경로 확인: {log_path}")
                if log_path.exists():
                    monkey_log_file = log_path
                    self.display_log_in_console(f"INFO - 로그 파일 발견: {monkey_log_file}")
                    break
            
            if not monkey_log_file:
                self.display_log_in_console("WARNING - monkey_test.log 파일을 찾을 수 없습니다.")
                # 모든 가능한 디렉토리에서 *.log 파일 검색
                for log_dir in [path.parent for path in possible_log_paths if path.parent.exists()]:
                    try:
                        log_files = list(log_dir.glob("*.log"))
                        if log_files:
                            self.display_log_in_console(f"INFO - {log_dir}에 있는 로그 파일들: {[f.name for f in log_files]}")
                            # 가장 최근 로그 파일 사용
                            latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
                            self.display_log_in_console(f"INFO - 가장 최근 로그 파일 사용: {latest_log}")
                            monkey_log_file = latest_log
                            break
                    except Exception as e:
                        self.display_log_in_console(f"WARNING - {log_dir} 검색 실패: {e}")
                        continue
                
                if not monkey_log_file:
                    self.display_log_in_console("INFO - 어떤 로그 파일도 찾을 수 없습니다.")
                    return
                    self.display_log_in_console(f"ERROR - 로그 파일 목록 확인 실패: {e}")
                    return
            
            # 파일 크기 확인
            try:
                file_size = monkey_log_file.stat().st_size
                self.display_log_in_console(f"INFO - 로그 파일 크기: {file_size} bytes")
                
                # 파일이 너무 크면 최근 부분만 읽기
                if file_size > 1024 * 1024:  # 1MB 이상
                    self.display_log_in_console("WARNING - 로그 파일이 1MB 이상입니다. 최근 500줄만 표시합니다.")
                    max_lines = 500
                else:
                    max_lines = 1000  # 작은 파일도 최대 1000줄로 제한
                    
            except Exception as e:
                self.display_log_in_console(f"WARNING - 파일 크기 확인 실패: {e}")
                max_lines = 500  # 기본값
            
            # 최근 N줄만 읽어서 표시 (여러 인코딩 시도)
            encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1']
            
            for encoding in encodings_to_try:
                try:
                    with open(monkey_log_file, 'r', encoding=encoding, errors='ignore') as f:
                        lines = f.readlines()
                        # 최근 N줄만 선택
                        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
                        
                        self.display_log_in_console(f"INFO - {monkey_log_file.name}에서 최근 {len(recent_lines)}줄 로드 완료 (인코딩: {encoding})")
                        
                        # 구분선 추가
                        self.display_log_in_console("--- 파일 로그 시작 ---")
                        
                        # 최근 로그 내용 표시
                        for line in recent_lines:
                            line = line.strip()
                            if line:  # 빈 줄 제외
                                self.display_log_in_console(line)
                                
                        self.display_log_in_console("--- 파일 로그 끝 ---")
                    break  # 성공하면 루프 종료
                    
                except UnicodeDecodeError:
                    self.display_log_in_console(f"WARNING - {encoding} 인코딩으로 읽기 실패, 다음 인코딩 시도")
                    continue  # 다음 인코딩 시도
                except Exception as e:
                    if encoding == encodings_to_try[-1]:  # 마지막 시도에서도 실패
                        self.display_log_in_console(f"ERROR - 로그 파일 읽기 실패: {e}")
                    continue
                            
        except Exception as e:
            self.display_log_in_console(f"ERROR - 기존 로그 로드 실패: {e}")
            import traceback
            self.display_log_in_console(f"ERROR - 상세 오류: {traceback.format_exc()}")

    def display_log_in_console(self, message):
        """콘솔 텍스트 위젯에 로그 표시"""
        try:
            if not self.console_text:
                return
                
            # GUI 스레드에서 실행하도록 보장
            def update_console():
                try:
                    # 색상 설정
                    if "ERROR" in message:
                        color = "red"
                    elif "WARNING" in message:
                        color = "orange"
                    elif "INFO" in message:
                        color = "blue"
                    else:
                        color = "black"
                    
                    # 텍스트 추가 (위젯이 존재할 때만)
                    if self.console_text:
                        self.console_text.config(state='normal')
                        self.console_text.insert(tk.END, message + "\n", color)
                        self.console_text.config(state='disabled')
                        
                        # 자동 스크롤
                        self.console_text.see(tk.END)
                except:
                    pass
            
            # 메인 스레드에서 실행
            self.after_idle(update_console)
            
        except Exception as e:
            # 콘솔 표시 중 오류 발생해도 무시
            pass
    
    def on_closing(self):
        """창 닫기 이벤트 처리 - GUI 즉시 종료, 정리는 백그라운드에서"""
        try:
            logger.info("애플리케이션 종료 시작...")
            
            # 1. matplotlib atexit 콜백 제거 (RuntimeError 방지)
            try:
                import matplotlib._pylab_helpers
                # 기존 atexit 콜백이 있으면 제거
                if hasattr(matplotlib._pylab_helpers, 'Gcf'):
                    try:
                        atexit.unregister(matplotlib._pylab_helpers.Gcf.destroy_all)
                        logger.debug("matplotlib atexit 콜백 제거됨")
                    except (ValueError, AttributeError):
                        pass  # 등록되지 않았거나 이미 제거됨
            except (ImportError, AttributeError):
                pass
            
            # 2. 즉시 GUI 창 숨기기 (사용자에게 빠른 피드백)
            self.withdraw()
            self.update()
            
            # 3. 급하게 처리해야 할 것들만 즉시 처리
            if hasattr(self, 'test_running') and self.test_running:
                logger.info("실행 중인 테스트 즉시 중지...")
                if hasattr(self, 'monkey_runner') and self.monkey_runner:
                    self.monkey_runner.stop_test()
                self.test_running = False
            
            # 연결 모니터링 중지
            if hasattr(self, 'connection_monitoring'):
                self.stop_connection_monitoring()
            
            # 4. 백그라운드 정리를 위한 스레드 시작
            import threading
            cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
            cleanup_thread.start()
            
            # 5. GUI 즉시 종료
            try:
                self.quit()  # 메인루프 종료
            except:
                pass
            
            try:
                self.destroy()  # 윈도우 파괴
            except:
                pass
                
            # 6. 백그라운드 정리가 완료될 때까지 잠시 대기 (최대 2초)
            cleanup_thread.join(timeout=2.0)
            
        except Exception as e:
            logger.error(f"애플리케이션 종료 중 오류: {e}")
            try:
                self.quit()
            except:
                pass
            try:
                self.destroy()
            except:
                pass
    
    def _background_cleanup(self):
        """백그라운드에서 실행되는 정리 작업"""
        try:
            logger.info("백그라운드 정리 작업 시작...")
            
            # MonkeyRunner 완전 정리
            if hasattr(self, 'monkey_runner') and self.monkey_runner:
                try:
                    logger.info("MonkeyRunner 백그라운드 정리 시작")
                    # 테스트 중지
                    self.monkey_runner.stop_test()
                    # 포그라운드 모니터링 강제 중지
                    self.monkey_runner.stop_foreground_monitoring()
                    # 모든 플래그 비활성화
                    self.monkey_runner.test_context.test_running = False
                    self.monkey_runner.logcat_active = False
                    self.monkey_runner.monitoring_active = False
                    logger.info("✅ MonkeyRunner 백그라운드 정리 완료")
                except Exception as e:
                    logger.warning(f"MonkeyRunner 정리 중 오류: {e}")
            
            # 백그라운드 스레드들 정리
            if hasattr(self, 'ui_helpers') and self.ui_helpers:
                try:
                    logger.debug("UI 헬퍼 정리 중...")
                    self.ui_helpers.stop()
                except Exception as e:
                    logger.debug(f"UI 헬퍼 정리 중 오류 (무시): {e}")
            
            # 성능 모니터링 중지
            if hasattr(self, 'test_context') and self.test_context:
                try:
                    # 성능 모니터링 관련 속성이 있으면 정리
                    if hasattr(self.test_context, 'monitoring_active'):
                        logger.debug("성능 모니터링 중지...")
                        self.test_context.monitoring_active = False
                    if hasattr(self.test_context, 'current_performance_data'):
                        self.test_context.current_performance_data = []
                except Exception as e:
                    logger.debug(f"성능 모니터링 정리 중 오류 (무시): {e}")
            
            # matplotlib 차트 정리 - 메인루프 종료 후에도 안전하게 정리
            try:
                logger.debug("matplotlib 차트 정리 중...")
                
                # 1. chart_handler의 차트들 정리 (GUI 요소가 있을 때만)
                if hasattr(self, 'chart_handler') and self.chart_handler:
                    try:
                        self.chart_handler.clear_existing_charts()
                    except Exception:
                        pass  # GUI가 이미 파괴된 경우 무시
                
                # 2. chart_generator의 figure들 정리
                if hasattr(self, 'chart_generator') and self.chart_generator:
                    try:
                        self.chart_generator.cleanup()
                    except Exception:
                        pass
                
                # 3. matplotlib 수동 정리 (백그라운드에서 안전)
                try:
                    import matplotlib
                    import matplotlib.pyplot as plt
                    
                    # 모든 figure 강제 닫기 (GUI 상태 체크 없이)
                    try:
                        plt.close('all')
                    except Exception:
                        pass
                    
                    # figure manager 수동 정리 (안전하게)
                    try:
                        from matplotlib._pylab_helpers import Gcf
                        # 각 manager를 개별적으로 안전하게 정리
                        managers_to_destroy = list(Gcf.get_all_fig_managers())
                        for manager in managers_to_destroy:
                            try:
                                # GUI 업데이트 없이 figure만 정리
                                if hasattr(manager, 'canvas') and hasattr(manager.canvas, 'figure'):
                                    plt.close(manager.canvas.figure)
                            except Exception:
                                pass  # 개별 manager 정리 실패는 무시
                        
                        # manager 딕셔너리 수동 클리어
                        try:
                            Gcf.figs.clear()
                        except Exception:
                            pass
                            
                    except (ImportError, AttributeError):
                        pass
                    except Exception:
                        pass
                        
                except ImportError:
                    pass
                except Exception as matplotlib_error:
                    logger.debug(f"matplotlib 백엔드 정리 중 오류 (무시): {matplotlib_error}")
                    
            except Exception as e:
                logger.debug(f"matplotlib 정리 중 오류 (무시): {e}")
            
            # 콘솔 핸들러 제거
            if hasattr(self, 'console_handler') and self.console_handler:
                try:
                    logger.debug("콘솔 핸들러 제거 중...")
                    root_logger = logging.getLogger()
                    root_logger.removeHandler(self.console_handler)
                except Exception as e:
                    logger.debug(f"콘솔 핸들러 정리 중 오류 (무시): {e}")
            
            logger.info("백그라운드 정리 작업 완료")
            
        except Exception as e:
            # 백그라운드 정리 중 오류는 로깅만 하고 프로그램 종료를 막지 않음
            try:
                logger.debug(f"백그라운드 정리 중 오류 (무시): {e}")
            except:
                pass  # 로거도 이미 정리되었을 수 있음

    def update_report_display(self):
        """리포트 표시 업데이트"""
        try:
            # 요약 탭 업데이트
            summary = self.test_context.current_test_report.get("summary", {})
            summary_text = f"""=== Monkey 테스트 요약 ===
• 테스트 대상: {summary.get('test_target', 'N/A')}
• 테스트 도구: {summary.get('test_tool', 'N/A')}
• 테스트 기간: {summary.get('test_period', 'N/A')}
• 테스트 설정: {summary.get('preset', 'N/A')}
• 총 이벤트 수: {summary.get('total_events', 'N/A')}
• 디바이스: {summary.get('device', 'N/A')}
• 연결 방식: {summary.get('connection_mode', 'N/A')}
• 결과 요약: {summary.get('result_summary', 'N/A')}
• 수행 시간: {summary.get('execution_time', '00분')}
"""
            
            # 요약 텍스트 업데이트
            if hasattr(self, 'summary_text') and self.summary_text:
                self.summary_text.config(state="normal")
                self.summary_text.delete(1.0, tk.END)
                self.summary_text.insert(1.0, summary_text)
                self.summary_text.config(state="disabled")
            
            # 상세 결과 탭 업데이트
            if hasattr(self, 'detail_tree') and self.detail_tree:
                # 기존 항목 제거
                for item in self.detail_tree.get_children():
                    self.detail_tree.delete(item)
                
                # 새 항목 추가
                details = self.test_context.current_test_report.get("details", [])
                for detail in details:
                    self.detail_tree.insert("", "end", values=(
                        detail.get("repeat", ""),
                        detail.get("time", ""),
                        detail.get("seed", ""),
                        detail.get("events", ""),
                        detail.get("crash", ""),
                        detail.get("anr", ""),
                        detail.get("timeout", ""),
                        detail.get("mem_peak", ""),
                        detail.get("cpu_peak", "")
                    ))
            
            # 이슈 탭 업데이트
            if hasattr(self, 'issue_text') and self.issue_text:
                issues_text = ""
                for issue in self.test_context.current_test_report.get("issues", []):
                    issues_text += f"• {issue}\n"
                
                if not issues_text:
                    issues_text = "생성된 개선 제안이 없습니다."
                
                self.issue_text.config(state="normal")
                self.issue_text.delete(1.0, tk.END)
                self.issue_text.insert(1.0, issues_text)
                self.issue_text.config(state="disabled")
            
            # 시각화 탭 업데이트 - 차트 생성 및 표시
            self.update_visualization_charts()
                
        except Exception as e:
            logger.error(f"리포트 표시 업데이트 오류: {e}")

    def update_visualization_charts(self):
        """차트 데이터 저장 및 성능그래프 보기 버튼 활성화"""
        try:
            logger.info("차트 데이터 처리 및 버튼 활성화 시작")
            
            # 테스트 결과 데이터 가져오기 (여러 방법 시도)
            details = []
            
            # 방법 1: 테스트 컨텍스트에서 가져오기
            if hasattr(self, 'test_context') and self.test_context:
                if hasattr(self.test_context, 'current_test_report') and self.test_context.current_test_report:
                    details = self.test_context.current_test_report.get("details", [])
                    logger.info(f"테스트 컨텍스트에서 데이터 발견: {len(details)}개")
            
            # 방법 2: monkey_runner에서 직접 가져오기  
            if not details and hasattr(self, 'monkey_runner') and self.monkey_runner:
                if hasattr(self.monkey_runner, 'test_context') and self.monkey_runner.test_context:
                    if hasattr(self.monkey_runner.test_context, 'current_test_report'):
                        details = self.monkey_runner.test_context.current_test_report.get("details", [])
                        logger.info(f"monkey_runner에서 데이터 발견: {len(details)}개")
            
            # 방법 3: 최근 테스트 결과 파일에서 가져오기 (fallback)
            if not details:
                logger.warning("메모리에서 데이터를 찾을 수 없습니다. 최근 테스트 결과 조회 시도")
                try:
                    # 최근 로그 파일에서 결과 파싱 시도
                    from pathlib import Path
                    log_dir = Path("logs")
                    if log_dir.exists():
                        recent_log = None
                        for log_file in log_dir.glob("monkey_test*.log"):
                            if recent_log is None or log_file.stat().st_mtime > recent_log.stat().st_mtime:
                                recent_log = log_file
                        
                        if recent_log:
                            logger.info(f"최근 로그 파일에서 결과 파싱 시도: {recent_log}")
                            # 간단한 로그 파싱으로 데이터 복구
                            details = self._parse_test_results_from_log(recent_log)
                            if details:
                                logger.info(f"로그에서 복구된 데이터: {len(details)}개")
                except Exception as e:
                    logger.warning(f"로그 파일 파싱 실패: {e}")
            
            if not details:
                logger.warning("표시할 테스트 결과 데이터가 없습니다.")
                # 오류 상황에서도 버튼 활성화 시도
                if hasattr(self, 'button_manager') and self.button_manager:
                    self.button_manager.enable_performance_graph_button()
                    logger.info("데이터 없지만 성능그래프 보기 버튼 활성화 시도")
                return
            
            # 데이터 샘플 로깅
            if details:
                sample_detail = details[0]
                logger.info(f"샘플 데이터 키: {list(sample_detail.keys())}")
                logger.info(f"샘플 데이터: {sample_detail}")
            
            # 차트 핸들러를 사용하여 차트 생성
            if hasattr(self, 'chart_handler'):
                logger.info("차트 핸들러 발견, 차트 생성 시작")
                
                # ChartGenerator 직접 import 및 사용
                try:
                    from src.utils.chart_generator import TestResultData, ChartGenerator
                    chart_generator = ChartGenerator()
                    logger.info("ChartGenerator 직접 생성 성공")
                except ImportError as e:
                    logger.error(f"ChartGenerator import 실패: {e}")
                    # 기본 차트 데이터 생성으로 fallback
                    self._create_basic_chart_data(details)
                    if hasattr(self, 'button_manager') and self.button_manager:
                        self.button_manager.enable_performance_graph_button()
                        logger.info("ChartGenerator 없지만 기본 차트로 버튼 활성화")
                    return
                except Exception as e:
                    logger.error(f"ChartGenerator 생성 실패: {e}")
                    # 기본 차트 데이터 생성으로 fallback
                    self._create_basic_chart_data(details)
                    if hasattr(self, 'button_manager') and self.button_manager:
                        self.button_manager.enable_performance_graph_button()
                        logger.info("ChartGenerator 생성 실패하지만 기본 차트로 버튼 활성화")
                    return
                
                # 차트 생성기로 차트 생성
                test_results = []
                
                for i, detail in enumerate(details):
                    try:
                        # 실행 시간 처리 (초 단위로 변환)
                        time_value = detail.get('time', 0.0)
                        if isinstance(time_value, str):
                            # "12초" 형태에서 숫자만 추출
                            import re
                            time_match = re.search(r'(\d+(?:\.\d+)?)', str(time_value))
                            execution_time = float(time_match.group(1)) if time_match else 0.0
                        else:
                            execution_time = float(time_value) if time_value else 0.0
                        
                        # 메모리 값 처리 (MB 단위로 변환)
                        mem_peak = detail.get('mem_peak', 0.0)
                        if isinstance(mem_peak, str):
                            mem_peak = float(''.join(filter(str.isdigit, mem_peak)) or "0")
                        
                        # CPU 값 처리 (% 단위)
                        cpu_peak = detail.get('cpu_peak', 0.0)
                        if isinstance(cpu_peak, str):
                            cpu_peak = float(''.join(c for c in cpu_peak if c.isdigit() or c == '.') or "0")
                        
                        test_result = TestResultData(
                            repeat_number=i + 1,
                            execution_time=execution_time,
                            event_count=detail.get('events', 0),
                            crash_count=detail.get('crashes', 0),
                            anr_count=detail.get('anrs', 0),
                            timeout_count=detail.get('timeout', 0),
                            memory_peak=float(mem_peak),
                            cpu_peak=float(cpu_peak),
                            seed=detail.get('seed'),
                            timestamp=detail.get('timestamp'),
                            start_time=detail.get('start_time')  # 테스트 시작 시간 추가
                        )
                        test_results.append(test_result)
                        
                    except Exception as e:
                        logger.warning(f"테스트 결과 {i+1} 처리 중 오류: {e}")
                        continue
                
                if test_results:
                    # 차트 생성 (새로운 간단한 메서드 사용)
                    try:
                        # 실제 테스트에 사용된 앱 패키지명 가져오기 (우선순위: test_context > selected_app_package)
                        app_package = "Unknown Package"
                        
                        # 1. test_context에서 실제 테스트 패키지명 확인
                        if hasattr(self, 'test_context') and hasattr(self.test_context, 'app_package_name') and self.test_context.app_package_name:
                            app_package = self.test_context.app_package_name
                            logger.info(f"test_context에서 패키지명 가져옴: {app_package}")
                        
                        # 2. test_context가 없으면 현재 선택된 패키지명 사용
                        elif self.selected_app_package.get() and self.selected_app_package.get() not in ["테스트할 앱을 선택하세요", "앱 목록 로딩 중...", "연결 실패", "클라이언트 오류", "오류 발생", "앱 없음"]:
                            app_package = self.selected_app_package.get()
                            logger.info(f"selected_app_package에서 패키지명 가져옴: {app_package}")
                        
                        # 3. 테스트 결과 데이터에서 패키지명 확인 (details에 target_package가 있을 수 있음)
                        elif details and len(details) > 0:
                            first_detail = details[0]
                            if isinstance(first_detail, dict) and 'target_package' in first_detail:
                                app_package = first_detail['target_package']
                                logger.info(f"테스트 결과에서 패키지명 가져옴: {app_package}")
                        
                        logger.info(f"차트 생성에 사용할 최종 패키지명: {app_package}")
                        
                        # 성능 데이터 가져오기 (간단한 방식)
                        performance_data = []
                        
                        # 방법 1: test_context에서 성능 데이터 가져오기
                        if hasattr(self, 'test_context') and hasattr(self.test_context, 'current_performance_data'):
                            performance_data = self.test_context.current_performance_data or []
                            logger.info(f"test_context에서 성능 데이터 가져옴: {len(performance_data)}개")
                        
                        # 방법 2: monkey_runner에서 성능 데이터 가져오기
                        if not performance_data and hasattr(self, 'monkey_runner') and self.monkey_runner:
                            if hasattr(self.monkey_runner, 'test_context'):
                                runner_perf_data = getattr(self.monkey_runner.test_context, 'current_performance_data', [])
                                if runner_perf_data:
                                    performance_data = runner_perf_data
                                    logger.info(f"monkey_runner에서 성능 데이터 가져옴: {len(performance_data)}개")
                        
                        # 방법 3: test_results에서 성능 데이터 변환
                        if not performance_data and test_results:
                            logger.info("test_results에서 성능 데이터 변환")
                            for i, result in enumerate(test_results):
                                # 메모리와 CPU 값이 유효한 경우만 추가
                                if result.memory_peak > 0 or result.cpu_peak > 0:
                                    # 실제 시간 정보 사용 (start_time이나 timestamp가 있으면 활용)
                                    timestamp = f"테스트{i+1}"
                                    if hasattr(result, 'start_time') and result.start_time:
                                        timestamp = result.start_time
                                    elif hasattr(result, 'timestamp') and result.timestamp:
                                        timestamp = result.timestamp
                                    
                                    performance_data.append({
                                        'memory': result.memory_peak,
                                        'cpu': result.cpu_peak,
                                        'timestamp': timestamp,
                                        'repeat': result.repeat_number
                                    })
                        
                        # 방법 4: details에서 직접 성능 데이터 추출
                        if not performance_data and details:
                            logger.info("details에서 직접 성능 데이터 추출")
                            for i, detail in enumerate(details):
                                mem_val = 0
                                cpu_val = 0
                                
                                # 메모리 값 추출
                                mem_peak = detail.get('mem_peak', 0)
                                if isinstance(mem_peak, str) and mem_peak != "N/A":
                                    import re
                                    mem_match = re.search(r'(\d+(?:\.\d+)?)', str(mem_peak))
                                    mem_val = float(mem_match.group(1)) if mem_match else 0
                                elif isinstance(mem_peak, (int, float)):
                                    mem_val = float(mem_peak)
                                
                                # CPU 값 추출
                                cpu_peak = detail.get('cpu_peak', 0)
                                if isinstance(cpu_peak, str) and cpu_peak != "N/A":
                                    import re
                                    cpu_match = re.search(r'(\d+(?:\.\d+)?)', str(cpu_peak))
                                    cpu_val = float(cpu_match.group(1)) if cpu_match else 0
                                elif isinstance(cpu_peak, (int, float)):
                                    cpu_val = float(cpu_peak)
                                
                                if mem_val > 0 or cpu_val > 0:
                                    # 실제 시간 정보 사용 (start_time이 있으면 활용)
                                    timestamp = detail.get('repeat', f"테스트{i+1}")
                                    if 'start_time' in detail and detail['start_time'] != "N/A":
                                        timestamp = detail['start_time']
                                    elif 'timestamp' in detail and detail['timestamp']:
                                        timestamp = detail['timestamp']
                                    
                                    performance_data.append({
                                        'memory': mem_val,
                                        'cpu': cpu_val,
                                        'timestamp': timestamp,
                                        'repeat': i + 1
                                    })
                        
                        logger.info(f"최종 성능 데이터: {len(performance_data)}개")
                        if performance_data:
                            logger.info(f"성능 데이터 샘플: {performance_data[0]}")
                        
                        # 새로운 간단한 차트 생성 메서드 사용
                        charts = None
                        if performance_data:
                            charts = chart_generator.create_simple_performance_charts(performance_data, app_package)
                        
                        # 기존 방식으로 fallback
                        if not charts and test_results:
                            logger.info("간단한 차트 생성 실패, 기존 방식으로 재시도")
                            charts = chart_generator.create_performance_charts(test_results, app_package)
                        
                        logger.info(f"✅ 차트 생성 성공: {list(charts.keys()) if charts else '없음'}")
                    except Exception as e:
                        logger.error(f"차트 생성 실패: {e}")
                        # 차트 생성 실패 시 기본 차트 데이터로 fallback
                        self._create_basic_chart_data(details)
                        if hasattr(self, 'button_manager') and self.button_manager:
                            self.button_manager.enable_performance_graph_button()
                            logger.info("차트 생성 실패하지만 기본 차트로 버튼 활성화")
                        return
                    
                    # 메모리와 CPU 차트만 저장 (팝업에서 사용)
                    gui_charts = {}
                    if charts and 'memory' in charts:
                        gui_charts['memory'] = charts['memory']
                        logger.info(f"메모리 차트 데이터 타입: {type(charts['memory'])}")
                    
                    if charts and 'cpu' in charts:
                        gui_charts['cpu'] = charts['cpu']
                        logger.info(f"CPU 차트 데이터 타입: {type(charts['cpu'])}")
                    
                    # 현재 차트 데이터 저장 (팝업에서 사용하기 위해)
                    if gui_charts:
                        self.current_chart_data = gui_charts
                        logger.info(f"✅ 차트 데이터 저장 완료: {list(gui_charts.keys())}")
                        
                        # 성능그래프 보기 버튼 활성화
                        if hasattr(self, 'button_manager') and self.button_manager:
                            self.button_manager.enable_performance_graph_button()
                            logger.info("✅ 성능그래프 보기 버튼 활성화 완료")
                        
                        # 전체 차트는 HTML 보고서 생성용으로 컨텍스트에 저장
                        if hasattr(self, 'test_context') and hasattr(self.test_context, 'current_test_report'):
                            self.test_context.current_test_report['charts'] = charts
                            logger.info("✅ 전체 차트를 HTML 보고서용으로 저장 완료")
                        
                        logger.info("차트 데이터 처리 및 버튼 활성화 완료")
                    else:
                        logger.warning("생성된 차트가 비어있습니다. 기본 차트 데이터로 fallback")
                        # 차트가 비어있으면 기본 차트 데이터 생성
                        self._create_basic_chart_data(details)
                        if hasattr(self, 'button_manager') and self.button_manager:
                            self.button_manager.enable_performance_graph_button()
                            logger.info("기본 차트 데이터로 성능그래프 보기 버튼 활성화")
                else:
                    logger.warning("유효한 테스트 결과 데이터가 없습니다.")
                    # 데이터가 없어도 버튼은 활성화 (기본 메시지 표시용)
                    if hasattr(self, 'button_manager') and self.button_manager:
                        self.button_manager.enable_performance_graph_button()
                        logger.info("데이터 없지만 성능그래프 보기 버튼 활성화")
            else:
                logger.warning("차트 핸들러가 없습니다. 기본 차트 데이터 생성 시도")
                # 차트 핸들러가 없으면 기본 차트 데이터 생성
                if details:
                    self._create_basic_chart_data(details)
                
                if hasattr(self, 'button_manager') and self.button_manager:
                    self.button_manager.enable_performance_graph_button()
                    logger.info("차트 핸들러 없지만 성능그래프 보기 버튼 활성화")
            
        except Exception as e:
            logger.error(f"차트 데이터 처리 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            # 오류 발생 시에도 버튼은 활성화 (기존 데이터로라도 보여주기 위해)
            if hasattr(self, 'button_manager') and self.button_manager:
                self.button_manager.enable_performance_graph_button()
                logger.info("오류 발생했지만 성능그래프 보기 버튼 활성화")
    
    def _create_basic_chart_data(self, details):
        """기본 차트 데이터 생성 (chart_handler가 없을 때 사용)"""
        try:
            logger.info("기본 차트 데이터 생성 시작")
            
            # 메모리와 CPU 데이터 추출
            memory_data = []
            cpu_data = []
            labels = []
            
            for i, detail in enumerate(details):
                try:
                    # 메모리 값 처리
                    mem_peak = detail.get('mem_peak', 0.0)
                    if isinstance(mem_peak, str):
                        # 숫자만 추출
                        mem_match = re.search(r'(\d+(?:\.\d+)?)', str(mem_peak))
                        mem_value = float(mem_match.group(1)) if mem_match else 0.0
                    else:
                        mem_value = float(mem_peak) if mem_peak else 0.0
                    
                    # CPU 값 처리
                    cpu_peak = detail.get('cpu_peak', 0.0)
                    if isinstance(cpu_peak, str):
                        # 숫자와 소수점만 추출
                        cpu_match = re.search(r'(\d+(?:\.\d+)?)', str(cpu_peak))
                        cpu_value = float(cpu_match.group(1)) if cpu_match else 0.0
                    else:
                        cpu_value = float(cpu_peak) if cpu_peak else 0.0
                    
                    memory_data.append(mem_value)
                    cpu_data.append(cpu_value)
                    labels.append(f"반복 {i+1}")
                    
                    logger.info(f"데이터 {i+1}: 메모리={mem_value}MB, CPU={cpu_value}%")
                    
                except Exception as e:
                    logger.warning(f"데이터 {i+1} 처리 중 오류: {e}")
                    memory_data.append(0.0)
                    cpu_data.append(0.0)
                    labels.append(f"반복 {i+1}")
            
            # 기본 차트 데이터 구조 생성
            basic_chart_data = {
                'memory': {
                    'data': memory_data,
                    'labels': labels,
                    'title': '메모리 사용량 (MB)',
                    'ylabel': '메모리 (MB)'
                },
                'cpu': {
                    'data': cpu_data,
                    'labels': labels,
                    'title': 'CPU 사용량 (%)',
                    'ylabel': 'CPU (%)'
                }
            }
            
            # 현재 차트 데이터 저장
            self.current_chart_data = basic_chart_data
            logger.info(f"✅ 기본 차트 데이터 생성 완료: 메모리 {len(memory_data)}개, CPU {len(cpu_data)}개")
            
        except Exception as e:
            logger.error(f"기본 차트 데이터 생성 오류: {e}")
            # 최소한의 더미 데이터라도 생성
            self.current_chart_data = {
                'memory': {'data': [0], 'labels': ['데이터 없음'], 'title': '메모리 사용량', 'ylabel': '메모리 (MB)'},
                'cpu': {'data': [0], 'labels': ['데이터 없음'], 'title': 'CPU 사용량', 'ylabel': 'CPU (%)'}
            }
            logger.info("더미 차트 데이터 생성")
    def update_charts_from_test_data(self):
        """테스트 완료 후 차트 데이터 업데이트"""
        try:
            # 테스트 컨텍스트에서 차트 데이터 확인
            if hasattr(self.test_context, 'current_test_report') and self.test_context.current_test_report:
                # charts 키에서 올바른 차트 데이터 가져오기 (chart_generator에서 생성된 것)
                chart_data = self.test_context.current_test_report.get('charts')
                
                if chart_data and isinstance(chart_data, dict):
                    logger.info(f"올바른 차트 데이터 발견: {list(chart_data.keys())}")
                    
                    # GUI용 차트 필터링 (메모리와 CPU만)
                    gui_charts = {}
                    if 'memory' in chart_data and isinstance(chart_data['memory'], dict):
                        gui_charts['memory'] = chart_data['memory']
                        logger.info("메모리 차트를 GUI용으로 선택")
                    if 'cpu' in chart_data and isinstance(chart_data['cpu'], dict):
                        gui_charts['cpu'] = chart_data['cpu']
                        logger.info("CPU 차트를 GUI용으로 선택")
                    
                    # 메모리와 CPU 차트 데이터를 팝업용으로 저장
                    if gui_charts:
                        # 현재 차트 데이터 저장 (팝업에서 사용하기 위해)
                        self.current_chart_data = gui_charts
                        logger.info(f"팝업용 차트 데이터 저장 완료: {list(gui_charts.keys())}")
                        
                        # 성능그래프 보기 버튼 활성화
                        if hasattr(self, 'button_manager') and self.button_manager:
                            self.button_manager.enable_performance_graph_button()
                            self.button_manager.enable_report_buttons()
                            logger.info("성능그래프 및 리포트 버튼 활성화 완료")
                    else:
                        logger.warning("표시할 GUI 차트가 없습니다 (메모리, CPU 차트 없음)")
                        # 차트가 없어도 버튼은 활성화 (기본 메시지 표시용)
                        if hasattr(self, 'button_manager') and self.button_manager:
                            self.button_manager.enable_performance_graph_button()
                            self.button_manager.enable_report_buttons()
                            logger.info("차트 없지만 성능그래프 및 리포트 버튼 활성화")
                else:
                    logger.info("올바른 차트 데이터가 없습니다. 기본 차트 생성을 시도합니다.")
                    # 기존 방식으로 차트 생성 시도
                    self.update_visualization_charts()
            else:
                logger.warning("테스트 리포트 데이터가 없습니다.")
                # 데이터가 없어도 버튼은 활성화 시도
                if hasattr(self, 'button_manager') and self.button_manager:
                    self.button_manager.enable_performance_graph_button()
                    self.button_manager.enable_report_buttons()
                    logger.info("데이터 없지만 성능그래프 및 리포트 버튼 활성화 시도")
                
        except Exception as e:
            logger.error(f"차트 데이터 업데이트 중 오류: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")

    def view_html_report(self):
        """HTML 리포트 보기"""
        try:
            if not self.test_context.current_test_report.get("details"):
                messagebox.showinfo("정보", "생성할 테스트 리포트가 없습니다. 먼저 테스트를 실행해주세요.")
                return
            
            if hasattr(self, 'report_generator') and self.report_generator:
                # 1. 파일 저장 위치 선택
                from tkinter import filedialog
                
                # 패키지명을 포함한 파일명 생성
                package_name = ""
                if hasattr(self, 'test_context') and self.test_context.app_package_name:
                    # 파일명에 사용할 수 있도록 점을 언더스코어로 변경
                    safe_package_name = self.test_context.app_package_name.replace('.', '_')
                    package_name = f"_{safe_package_name}"
                elif self.selected_app_package.get() and self.selected_app_package.get() != "테스트할 앱을 선택하세요":
                    # 파일명에 사용할 수 있도록 점을 언더스코어로 변경
                    safe_package_name = self.selected_app_package.get().replace('.', '_')
                    package_name = f"_{safe_package_name}"
                
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".html",
                    filetypes=[("HTML files", "*.html")],
                    initialfile=f"Monkey_Report{package_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    title="HTML 리포트 저장 위치 선택"
                )
                
                if not file_path:
                    return  # 사용자가 취소한 경우
                
                # 2. HTML 파일 생성
                if self.report_generator.save_html_report_to_path(file_path):
                    # 3. 브라우저에서 열지 묻는 확인 팝업
                    result = messagebox.askyesno(
                        "HTML 파일 저장 완료", 
                        f"HTML 리포트가 저장되었습니다.\n{file_path}\n\n브라우저에서 열까요?",
                        icon="question"
                    )
                    
                    if result:  # 사용자가 "예"를 선택한 경우
                        try:
                            import webbrowser
                            import os
                            abs_path = os.path.abspath(file_path)
                            
                            # Windows에서는 기본 브라우저로 열기
                            import sys
                            if sys.platform.startswith('win'):
                                try:
                                    os.startfile(abs_path)
                                except Exception as e:
                                    logger.warning(f"os.startfile 실패, webbrowser 사용: {e}")
                                    webbrowser.open(f"file:///{abs_path.replace(os.sep, '/')}")
                            else:
                                webbrowser.open(f"file:///{abs_path.replace(os.sep, '/')}")
                                
                            logger.info(f"브라우저에서 HTML 리포트 열기 완료: {abs_path}")
                        except Exception as e:
                            logger.error(f"브라우저 열기 실패: {e}")
                            messagebox.showerror("브라우저 열기 실패", f"브라우저에서 파일을 열 수 없습니다:\n{e}")
                else:
                    messagebox.showerror("오류", "HTML 리포트 생성에 실패했습니다.")
            else:
                messagebox.showwarning("경고", "리포트 생성기가 초기화되지 않았습니다.")
        except Exception as e:
            logger.error(f"HTML 리포트 보기 오류: {e}")
            messagebox.showerror("오류", f"HTML 리포트 보기 중 오류가 발생했습니다: {e}")

    def export_to_excel(self):
        """엑셀 내보내기"""
        try:
            if not self.test_context.current_test_report.get("details"):
                messagebox.showinfo("정보", "내보낼 데이터가 없습니다.")
                return
            
            if hasattr(self, 'report_generator') and self.report_generator:
                from tkinter import filedialog
                import datetime
                
                # 패키지명을 포함한 파일명 생성
                package_name = ""
                if hasattr(self, 'test_context') and self.test_context.app_package_name:
                    # 파일명에 사용할 수 있도록 점을 언더스코어로 변경
                    safe_package_name = self.test_context.app_package_name.replace('.', '_')
                    package_name = f"_{safe_package_name}"
                elif self.selected_app_package.get() and self.selected_app_package.get() != "테스트할 앱을 선택하세요":
                    # 파일명에 사용할 수 있도록 점을 언더스코어로 변경
                    safe_package_name = self.selected_app_package.get().replace('.', '_')
                    package_name = f"_{safe_package_name}"
                
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".xlsx",
                    filetypes=[("Excel files", "*.xlsx")],
                    initialfile=f"Monkey_Report{package_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                
                if file_path:
                    if self.report_generator.generate_excel_report(file_path):
                        messagebox.showinfo("내보내기 완료", f"리포트가 저장되었습니다: {file_path}")
                    else:
                        messagebox.showerror("오류", "엑셀 내보내기에 실패했습니다.")
            else:
                messagebox.showwarning("경고", "리포트 생성기가 초기화되지 않았습니다.")
        except Exception as e:
            logger.error(f"엑셀 내보내기 오류: {e}")
            messagebox.showerror("오류", f"엑셀 내보내기 중 오류가 발생했습니다: {e}")

    def _setup_app_icon(self):
        """애플리케이션 아이콘 설정"""
        try:
            import sys
            import os
            from PIL import Image, ImageTk
            
            icon_found = False
            
            # EXE 환경인지 확인
            if getattr(sys, 'frozen', False):
                # PyInstaller 환경
                possible_icon_paths = []
                if hasattr(sys, '_MEIPASS'):
                    possible_icon_paths.extend([
                        os.path.join(sys._MEIPASS, "icon.ico"),  # type: ignore
                        os.path.join(sys._MEIPASS, "icon.png")   # type: ignore
                    ])
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
                            logger.info(f"ICO 아이콘 적용 성공: {icon_path}")
                            icon_found = True
                            break
                        else:
                            # PNG 파일을 PIL로 로드하고 PhotoImage로 변환
                            pil_image = Image.open(icon_path)
                            # 아이콘 크기 조정 (32x32)
                            pil_image = pil_image.resize((32, 32), Image.Resampling.LANCZOS)
                            photo_image = ImageTk.PhotoImage(pil_image)
                            self.iconphoto(True, photo_image)  # type: ignore
                            # 참조 유지를 위해 인스턴스 변수에 저장
                            self._icon_image = photo_image
                            logger.info(f"PNG 아이콘 적용 성공: {icon_path}")
                            icon_found = True
                            break
                    except Exception as e:
                        logger.warning(f"아이콘 로드 실패 {icon_path}: {e}")
                        continue
            
            if not icon_found:
                logger.warning("아이콘 파일을 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"아이콘 설정 중 오류: {e}")

    def _show_custom_messagebox(self, title: str, message: str, msg_type: str = "info"):
        """아이콘이 포함된 커스텀 메시지박스"""
        try:
            # 새 창 생성
            dialog = tk.Toplevel(self)
            dialog.title(title)
            dialog.resizable(False, False)
            dialog.grab_set()  # 모달 다이얼로그로 설정
            
            # 창 크기 설정
            dialog_width = 320
            dialog_height = 150
            
            # 화면 중앙에 위치
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()
            x = (screen_width - dialog_width) // 2
            y = (screen_height - dialog_height) // 2
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            
            # 메인 창과 같은 아이콘 설정
            try:
                if hasattr(self, '_icon_image'):
                    dialog.iconphoto(True, self._icon_image)  # type: ignore
                else:
                    # 아이콘 파일 직접 로드
                    import sys
                    import os
                    from PIL import Image, ImageTk
                    
                    if getattr(sys, 'frozen', False):
                        # EXE 환경
                        if hasattr(sys, '_MEIPASS'):
                            icon_path = os.path.join(sys._MEIPASS, "icon.ico")  # type: ignore
                        else:
                            icon_path = os.path.join(os.path.dirname(sys.executable), "icon.ico")
                    else:
                        # 개발 환경
                        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                        icon_path = os.path.join(base_dir, "icon.ico")
                    
                    if os.path.exists(icon_path):
                        if icon_path.endswith('.ico'):
                            dialog.iconbitmap(icon_path)
                        else:
                            pil_image = Image.open(icon_path)
                            pil_image = pil_image.resize((32, 32), Image.Resampling.LANCZOS)
                            icon_img = ImageTk.PhotoImage(pil_image)
                            dialog.iconphoto(True, icon_img)  # type: ignore
            except Exception as e:
                logger.warning(f"다이얼로그 아이콘 설정 실패: {e}")
            
            # 메인 프레임
            main_frame = ttk.Frame(dialog, padding="15")
            main_frame.pack(fill="both", expand=True)
            
            # 메시지 타입에 따른 아이콘 텍스트
            icon_text = "ℹ️" if msg_type == "info" else "❌" if msg_type == "error" else "⚠️"
            
            # 아이콘과 메시지 프레임
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill="both", expand=True)
            
            # 아이콘 레이블
            icon_label = ttk.Label(content_frame, text=icon_text, font=("", 16))
            icon_label.pack(side="left", padx=(0, 10))
            
            # 메시지 레이블
            message_label = ttk.Label(content_frame, text=message, font=("", 9), wraplength=250)
            message_label.pack(side="left", fill="both", expand=True)
            
            # 버튼 프레임
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill="x", pady=(15, 0))
            
            # 확인 버튼
            ok_button = ttk.Button(button_frame, text="확인", command=dialog.destroy)
            ok_button.pack(anchor="center")
            
            # 포커스 설정
            ok_button.focus_set()
            
            # Enter 키로 닫기
            dialog.bind('<Return>', lambda e: dialog.destroy())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # 다이얼로그가 닫힐 때까지 대기
            self.wait_window(dialog)
            
        except Exception as e:
            logger.error(f"커스텀 메시지박스 오류: {e}")
            # 기본 messagebox로 fallback
            import tkinter.messagebox as messagebox
            if msg_type == "error":
                messagebox.showerror(title, message)
            elif msg_type == "warning":
                messagebox.showwarning(title, message)
            else:
                messagebox.showinfo(title, message)
    
    def _parse_test_results_from_log(self, log_file_path):
        """로그 파일에서 테스트 결과 데이터 파싱 (fallback)"""
        try:
            import re
            from pathlib import Path
            
            details = []
            with open(log_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 회차별 완료 로그 패턴 찾기
            # 예: "반복 1 완료 - 걸린 시간: 12.5초, 이벤트: 1000개, 크래시: 0회, ANR: 0회"
            pattern = r'반복\s+(\d+)\s+완료.*?걸린\s*시간:\s*([0-9.]+)초.*?이벤트:\s*(\d+)개.*?크래시:\s*(\d+)회.*?ANR:\s*(\d+)회'
            matches = re.findall(pattern, content)
            
            for i, match in enumerate(matches):
                repeat_num, time_sec, events, crashes, anrs = match
                
                # 기본 데이터 구조 생성
                detail = {
                    'repeat': f"{repeat_num}회차",
                    'time': f"{time_sec}초",
                    'events': int(events),
                    'crash': "❌ 1" if int(crashes) > 0 else "✅ 0",
                    'anr': "❌ 1" if int(anrs) > 0 else "✅ 0",
                    'timeout': "✅ 0",
                    'mem_peak': "N/A",  # 로그에서 메모리 정보가 없으면 기본값
                    'cpu_peak': "N/A",  # 로그에서 CPU 정보가 없으면 기본값
                    'seed': "N/A",
                    'start_time': "N/A"
                }
                
                details.append(detail)
            
            logger.info(f"로그 파싱 완료: {len(details)}개 회차 데이터 복구")
            return details
            
        except Exception as e:
            logger.error(f"로그 파싱 오류: {e}")
            return []
    
    def start_connection_monitoring(self):
        """연결 모니터링 시작"""
        if not self.connection_monitoring:
            self.connection_monitoring = True
            self.connection_monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
            self.connection_monitor_thread.start()
            logger.info("연결 모니터링 시작됨")
    
    def stop_connection_monitoring(self):
        """연결 모니터링 중지"""
        self.connection_monitoring = False
        if self.connection_monitor_thread:
            self.connection_monitor_thread = None
        logger.info("연결 모니터링 중지됨")
    
    def _monitor_connection(self):
        """연결 상태 모니터링 스레드"""
        import time
        
        while self.connection_monitoring:
            try:
                # 30초마다 연결 상태 확인 (GUI 간섭 최소화)
                time.sleep(30)
                
                if not self.connection_monitoring:
                    break
                
                # 실제 디바이스 목록을 확인하여 연결 상태 판단
                connected_devices = self.adb_client.get_connected_devices() if self.adb_client else []
                current_device_serial = getattr(self.adb_client, 'device_serial', None) if self.adb_client else None
                
                is_connected = len(connected_devices) > 0 and (
                    not current_device_serial or 
                    current_device_serial in connected_devices
                )
                
                # 연결 상태 변화 감지
                if self.last_connection_status and not is_connected:
                    # 연결이 끊어진 경우
                    logger.warning("🔌 디바이스 연결이 끊어졌습니다")
                    self.after(0, self._handle_connection_lost)
                    
                elif not self.last_connection_status and is_connected:
                    # 연결이 다시 된 경우
                    logger.info("🔌 디바이스가 다시 연결되었습니다")
                    
                    # 디바이스 시리얼이 변경되었을 수 있으므로 업데이트
                    if connected_devices and self.adb_client:
                        if current_device_serial and current_device_serial not in connected_devices:
                            # 새로운 디바이스가 연결된 경우
                            if hasattr(self.adb_client, 'set_device_serial'):
                                self.adb_client.set_device_serial(connected_devices[0])
                            else:
                                setattr(self.adb_client, 'device_serial', connected_devices[0])
                            logger.info(f"새 디바이스로 연결됨: {connected_devices[0]}")
                        elif not current_device_serial:
                            # 초기 연결인 경우
                            if hasattr(self.adb_client, 'set_device_serial'):
                                self.adb_client.set_device_serial(connected_devices[0])
                            else:
                                setattr(self.adb_client, 'device_serial', connected_devices[0])
                            logger.info(f"디바이스 연결됨: {connected_devices[0]}")
                    
                    self.after(0, self._handle_connection_restored)
                    self.reconnection_attempts = 0
                
                self.last_connection_status = is_connected
                
            except Exception as e:
                logger.debug(f"연결 모니터링 중 오류: {e}")
                time.sleep(10)  # 오류 시 더 긴 간격으로 재시도
    
    def _handle_connection_lost(self):
        """연결 끊어짐 처리"""
        try:
            # 디바이스 상태 라벨 업데이트 (오른쪽 연결 상태 표시)
            if hasattr(self, 'device_status_label') and self.device_status_label and self.device_status_label.winfo_exists():
                try:
                    self.device_status_label.config(text="⚠️ 연결 끊어짐", foreground="red")
                except tk.TclError:
                    logger.debug("device_status_label이 이미 파괴됨")
            
            # 패키지 상태 라벨은 업데이트하지 않음 (불필요한 메시지 제거)
            # if hasattr(self, 'package_status_label') and self.package_status_label and self.package_status_label.winfo_exists():
            #     try:
            #         self.package_status_label.config(text="⚠️ 연결 끊어짐", foreground="orange")
            #     except tk.TclError:
            #         logger.debug("package_status_label이 이미 파괴됨")
            
            # 진행 중인 테스트가 있으면 일시 중지
            if self.test_running:
                logger.warning("테스트 진행 중 연결 끊어짐 - 재연결을 시도합니다")
                # 테스트는 계속 진행하되, 재연결 시도
                self._attempt_reconnection()
            else:
                logger.info("연결이 끊어졌습니다. USB 케이블을 다시 연결해주세요.")
                
        except Exception as e:
            logger.error(f"연결 끊어짐 처리 중 오류: {e}")
    
    def _handle_connection_restored(self):
        """연결 복구 처리"""
        try:
            # 현재 선택된 패키지 보존 (재연결 전 상태 기억)
            preserved_package = self._get_current_valid_package_selection()
            
            # 디바이스 상태 라벨 업데이트 (안전성 검사)
            if hasattr(self, 'device_status_label') and self.device_status_label and self.device_status_label.winfo_exists():
                try:
                    connection_mode = self.adb_client.get_connection_mode() if self.adb_client else "알 수 없음"
                    self.device_status_label.config(text=f"✅ 연결됨 ({connection_mode})", foreground="green")
                except tk.TclError:
                    logger.debug("device_status_label이 이미 파괴됨")
            
            # 패키지 상태 라벨도 업데이트 (불필요한 새로고침 메시지 제거)
            # if hasattr(self, 'package_status_label') and self.package_status_label and self.package_status_label.winfo_exists():
            #     try:
            #         self.package_status_label.config(text="🔄 패키지 목록 새로고침 중...", foreground="blue")
            #     except tk.TclError:
            #         logger.debug("package_status_label이 이미 파괴됨")
            
            logger.info("✅ 디바이스 연결이 복구되었습니다")
            
            # 보존된 패키지 선택을 임시 저장
            if preserved_package:
                self._preserved_package_selection = preserved_package
                logger.info(f"재연결 전 패키지 선택 보존: {preserved_package}")
            
            # 패키지 목록 새로고침 (백그라운드에서)
            threading.Thread(target=self._refresh_packages_after_reconnection, daemon=True).start()
            
            # TestContext도 업데이트
            if hasattr(self, 'test_context') and self.test_context and self.adb_client:
                current_device_serial = getattr(self.adb_client, 'device_serial', None)
                if current_device_serial:
                    self.test_context.device_serial = current_device_serial
                    logger.info(f"TestContext 디바이스 시리얼 업데이트: {current_device_serial}")
            
        except Exception as e:
            logger.error(f"연결 복구 처리 중 오류: {e}")
    
    def _get_current_valid_package_selection(self):
        """현재 선택된 유효한 패키지명 반환 (없으면 None)"""
        try:
            if hasattr(self, 'selected_app_package') and self.selected_app_package:
                current_selection = self.selected_app_package.get()
                # 유효한 패키지 선택인지 확인
                if (current_selection and 
                    current_selection not in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", 
                                            "업데이트 실패", "재부팅 후 다시 연결해주세요", "앱 목록 로딩 중...", "클라이언트 오류"]):
                    return current_selection
        except Exception as e:
            logger.debug(f"현재 패키지 선택 확인 중 오류: {e}")
        return None
    
    def _attempt_reconnection(self):
        """재연결 시도"""
        if self.reconnection_attempts >= self.max_reconnection_attempts:
            logger.warning(f"최대 재연결 시도 횟수({self.max_reconnection_attempts})에 도달했습니다")
            return
        
        self.reconnection_attempts += 1
        logger.info(f"재연결 시도 {self.reconnection_attempts}/{self.max_reconnection_attempts}")
        
        # 백그라운드에서 재연결 시도
        threading.Thread(target=self._background_reconnection, daemon=True).start()
    
    def _background_reconnection(self):
        """백그라운드 재연결 작업"""
        import time
        
        try:
            # 잠시 대기 후 재연결 시도
            time.sleep(2)
            
            if self.adb_client:
                logger.info("ADB 서버 재시작 시도...")
                
                # ADB 서버 재시작
                self.adb_client.run_command("kill-server")
                time.sleep(1)
                self.adb_client.run_command("start-server")
                time.sleep(2)
                
                # 연결된 디바이스 확인
                connected_devices = self.adb_client.get_connected_devices()
                if connected_devices:
                    # 첫 번째 디바이스로 연결
                    if hasattr(self.adb_client, 'set_device_serial'):
                        self.adb_client.set_device_serial(connected_devices[0])
                    else:
                        setattr(self.adb_client, 'device_serial', connected_devices[0])
                    
                    logger.info(f"재연결 성공! 디바이스: {connected_devices[0]}")
                    self.after(0, self._handle_connection_restored)
                else:
                    logger.warning("재연결 실패 - 디바이스를 찾을 수 없습니다")
                    
        except Exception as e:
            logger.error(f"백그라운드 재연결 중 오류: {e}")
    
    def _refresh_packages_after_reconnection(self):
        """재연결 후 패키지 목록 새로고침 (오류 팝업 억제)"""
        try:
            import time
            time.sleep(2)  # 연결 안정화를 위해 더 긴 대기
            
            logger.info("재연결 후 패키지 목록 새로고침 시작...")
            
            if self.adb_client:
                packages = self.adb_client.get_installed_packages()
                if packages:
                    # 메인 스레드에서 UI 업데이트
                    self.after(0, lambda: self._update_package_list_silent(packages))
                    logger.info(f"재연결 후 패키지 목록 새로고침 완료: {len(packages)}개")
                else:
                    logger.warning("재연결 후 패키지 목록이 비어있습니다")
                    # 오류 팝업 대신 로그만 기록
                    self.after(0, lambda: self.selected_app_package.set("패키지 로딩 실패"))
            else:
                logger.error("ADB 클라이언트가 없습니다")
                
        except Exception as e:
            logger.error(f"재연결 후 패키지 새로고침 중 오류: {e}")
            # 오류 팝업 대신 로그만 기록
            self.after(0, lambda: self.selected_app_package.set("새로고침 실패"))
    
    def _update_package_list_silent(self, packages):
        """패키지 목록 업데이트 (오류 팝업 없이)"""
        try:
            logger.info(f"패키지 목록 자동 업데이트: {len(packages)}개 패키지")
            self.app_packages = packages
            
            if not packages:
                logger.warning("패키지 목록이 비어있음")
                self.selected_app_package.set("앱 없음")
                return
            
            # 보존된 패키지 선택 복원 시도
            preserved_package = getattr(self, '_preserved_package_selection', None)
            if (preserved_package and 
                preserved_package in self.app_packages):
                self.selected_app_package.set(preserved_package)
                logger.info(f"재연결 후 패키지 선택 복원: {preserved_package}")
                # 보존된 선택 제거
                if hasattr(self, '_preserved_package_selection'):
                    delattr(self, '_preserved_package_selection')
            else:
                self.selected_app_package.set("테스트할 앱을 선택하세요")
                logger.info("기본 선택 텍스트로 설정")
            
            logger.info(f"패키지 목록 자동 업데이트 완료: {len(self.app_packages)}개 앱")
            
        except Exception as e:
            logger.error(f"패키지 목록 자동 업데이트 오류: {e}")
            self.selected_app_package.set("업데이트 실패")
            
            # UI가 아직 존재하는지 확인
            if not hasattr(self, 'package_handler') or not self.package_handler:
                logger.warning("package_handler가 없어서 직접 로드 시도")
                self.after(0, self._safe_load_app_packages)
                return
            
            # 메인 스레드에서 패키지 새로고침 실행
            self.after(0, self._safe_refresh_packages)
            logger.info("패키지 새로고침 요청 완료")
            
            # 재연결 후 추가 처리
            try:
                self.after(0, self._safe_load_app_packages)
                logger.info("대체 패키지 로드 방법 사용")
            except Exception as nested_e:
                logger.error(f"대체 패키지 로드 중 오류: {nested_e}")
    
    def _safe_refresh_packages(self):
        """안전한 패키지 새로고침 (메인 스레드에서 실행)"""
        try:
            if hasattr(self, 'package_handler') and self.package_handler:
                # 재연결 후 조용한 새로고침 사용 (팝업 없이)
                self.package_handler.refresh_app_packages_quiet()
            else:
                self._safe_load_app_packages()
        except Exception as e:
            logger.error(f"안전한 패키지 새로고침 실패: {e}")
            self._safe_load_app_packages()
    
    def _safe_load_app_packages(self):
        """안전한 패키지 로드 (메인 스레드에서 실행)"""
        try:
            if hasattr(self, 'load_app_packages'):
                self.load_app_packages()
            else:
                logger.warning("load_app_packages 메서드가 없습니다")
        except Exception as e:
            logger.error(f"안전한 패키지 로드 실패: {e}")
    
    def _update_connection_status(self):
        """현재 연결 상태를 UI에 반영"""
        try:
            if hasattr(self, 'device_status_label') and self.device_status_label and self.adb_client:
                # 위젯이 아직 존재하는지 확인
                if self.device_status_label.winfo_exists():
                    try:
                        connection_mode = self.adb_client.get_connection_mode()
                        self.device_status_label.config(text=f"✅ 연결됨 ({connection_mode})", foreground="green")
                    except tk.TclError:
                        logger.debug("device_status_label이 이미 파괴됨")
                
        except Exception as e:
            logger.debug(f"연결 상태 업데이트 중 오류: {e}")  # 로그 레벨을 debug로 낮춤
    
    def add_gemini_logo(self, parent_frame):
        """Gemini AI 로고를 프리셋 프레임에 추가 (기존 크기 유지)"""
        try:
            # Gemini 로고 이미지 로드 (프로젝트 루트 경로)
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            logo_path = os.path.join(current_dir, "Gemini_logo.png")
            
            logger.info(f"🔍 Gemini 로고 경로 확인: {logo_path}")
            logger.info(f"🔍 파일 존재 여부: {os.path.exists(logo_path)}")
            
            if os.path.exists(logo_path):
                # 이미지 로드 및 크기 조정 (더 작게)
                original_image = Image.open(logo_path)
                logger.info(f"🔍 원본 이미지 크기: {original_image.size}")
                
                # 로고 크기를 더 작게 조정 (width=60, height는 비율 유지)
                width = 100
                height = int((width / original_image.width) * original_image.height)
                resized_image = original_image.resize((width, height), Image.Resampling.LANCZOS)
                
                # PhotoImage로 변환
                self.gemini_logo = ImageTk.PhotoImage(resized_image)
                
                # 기존 그리드 공간을 활용한 오버레이 방식
                logo_frame = ttk.Frame(parent_frame)
                # row=3~5 영역에 걸쳐서 오른쪽 끝에 배치
                logo_frame.grid(row=3, column=1, rowspan=3, sticky="se", padx=5, pady=5)
                
                # 로고 이미지 라벨
                logo_label = ttk.Label(logo_frame, image=self.gemini_logo)
                logo_label.pack()
                
                # "For Gemini Flash" 텍스트 추가 (로고 아래, 더 작은 폰트)
                text_label = ttk.Label(logo_frame, text="", 
                                     font=("Arial", 7), foreground="gray")
                text_label.pack()
                
                logger.info("✅ Gemini 로고 추가 완료 (오버레이 방식)")
            else:
                logger.warning(f"❌ Gemini 로고 파일을 찾을 수 없음: {logo_path}")
                
        except Exception as e:
            logger.error(f"❌ Gemini 로고 추가 실패: {e}")
            import traceback
            logger.error(f"스택 트레이스: {traceback.format_exc()}")


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('monkey_gui.log', encoding='utf-8')
        ]
    )
    
    try:
        app = MonkeyTestApp()
        app.mainloop()
    except Exception as e:
        logger.error(f"애플리케이션 실행 중 오류: {e}")
        logger.exception("상세 오류:")
