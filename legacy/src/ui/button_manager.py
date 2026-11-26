#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
버튼 영역 UI 컴포넌트
메인 앱의 모든 버튼들을 관리하는 분리된 컴포넌트
"""
import logging
from tkinter import ttk, messagebox
from typing import Optional

logger = logging.getLogger(__name__)

class ButtonManager:
    """메인 앱의 모든 버튼들을 관리하는 클래스"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        
        # 버튼 위젯들
        self.start_button: Optional[ttk.Button] = None
        self.refresh_button: Optional[ttk.Button] = None
        self.wireless_disconnect_button: Optional[ttk.Button] = None
        self.reboot_button: Optional[ttk.Button] = None
        self.performance_graph_button: Optional[ttk.Button] = None
        self.html_view_button: Optional[ttk.Button] = None
        self.excel_export_button: Optional[ttk.Button] = None
    
    def create_button_frame(self, parent_frame):
        """버튼 프레임 생성 (원본과 100% 동일한 배치)"""
        # 버튼 프레임
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill="x", pady=10)
        
        # 좌측: 테스트 시작 버튼과 제어 버튼들
        test_control_frame = ttk.Frame(button_frame)
        test_control_frame.pack(side="left")
        
        # 테스트 시작 버튼
        self.start_button = ttk.Button(test_control_frame, text="테스트 시작", 
                                      command=self.start_test_thread)
        self.start_button.pack(side="left", padx=5)
        
        # 중앙: 프로그래스바 영역 (무선연결 해제 버튼 공간 확보)
        progress_frame = ttk.Frame(button_frame)
        progress_frame.pack(side="left", expand=True, fill="x", padx=(20, 80))  # 오른쪽에 무선연결 해제 버튼 공간 확보
        
        # 프로그래스바 영역을 progress_manager에서 사용할 수 있도록 main_app에 전달
        if hasattr(self.main_app, 'progress_manager'):
            self.main_app.progress_manager.set_progress_frame(progress_frame)
        
        # 우측: 리포트 관련 버튼들
        report_frame = ttk.Frame(button_frame)
        report_frame.pack(side="right")
        
        # 폰 재부팅 버튼 (HTML 보기 버튼 왼쪽에 위치)
        self.reboot_button = ttk.Button(report_frame, text="폰 재부팅", 
                                       command=self.reboot_device)
        self.reboot_button.pack(side="left", padx=5)
        
        # 무선 연결 종료 버튼 (무선 모드일 때만 표시)
        if getattr(self.main_app.test_context, 'is_wireless_mode', False):
            self.wireless_disconnect_button = ttk.Button(report_frame, text="무선 연결 종료", 
                                                        command=self.disconnect_wireless)
            self.wireless_disconnect_button.pack(side="left", padx=5)
        
        # HTML 보기 버튼 (테스트 완료 후에만 활성화)
        self.html_view_button = ttk.Button(report_frame, text="HTML 보기", 
                                          command=self.view_html_report, 
                                          state="disabled")
        self.html_view_button.pack(side="left", padx=5)
        
        # 엑셀 내보내기 버튼 (테스트 완료 후에만 활성화)
        self.excel_export_button = ttk.Button(report_frame, text="엑셀 내보내기", 
                                             command=self.export_to_excel, 
                                             state="disabled")
        self.excel_export_button.pack(side="left", padx=5)
        
        # 성능그래프 보기 버튼 (테스트 완료 후에만 활성화)
        self.performance_graph_button = ttk.Button(report_frame, text="성능그래프 보기", 
                                                  command=self.show_performance_graph, 
                                                  state="disabled")
        self.performance_graph_button.pack(side="left", padx=5)
        
        ttk.Button(report_frame, text="콘솔 로그", command=self.toggle_console_log).pack(side="left", padx=5)
        
        logger.info("버튼 프레임 생성 완료")
    
    def create_refresh_button(self, parent_frame):
        """새로고침 버튼 생성 (앱 선택 영역용)"""
        self.refresh_button = ttk.Button(parent_frame, text="새로고침", 
                                        command=self.main_app.load_app_packages)
        self.refresh_button.pack(side="left", padx=5)
        return self.refresh_button
    
    def start_test_thread(self):
        """테스트 시작 버튼 클릭 시, 별도의 스레드에서 테스트를 실행합니다. (원본과 100% 동일)"""
        logger.info("테스트 시작 요청")
        
        # 1. 테스트 실행 중 여부 확인
        if self.main_app.test_running:
            logger.warning("이미 테스트가 실행 중임")
            messagebox.showinfo("정보", "이미 테스트가 실행 중입니다.")
            return
        
        # 2. 장치 연결 상태 확인
        if not self.main_app.test_context.device_serial:
            logger.warning("DEVICE_SERIAL이 설정되지 않음")
            messagebox.showwarning("장치 없음", "ADB 장치가 연결되지 않았습니다.")
            return
        
        # 3. 앱 패키지 목록 로드 여부 확인
        if not hasattr(self.main_app, 'app_packages') or not self.main_app.app_packages:
            logger.warning("앱 패키지 목록이 로드되지 않음")
            messagebox.showwarning("앱 목록 없음", "앱 패키지 목록이 로드되지 않았습니다.\n먼저 '새로고침' 버튼을 눌러 앱 목록을 로드해주세요.")
            return
        
        # 4. 선택된 앱 패키지 유효성 확인
        selected_app = self.main_app.selected_app_package.get().strip()
        
        # 빈 문자열이거나 None인 경우
        if not selected_app:
            logger.warning("선택된 앱이 없음 (빈 문자열)")
            messagebox.showwarning("앱 선택 없음", "테스트할 앱을 선택해주세요.")
            return
        
        # 로딩/오류 상태 메시지인 경우
        invalid_states = ["앱 목록 로딩 중...", "로딩 중...", "연결 실패", "오류 발생", "앱 없음", "업데이트 실패", "테스트할 앱을 선택하세요", ""]
        if selected_app in invalid_states:
            logger.warning(f"유효하지 않은 앱 선택 상태: {selected_app}")
            messagebox.showwarning("앱 선택 오류", f"유효하지 않은 앱 선택 상태입니다: {selected_app}\n\n먼저 '새로고침' 버튼을 눌러 앱 목록을 다시 로드해주세요.")
            return
        
        # 선택된 앱이 실제 로드된 목록에 있는지 확인
        if selected_app not in self.main_app.app_packages:
            logger.warning(f"선택된 앱이 패키지 목록에 없음: {selected_app}")
            messagebox.showwarning("앱 선택 오류", f"선택된 앱 '{selected_app}'이 로드된 패키지 목록에 없습니다.\n\n다시 앱을 선택하거나 '새로고침' 버튼을 눌러주세요.")
            return
        
        # 패키지명 형식 검증 (기본적인 Android 패키지명 패턴)
        if not self._is_valid_package_name(selected_app):
            logger.warning(f"유효하지 않은 패키지명 형식: {selected_app}")
            messagebox.showwarning("패키지명 오류", f"선택된 패키지명이 유효하지 않습니다: {selected_app}\n\n올바른 Android 패키지명을 선택해주세요.")
            return
        
        # 테스트 시작 위임
        self._start_test_with_validation(selected_app)
    
    def _is_valid_package_name(self, package_name):
        """패키지명 유효성 검사"""
        import re
        # 기본적인 Android 패키지명 패턴 검사
        pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'
        return re.match(pattern, package_name) is not None
    
    def _start_test_with_validation(self, selected_app):
        """검증된 앱으로 테스트 시작 (원본과 동일한 방식)"""
        # 테스트 컨텍스트에 앱 설정
        self.main_app.test_context.app_package_name = selected_app
        
        # 테스트 설정 가져오기 (새로운 Seed 로직 적용)
        selected_preset_name = self.main_app.selected_preset.get()
        logger.info(f"선택된 프리셋: {selected_preset_name}")
        
        if selected_preset_name == "Custom":
            try:
                events = int(self.main_app.custom_events.get())
                repeats = int(self.main_app.custom_repeats.get())
                throttle = int(self.main_app.custom_throttle.get())
                # 사용자 지정은 Random Seed 사용
                seed = "random"
                logger.info(f"사용자 지정 설정: events={events}, repeats={repeats}, throttle={throttle}, seed=random")
            except ValueError as e:
                logger.error(f"사용자 지정 값 파싱 오류: {e}")
                messagebox.showerror("입력 오류", "사용자 지정 값들이 유효하지 않습니다. 숫자를 입력해주세요.")
                return
        elif selected_preset_name == "재현테스트":
            try:
                # 재현테스트는 사용자 입력값 + 수동 Seed 사용
                events = int(self.main_app.custom_events.get())
                repeats = int(self.main_app.custom_repeats.get())
                throttle = int(self.main_app.custom_throttle.get())
                seed = int(self.main_app.custom_seed.get())
                logger.info(f"재현테스트 설정: events={events}, repeats={repeats}, throttle={throttle}, seed={seed}")
            except ValueError as e:
                logger.error(f"재현테스트 값 파싱 오류: {e}")
                messagebox.showerror("입력 오류", "재현테스트에서는 모든 값이 유효한 숫자여야 합니다.")
                return
        else:
            from src.config import PRESETS
            preset_config = PRESETS[selected_preset_name]
            events = preset_config["events"]
            seed = preset_config["seed"]  # "random"
            repeats = preset_config["repeats"]
            throttle = preset_config["throttle"]
            logger.info(f"프리셋 설정: events={events}, seed={seed}, repeats={repeats}, throttle={throttle}")
        
        # 테스트 컨텍스트 설정
        self.main_app.test_context.events = events
        self.main_app.test_context.repeats = repeats
        self.main_app.test_context.throttle = throttle
        self.main_app.test_context.seed = seed
        self.main_app.test_context.preset_name = selected_preset_name
        
        # UI 상태 변경
        self.main_app.test_running = True
        self.update_test_button_state(True)
        
        # 테스트 실행 (원본의 _run_monkey_test와 동일한 방식)
        import threading
        threading.Thread(target=self.main_app._run_monkey_test, args=(selected_app,), daemon=True).start()

    def view_html_report(self):
        """HTML 리포트 보기"""
        # 테스트 완료 상태 확인
        if not self._is_test_completed():
            messagebox.showinfo("정보", "생성할 테스트 리포트가 없습니다. 먼저 테스트를 실행해주세요.")
            return
        self.main_app.view_html_report()

    def export_to_excel(self):
        """Excel 리포트 내보내기"""
        # 테스트 완료 상태 확인
        if not self._is_test_completed():
            messagebox.showinfo("정보", "내보낼 테스트 결과가 없습니다. 먼저 테스트를 실행해주세요.")
            return
        self.main_app.export_to_excel()
    
    def _is_test_completed(self):
        """테스트 완료 상태 확인"""
        try:
            if hasattr(self.main_app, 'test_context') and self.main_app.test_context:
                if hasattr(self.main_app.test_context, 'current_test_report') and self.main_app.test_context.current_test_report:
                    details = self.main_app.test_context.current_test_report.get("details", [])
                    return len(details) > 0
            return False
        except Exception as e:
            logger.error(f"테스트 완료 상태 확인 중 오류: {e}")
            return False

    def toggle_console_log(self):
        """콘솔 로그 창 토글"""
        self.main_app.toggle_console_log()

    def disconnect_wireless(self):
        """무선 연결 종료"""
        try:
            if self.main_app.adb_client and hasattr(self.main_app.test_context, 'is_wireless_mode') and self.main_app.test_context.is_wireless_mode:
                # 무선 연결 종료
                result = self.main_app.adb_client.run_command("disconnect")
                if result and "disconnected" in result.lower():
                    messagebox.showinfo("연결 종료", 
                                      "무선 연결이 종료되었습니다.\n\n"
                                      "필요시 다시 연결할 수 있습니다.\n"
                                      "프로그램은 계속 실행됩니다.")
                    # 앱 종료 대신 연결 상태만 리셋
                    self._reset_connection_after_disconnect()
                else:
                    messagebox.showwarning("연결 종료 실패", "무선 연결 종료에 실패했습니다.")
            else:
                messagebox.showinfo("정보", "현재 유선 연결 상태입니다.")
        except Exception as e:
            logger.error(f"무선 연결 종료 오류: {e}")
            messagebox.showerror("오류", f"무선 연결 종료 중 오류 발생: {e}")
    
    def _reset_connection_after_disconnect(self):
        """무선 연결 종료 후 연결 상태 리셋"""
        try:
            # 무선 모드 해제
            if hasattr(self.main_app.test_context, 'is_wireless_mode'):
                self.main_app.test_context.is_wireless_mode = False
            
            # 디바이스 시리얼 초기화
            if hasattr(self.main_app.test_context, 'device_serial'):
                self.main_app.test_context.device_serial = None
            
            # 앱 패키지 목록 초기화
            if hasattr(self.main_app, 'app_packages'):
                self.main_app.app_packages = []
            
            # 앱 선택 상태 초기화
            if hasattr(self.main_app, 'selected_app_package'):
                self.main_app.selected_app_package.set("연결이 종료되었습니다. 다시 연결해주세요")
            
            # 앱 패키지 목록 초기화 (Button은 별도 처리 불필요)
            if hasattr(self.main_app, 'app_packages'):
                self.main_app.app_packages = []
            
            # 테스트 중인 경우 중지
            if hasattr(self.main_app, 'test_running') and self.main_app.test_running:
                self.main_app.test_running = False
                self.update_test_button_state(False)
            
            logger.info("무선 연결 종료 후 연결 상태 리셋 완료")
        except Exception as e:
            logger.error(f"연결 상태 리셋 오류: {e}")

    def reboot_device(self):
        """장치 재부팅"""
        try:
            confirm = messagebox.askyesno("장치 재부팅", 
                                        "장치를 재부팅하시겠습니까?\n\n재부팅 후 연결이 끊어집니다.")
            if confirm:
                if self.main_app.adb_client:
                    self.main_app.adb_client.run_command("reboot")
                    messagebox.showinfo("재부팅 완료", 
                                      "장치 재부팅 명령을 전송했습니다.\n\n"
                                      "재부팅이 완료되면 다시 연결해주세요.\n"
                                      "프로그램은 계속 실행됩니다.")
                    # 앱 종료 대신 연결 상태만 리셋
                    self._reset_connection_after_reboot()
                else:
                    messagebox.showerror("오류", "ADB 클라이언트가 초기화되지 않았습니다.")
        except Exception as e:
            logger.error(f"장치 재부팅 오류: {e}")
            messagebox.showerror("오류", f"장치 재부팅 중 오류 발생: {e}")
    
    def _reset_connection_after_reboot(self):
        """재부팅 후 연결 상태 리셋"""
        try:
            # 디바이스 시리얼 초기화
            if hasattr(self.main_app.test_context, 'device_serial'):
                self.main_app.test_context.device_serial = None
            
            # 패키지 목록과 선택은 초기화하지 않음 (재연결 시 자동으로 새로고침됨)
            # 대신 재연결 대기 메시지만 표시
            if hasattr(self.main_app, 'selected_app_package'):
                current_selection = self.main_app.selected_app_package.get()
                # 유효한 패키지가 선택되어 있었다면 그대로 유지
                if current_selection not in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", "업데이트 실패"]:
                    logger.info(f"재부팅 후 패키지 선택 유지: {current_selection}")
                else:
                    self.main_app.selected_app_package.set("재부팅 후 다시 연결해주세요")
            
            # 테스트 중인 경우 중지
            if hasattr(self.main_app, 'test_running') and self.main_app.test_running:
                self.main_app.test_running = False
                self.update_test_button_state(False)
            
            logger.info("재부팅 후 연결 상태 리셋 완료 (패키지 선택 보존)")
        except Exception as e:
            logger.error(f"연결 상태 리셋 오류: {e}")
    
    def show_performance_graph(self):
        """성능그래프 보기 버튼 클릭 시 팝업 윈도우 표시"""
        try:
            logger.info("성능그래프 보기 요청")
            
            # 차트 데이터 확인 및 디버깅
            has_chart_data = hasattr(self.main_app, 'current_chart_data') and self.main_app.current_chart_data
            logger.info(f"차트 데이터 존재 여부: {has_chart_data}")
            
            if has_chart_data:
                logger.info(f"차트 데이터 키: {list(self.main_app.current_chart_data.keys())}")
                for key, value in self.main_app.current_chart_data.items():
                    logger.info(f"차트 [{key}] 타입: {type(value)}, 크기: {len(value) if isinstance(value, (list, dict)) else 'N/A'}")
            
            # 차트 데이터가 없으면 테스트 컨텍스트에서 다시 생성 시도
            if not has_chart_data:
                logger.info("차트 데이터가 없어서 재생성 시도")
                self.main_app.update_visualization_charts()
                
                # 재생성 후 다시 확인
                has_chart_data = hasattr(self.main_app, 'current_chart_data') and self.main_app.current_chart_data
                if has_chart_data:
                    logger.info(f"차트 데이터 재생성 성공: {list(self.main_app.current_chart_data.keys())}")
                else:
                    logger.warning("차트 데이터 재생성 실패")
            
            # 여전히 데이터가 없으면 경고 메시지
            if not has_chart_data:
                messagebox.showwarning("데이터 없음", "표시할 성능 데이터가 없습니다.\n테스트를 완료한 후 다시 시도해주세요.")
                return
            
            # 테스트 정보 수집 - 더 정확한 패키지명 가져오기
            package_name = 'Unknown Package'
            
            # 1. test_context에서 패키지명 시도
            if hasattr(self.main_app, 'test_context') and self.main_app.test_context:
                logger.info(f"test_context 속성들: {dir(self.main_app.test_context)}")
                
                # app_package_name 우선 확인 (가장 정확한 패키지명)
                if hasattr(self.main_app.test_context, 'app_package_name') and self.main_app.test_context.app_package_name:
                    package_name = self.main_app.test_context.app_package_name
                    logger.info(f"test_context.app_package_name에서 가져옴: {package_name}")
                elif hasattr(self.main_app.test_context, 'package_name') and self.main_app.test_context.package_name:
                    package_name = self.main_app.test_context.package_name
                    logger.info(f"test_context.package_name에서 가져옴: {package_name}")
                # 2. selected_app에서 패키지명 시도
                elif hasattr(self.main_app.test_context, 'selected_app') and self.main_app.test_context.selected_app:
                    if isinstance(self.main_app.test_context.selected_app, dict):
                        package_name = self.main_app.test_context.selected_app.get('package', 'Unknown Package')
                        logger.info(f"test_context.selected_app dict에서 가져옴: {package_name}")
                    else:
                        package_name = str(self.main_app.test_context.selected_app)
                        logger.info(f"test_context.selected_app str에서 가져옴: {package_name}")
                # 3. current_test_report에서 패키지명 시도
                elif hasattr(self.main_app.test_context, 'current_test_report') and self.main_app.test_context.current_test_report:
                    report = self.main_app.test_context.current_test_report
                    if 'package_name' in report:
                        package_name = report['package_name']
                        logger.info(f"current_test_report에서 가져옴: {package_name}")
                    elif 'app_info' in report and isinstance(report['app_info'], dict):
                        app_info = report['app_info']
                        if 'package' in app_info:
                            package_name = app_info['package']
                            logger.info(f"current_test_report.app_info.package에서 가져옴: {package_name}")
            
            # 4. 현재 선택된 앱에서 패키지명 시도
            if package_name == 'Unknown Package':
                if hasattr(self.main_app, 'app_var') and self.main_app.app_var:
                    selected_app = self.main_app.app_var.get()
                    logger.info(f"app_var에서 선택된 앱: {selected_app}")
                    if selected_app and ' - ' in selected_app:
                        package_name = selected_app.split(' - ')[1]  # "앱이름 - 패키지명" 형식에서 패키지명 추출
                        logger.info(f"app_var에서 패키지명 추출: {package_name}")
                    elif selected_app:
                        package_name = selected_app
                        logger.info(f"app_var 전체를 패키지명으로 사용: {package_name}")
            
            # 5. 드롭다운에서 현재 선택된 값 시도
            if package_name == 'Unknown Package':
                try:
                    if hasattr(self.main_app, 'app_dropdown') and self.main_app.app_dropdown:
                        current_selection = self.main_app.app_dropdown.get()
                        logger.info(f"드롭다운에서 현재 선택: {current_selection}")
                        if current_selection and ' - ' in current_selection:
                            package_name = current_selection.split(' - ')[1]
                            logger.info(f"드롭다운에서 패키지명 추출: {package_name}")
                except Exception as e:
                    logger.warning(f"드롭다운에서 패키지명 가져오기 실패: {e}")
            
            # 최종 검증 및 더 정확한 패키지명 추출 시도
            if not package_name or package_name in ['Unknown Package', '', 'None']:
                # 6. 차트 데이터에서 패키지명 추출 시도
                try:
                    if hasattr(self.main_app, 'current_chart_data') and self.main_app.current_chart_data:
                        for chart_key in ['memory', 'cpu']:
                            if chart_key in self.main_app.current_chart_data:
                                chart_info = self.main_app.current_chart_data[chart_key]
                                if isinstance(chart_info, dict) and 'title' in chart_info:
                                    title = chart_info['title']
                                    if ' - ' in title and 'com.' in title:
                                        package_name = title.split(' - ')[-1]
                                        logger.info(f"차트 데이터에서 패키지명 추출: {package_name}")
                                        break
                except Exception as e:
                    logger.warning(f"차트 데이터에서 패키지명 추출 실패: {e}")
                
                # 여전히 찾지 못한 경우
                if not package_name or package_name in ['Unknown Package', '', 'None']:
                    package_name = 'Unknown Package'
            
            logger.info(f"팝업에 사용할 최종 패키지명: {package_name}")
            
            test_info = {
                'package_name': package_name,
                'test_time': getattr(self.main_app.test_context, 'start_time', 'Unknown'),
                'total_repeats': getattr(self.main_app.test_context, 'repeats', 'N/A')
            }
            
            # 팝업 윈도우 생성 및 표시 (main_app을 parent로 사용)
            from src.ui.performance_graph_popup import PerformanceGraphPopup
            popup = PerformanceGraphPopup(self.main_app, self.main_app.current_chart_data, test_info)
            
            logger.info("성능그래프 팝업 표시 완료")
            
        except Exception as e:
            error_msg = f"성능그래프 표시 중 오류 발생: {e}"
            logger.error(error_msg)
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            messagebox.showerror("오류", error_msg)
    
    def enable_performance_graph_button(self):
        """성능그래프 보기 버튼 활성화 (테스트 완료 후 호출)"""
        try:
            if self.performance_graph_button:
                self.performance_graph_button.config(state="normal")
                logger.info("✅ 성능그래프 보기 버튼 활성화 성공")
            else:
                logger.error("❌ performance_graph_button이 None입니다")
        except Exception as e:
            logger.error(f"❌ 성능그래프 보기 버튼 활성화 실패: {e}")
    
    def disable_performance_graph_button(self):
        """성능그래프 보기 버튼 비활성화 (테스트 시작 시 호출)"""
        try:
            if self.performance_graph_button:
                self.performance_graph_button.config(state="disabled")
                logger.info("✅ 성능그래프 보기 버튼 비활성화 성공")
            else:
                logger.error("❌ performance_graph_button이 None입니다")
        except Exception as e:
            logger.error(f"❌ 성능그래프 보기 버튼 비활성화 실패: {e}")
    
    def enable_report_buttons(self):
        """HTML 보기 및 엑셀 내보내기 버튼 활성화 (테스트 완료 후 호출)"""
        try:
            if self.html_view_button:
                self.html_view_button.config(state="normal")
                logger.info("✅ HTML 보기 버튼 활성화 성공")
            else:
                logger.error("❌ html_view_button이 None입니다")
                
            if self.excel_export_button:
                self.excel_export_button.config(state="normal")
                logger.info("✅ 엑셀 내보내기 버튼 활성화 성공")
            else:
                logger.error("❌ excel_export_button이 None입니다")
        except Exception as e:
            logger.error(f"❌ 리포트 버튼 활성화 실패: {e}")
    
    def disable_report_buttons(self):
        """HTML 보기 및 엑셀 내보내기 버튼 비활성화 (테스트 시작 시 호출)"""
        try:
            if self.html_view_button:
                self.html_view_button.config(state="disabled")
                logger.info("✅ HTML 보기 버튼 비활성화 성공")
            else:
                logger.error("❌ html_view_button이 None입니다")
                
            if self.excel_export_button:
                self.excel_export_button.config(state="disabled")
                logger.info("✅ 엑셀 내보내기 버튼 비활성화 성공")
            else:
                logger.error("❌ excel_export_button이 None입니다")
        except Exception as e:
            logger.error(f"❌ 리포트 버튼 비활성화 실패: {e}")
            
    def update_test_button_state(self, is_testing: bool):
        """테스트 버튼 상태 업데이트"""
        if self.start_button:
            if is_testing:
                self.start_button.config(state="disabled", text="테스트 진행 중...")
            else:
                self.start_button.config(state="normal", text="테스트 시작")
