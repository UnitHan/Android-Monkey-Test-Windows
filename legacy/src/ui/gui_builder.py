#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI 구성요소 생성 핸들러
main_app.py에서 분리된 GUI 생성 관련 기능들
"""
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext

logger = logging.getLogger(__name__)

class GUIBuilder:
    """GUI 구성요소 생성을 담당하는 클래스"""
    
    def __init__(self, main_app):
        self.main_app = main_app
    
    def create_test_config_tab(self):
        """테스트 설정 탭 생성"""
        self.main_app.test_frame = ttk.Frame(self.main_app.notebook)
        self.main_app.notebook.add(self.main_app.test_frame, text="테스트 설정")
        
        # 메인 컨테이너를 좌우로 분할
        main_container = ttk.PanedWindow(self.main_app.test_frame, orient="horizontal")
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 좌측: 설정 영역
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=1)
        
        # 우측: 앱 정보 영역
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=1)
        
        self.create_device_section(left_frame)
        self.create_package_section(left_frame)
        self.create_test_settings_section(left_frame)
        self.create_control_buttons(left_frame)
        self.create_app_info_section(right_frame)
    
    def create_device_section(self, parent):
        """장치 연결 섹션"""
        device_frame = ttk.LabelFrame(parent, text="📱 장치 연결", padding=10)
        device_frame.pack(fill="x", padx=5, pady=5)
        
        self.main_app.device_status_label = ttk.Label(device_frame, text="연결 확인 중...", foreground="orange")
        self.main_app.device_status_label.pack(anchor="w")
        
        button_frame = ttk.Frame(device_frame)
        button_frame.pack(fill="x", pady=(5, 0))
        
        self.main_app.connect_button = ttk.Button(
            button_frame, 
            text="ADB 재연결", 
            command=self.main_app.ui_helpers.safe_method_call_wrapper('connect_adb')
        )
        self.main_app.connect_button.pack(side="left")
    
    def create_package_section(self, parent):
        """패키지 선택 섹션"""
        package_frame = ttk.LabelFrame(parent, text="📦 앱 패키지 선택", padding=10)
        package_frame.pack(fill="x", padx=5, pady=5)
        
        # 패키지 선택 영역
        selection_frame = ttk.Frame(package_frame)
        selection_frame.pack(fill="x")
        
        ttk.Label(selection_frame, text="패키지:").pack(side="left")
        
        self.main_app.package_combobox = ttk.Combobox(
            selection_frame, 
            state="readonly", 
            width=40
        )
        self.main_app.package_combobox.pack(side="left", padx=(5, 0), fill="x", expand=True)
        self.main_app.package_combobox.bind('<<ComboboxSelected>>', self.main_app.package_handler.on_package_selected)
        
        self.main_app.refresh_button = ttk.Button(
            selection_frame, 
            text="새로고침", 
            command=self.main_app.ui_helpers.safe_method_call_wrapper('refresh_app_packages')
        )
        self.main_app.refresh_button.pack(side="right", padx=(5, 0))
        
        # 패키지 상태 표시
        self.main_app.package_status_label = ttk.Label(
            package_frame, 
            text="ADB 연결 후 새로고침을 클릭하세요", 
            foreground="gray"
        )
        self.main_app.package_status_label.pack(anchor="w", pady=(5, 0))
    
    def create_test_settings_section(self, parent):
        """테스트 설정 섹션"""
        settings_frame = ttk.LabelFrame(parent, text="⚙️ 테스트 설정", padding=10)
        settings_frame.pack(fill="x", padx=5, pady=5)
        
        # 이벤트 수 설정
        event_frame = ttk.Frame(settings_frame)
        event_frame.pack(fill="x", pady=2)
        ttk.Label(event_frame, text="이벤트 수:").pack(side="left")
        self.main_app.event_count_var = tk.StringVar(value="1000")
        event_entry = ttk.Entry(event_frame, textvariable=self.main_app.event_count_var, width=10)
        event_entry.pack(side="right")
        
        # 반복 횟수 설정
        repeat_frame = ttk.Frame(settings_frame)
        repeat_frame.pack(fill="x", pady=2)
        ttk.Label(repeat_frame, text="반복 횟수:").pack(side="left")
        self.main_app.repeat_count_var = tk.StringVar(value="5")
        repeat_entry = ttk.Entry(repeat_frame, textvariable=self.main_app.repeat_count_var, width=10)
        repeat_entry.pack(side="right")
        
        # 시간 지연 설정
        delay_frame = ttk.Frame(settings_frame)
        delay_frame.pack(fill="x", pady=2)
        ttk.Label(delay_frame, text="이벤트 지연(ms):").pack(side="left")
        self.main_app.delay_var = tk.StringVar(value="100")
        delay_entry = ttk.Entry(delay_frame, textvariable=self.main_app.delay_var, width=10)
        delay_entry.pack(side="right")
        
        # 시드 설정
        seed_frame = ttk.Frame(settings_frame)
        seed_frame.pack(fill="x", pady=2)
        ttk.Label(seed_frame, text="시드 (선택):").pack(side="left")
        self.main_app.seed_var = tk.StringVar()
        seed_entry = ttk.Entry(seed_frame, textvariable=self.main_app.seed_var, width=10)
        seed_entry.pack(side="right")
    
    def create_control_buttons(self, parent):
        """제어 버튼 섹션"""
        control_frame = ttk.LabelFrame(parent, text="🎮 테스트 제어", padding=10)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        button_container = ttk.Frame(control_frame)
        button_container.pack(fill="x")
        
        self.main_app.start_button = ttk.Button(
            button_container,
            text="🚀 테스트 시작",
            command=self.main_app.ui_helpers.safe_method_call_wrapper('start_test_thread')
        )
        self.main_app.start_button.pack(side="left", padx=(0, 5))
        
        self.main_app.stop_button = ttk.Button(
            button_container,
            text="🛑 테스트 중지",
            command=self.main_app.ui_helpers.safe_method_call_wrapper('stop_test'),
            state="disabled"
        )
        self.main_app.stop_button.pack(side="left", padx=(0, 15))  # 프로그래스바 공간 확보
        
        # 프로그래스바 추가 (테스트 시작/중지 버튼 바로 옆)
        self.main_app.progress_container = self.main_app.progress_manager.create_progress_bar(button_container)
        
        self.main_app.export_button = ttk.Button(
            button_container,
            text="📊 결과 내보내기",
            command=self.main_app.ui_helpers.safe_method_call_wrapper('export_results')
        )
        self.main_app.export_button.pack(side="right")
        logger.info("제어 버튼 및 프로그래스바 생성 완료")
    
    def create_app_info_section(self, parent):
        """앱 정보 표시 섹션"""
        app_info_frame = ttk.LabelFrame(parent, text="📱 앱 정보", padding=10)
        app_info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 앱 아이콘과 기본 정보
        header_frame = ttk.Frame(app_info_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # 아이콘 표시용 레이블
        self.main_app.app_icon_label = ttk.Label(header_frame, text="📱", font=("Noto Sans KR", 32))
        self.main_app.app_icon_label.pack(side="left", padx=(0, 10))
        
        # 앱 기본 정보
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side="left", fill="both", expand=True)
        
        self.main_app.app_name_label = ttk.Label(info_frame, text="앱을 선택하세요", font=("Noto Sans KR", 14, "bold"))
        self.main_app.app_name_label.pack(anchor="w")
        
        self.main_app.app_developer_label = ttk.Label(info_frame, text="개발자: -", foreground="gray")
        self.main_app.app_developer_label.pack(anchor="w")
        
        self.main_app.app_category_label = ttk.Label(info_frame, text="카테고리: -", foreground="gray")
        self.main_app.app_category_label.pack(anchor="w")
        
        # 버전 정보
        version_frame = ttk.LabelFrame(app_info_frame, text="버전 정보", padding=5)
        version_frame.pack(fill="x", pady=(5, 0))
        
        self.main_app.app_version_label = ttk.Label(version_frame, text="📱 설치된 버전: -")
        self.main_app.app_version_label.pack(anchor="w")
        
        self.main_app.store_version_label = ttk.Label(version_frame, text="🛒 스토어 버전: -")
        self.main_app.store_version_label.pack(anchor="w")
        
        self.main_app.update_status_label = ttk.Label(version_frame, text="업데이트 상태: -", foreground="gray")
        self.main_app.update_status_label.pack(anchor="w")
    
    def create_visualization_tab(self):
        """시각화 탭 생성"""
        self.main_app.visualization_frame = ttk.Frame(self.main_app.notebook)
        self.main_app.notebook.add(self.main_app.visualization_frame, text="📊 시각화")
        
        # 스크롤 가능한 프레임 생성
        canvas = tk.Canvas(self.main_app.visualization_frame)
        scrollbar = ttk.Scrollbar(self.main_app.visualization_frame, orient="vertical", command=canvas.yview)
        self.main_app.scrollable_frame = ttk.Frame(canvas)
        
        self.main_app.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.main_app.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 초기 메시지
        initial_label = ttk.Label(
            self.main_app.scrollable_frame,
            text="테스트를 실행하면 성능 차트가 여기에 표시됩니다.",
            font=("Noto Sans KR", 12),
            foreground="gray"
        )
        initial_label.pack(pady=50)
    
    def create_log_tab(self):
        """로그 탭 생성"""
        self.main_app.log_frame = ttk.Frame(self.main_app.notebook)
        self.main_app.notebook.add(self.main_app.log_frame, text="📋 로그")
        
        # 로그 제어 버튼
        log_control_frame = ttk.Frame(self.main_app.log_frame)
        log_control_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(
            log_control_frame,
            text="로그 지우기",
            command=self.main_app.ui_helpers.clear_log
        ).pack(side="left")
        
        ttk.Button(
            log_control_frame,
            text="로그 저장",
            command=self.main_app.ui_helpers.save_log
        ).pack(side="left", padx=(5, 0))
        
        # 로그 표시 영역
        self.main_app.log_text = scrolledtext.ScrolledText(
            self.main_app.log_frame,
            wrap=tk.WORD,
            height=15,
            font=("Consolas", 9)
        )
        self.main_app.log_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
    
    def create_report_tab(self):
        """리포트 탭 생성"""
        self.main_app.report_frame = ttk.Frame(self.main_app.notebook)
        self.main_app.notebook.add(self.main_app.report_frame, text="리포트")
        
        # 리포트 버튼들
        button_frame = ttk.Frame(self.main_app.report_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(button_frame, text="HTML 보기", command=self.main_app.view_html_report).pack(side="left", padx=5)
        ttk.Button(button_frame, text="엑셀 내보내기", command=self.main_app.export_to_excel).pack(side="left", padx=5)
        
        # 리포트 노트북 (하위 탭들)
        self.main_app.report_notebook = ttk.Notebook(self.main_app.report_frame)
        self.main_app.report_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 요약 탭
        self.main_app.summary_tab = ttk.Frame(self.main_app.report_notebook)
        self.main_app.report_notebook.add(self.main_app.summary_tab, text="요약")
        self.main_app.summary_text = tk.Text(
            self.main_app.summary_tab, 
            wrap="word", 
            height=15, 
            font=("Inter", 10)
        )
        self.main_app.summary_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.main_app.summary_text.config(state="disabled")
        
        # 상세 결과 탭
        self.main_app.detail_tab = ttk.Frame(self.main_app.report_notebook)
        self.main_app.report_notebook.add(self.main_app.detail_tab, text="결과 상세")
        self.main_app.detail_tree = ttk.Treeview(
            self.main_app.detail_tab,
            columns=("repeat", "time", "seed", "events", "crash", "anr", "timeout", "mem_peak", "cpu_peak"),
            show="headings"
        )
        
        # 컬럼 헤더 설정
        self.main_app.detail_tree.heading("repeat", text="반복")
        self.main_app.detail_tree.heading("time", text="실행 시간")
        self.main_app.detail_tree.heading("seed", text="Seed")
        self.main_app.detail_tree.heading("events", text="이벤트 수")
        self.main_app.detail_tree.heading("crash", text="Crash")
        self.main_app.detail_tree.heading("anr", text="ANR")
        self.main_app.detail_tree.heading("timeout", text="Timeout")
        self.main_app.detail_tree.heading("mem_peak", text="메모리 피크")
        self.main_app.detail_tree.heading("cpu_peak", text="CPU 피크")
        
        # 컬럼 너비 설정
        self.main_app.detail_tree.column("repeat", width=50, anchor="center")
        self.main_app.detail_tree.column("time", width=100, anchor="center")
        self.main_app.detail_tree.column("seed", width=60, anchor="center")
        self.main_app.detail_tree.column("events", width=80, anchor="center")
        self.main_app.detail_tree.column("crash", width=60, anchor="center")
        self.main_app.detail_tree.column("anr", width=60, anchor="center")
        self.main_app.detail_tree.column("timeout", width=80, anchor="center")
        self.main_app.detail_tree.column("mem_peak", width=100, anchor="center")
        self.main_app.detail_tree.column("cpu_peak", width=80, anchor="center")
        self.main_app.detail_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 이슈 요약 탭
        self.main_app.issue_tab = ttk.Frame(self.main_app.report_notebook)
        self.main_app.report_notebook.add(self.main_app.issue_tab, text="이슈 요약 및 권고사항")
        self.main_app.issue_text = tk.Text(
            self.main_app.issue_tab,
            wrap="word",
            font=("Inter", 10)
        )
        self.main_app.issue_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.main_app.issue_text.config(state="disabled")
        
        # 시각화 탭 - 숨김 처리 (사용자 요청에 따라 제거)
        # self.main_app.visualization_tab = ttk.Frame(self.main_app.report_notebook)
        # self.main_app.report_notebook.add(self.main_app.visualization_tab, text="시각화")
        # ttk.Label(
        #     self.main_app.visualization_tab,
        #     text="시각화 기능은 HTML 리포트에서 제공됩니다.",
        #     font=("Inter", 12)
        # ).pack(pady=50)
    
    def create_status_bar(self):
        """상태바 생성"""
        self.main_app.status_frame = ttk.Frame(self.main_app)
        self.main_app.status_frame.pack(fill="x", side="bottom")
        
        self.main_app.status_label = ttk.Label(
            self.main_app.status_frame,
            text="준비 완료",
            relief="sunken",
            anchor="w"
        )
        self.main_app.status_label.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        self.main_app.progress_var = tk.DoubleVar()
        self.main_app.progress_bar = ttk.Progressbar(
            self.main_app.status_frame,
            variable=self.main_app.progress_var,
            maximum=100
        )
        self.main_app.progress_bar.pack(side="right", padx=5, pady=2)
