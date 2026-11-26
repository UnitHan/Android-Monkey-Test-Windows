#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테스트 처리 핸들러
main_app.py에서 분리된 테스트 실행 관련 기능들
"""
import logging
import threading
from src.utils.gui_utils import messagebox
from src.core.test_context import TestContext

logger = logging.getLogger(__name__)

class TestHandler:
    """테스트 처리를 담당하는 핸들러"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        
    def start_test_thread(self):
        """테스트 시작 (새 스레드에서)"""
        if self.main_app.is_testing:
            messagebox.showwarning("테스트 진행 중", "이미 테스트가 진행 중입니다.")
            return
        
        if not self._validate_test_settings():
            return
        
        self.main_app.is_testing = True
        self._update_ui_for_testing(True)
        
        # 테스트 스레드 시작
        self.main_app.test_thread = threading.Thread(
            target=self._run_test_background,
            daemon=True
        )
        self.main_app.test_thread.start()
    
    def _validate_test_settings(self):
        """테스트 설정 유효성 검사 (원본과 동일한 변수명 사용)"""
        try:
            if not self.main_app.adb_client:
                messagebox.showerror("오류", "ADB가 연결되지 않았습니다.")
                return False
            
            # 선택된 앱 패키지 확인
            package_name = self.main_app.selected_app_package.get().strip()
            if not package_name or package_name in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생"]:
                messagebox.showerror("오류", "테스트할 앱 패키지를 선택하세요.")
                return False
            
            # 프리셋 또는 사용자 지정 설정값 유효성 검사
            selected_preset = self.main_app.selected_preset.get()
            if selected_preset in ["Custom", "재현테스트"]:
                # 사용자 지정 및 재현테스트 설정값 검사
                event_count = int(self.main_app.custom_events.get())
                repeat_count = int(self.main_app.custom_repeats.get())
                throttle = int(self.main_app.custom_throttle.get())
                
                if event_count <= 0 or repeat_count <= 0 or throttle < 0:
                    messagebox.showerror("오류", "설정값이 올바르지 않습니다.")
                    return False
                
                # 재현테스트에서는 추가로 seed 값 검증
                if selected_preset == "재현테스트":
                    seed = int(self.main_app.custom_seed.get())
                    if not (1000 <= seed <= 9999):
                        messagebox.showerror("오류", "Seed 값은 1000~9999 범위의 4자리 숫자여야 합니다.")
                        return False
            
            return True
            
        except ValueError:
            messagebox.showerror("오류", "설정값에 올바른 숫자를 입력하세요.")
            return False
    
    def _update_ui_for_testing(self, testing):
        """테스트 상태에 따른 UI 업데이트 (버튼 매니저 사용)"""
        if hasattr(self.main_app, 'button_manager'):
            self.main_app.button_manager.update_test_button_state(testing)
            
            # 테스트 시작 시 리포트 버튼들 비활성화
            if testing:
                self.main_app.button_manager.disable_report_buttons()
                self.main_app.button_manager.disable_performance_graph_button()
                logger.info("테스트 시작 - 리포트 버튼들 비활성화")
        
        # 상태 레이블 업데이트 (있는 경우에만)
        if hasattr(self.main_app, 'status_label'):
            if testing:
                self.main_app.status_label.config(text="테스트 진행 중...")
            else:
                self.main_app.status_label.config(text="준비 완료")
        
        # 프로그레스 바 업데이트 (있는 경우에만)
        if hasattr(self.main_app, 'progress_var') and not testing:
            self.main_app.progress_var.set(0)
    
    def _run_test_background(self):
        """백그라운드에서 테스트 실행 (원본과 동일한 변수명 사용)"""
        try:
            # 테스트 컨텍스트 생성
            package_name = self.main_app.selected_app_package.get()
            
            # 이미 test_context가 있으므로 설정 업데이트
            if not hasattr(self.main_app, 'test_context'):
                from src.core.test_context import TestContext
                self.main_app.test_context = TestContext()
            
            self.main_app.test_context.app_package_name = package_name
            
            # 프리셋 또는 사용자 지정 설정 적용 (새로운 Seed 로직)
            selected_preset = self.main_app.selected_preset.get()
            if selected_preset == "Custom":
                # 사용자 지정 설정 (Random Seed 사용)
                self.main_app.test_context.preset_name = "Custom"
                self.main_app.test_context.events = int(self.main_app.custom_events.get())
                self.main_app.test_context.repeats = int(self.main_app.custom_repeats.get())
                self.main_app.test_context.throttle = int(self.main_app.custom_throttle.get())
                self.main_app.test_context.seed = "random"
            elif selected_preset == "재현테스트":
                # 재현테스트 설정 (사용자 입력값 + 수동 Seed)
                self.main_app.test_context.preset_name = "재현테스트"
                self.main_app.test_context.events = int(self.main_app.custom_events.get())
                self.main_app.test_context.repeats = int(self.main_app.custom_repeats.get())
                self.main_app.test_context.throttle = int(self.main_app.custom_throttle.get())
                self.main_app.test_context.seed = int(self.main_app.custom_seed.get())
            else:
                # 기본 프리셋 설정 (Random Seed)
                from src.config import PRESETS
                preset_config = PRESETS[selected_preset]
                self.main_app.test_context.preset_name = selected_preset
                self.main_app.test_context.events = preset_config["events"]
                self.main_app.test_context.repeats = preset_config["repeats"]
                self.main_app.test_context.throttle = preset_config["throttle"]
                self.main_app.test_context.seed = preset_config["seed"]  # "random"
            
            # MonkeyRunner 생성 (test_context와 함께)
            from src.core.monkey_runner import MonkeyRunner
            self.main_app.monkey_runner = MonkeyRunner(self.main_app.adb_client, self.main_app.test_context)
            
            # 콜백 설정
            self.main_app.monkey_runner.set_progress_callback(self._update_progress)
            self.main_app.monkey_runner.set_completion_callback(self._on_test_completion)
            self.main_app.monkey_runner.set_status_callback(self._on_status_update)
            
            logger.info(f"🚀 테스트 시작: {package_name}")
            
            # 테스트 실행
            success = self.main_app.monkey_runner.start_test()
            
            if not success:
                # 테스트 시작 실패
                self.main_app.after(0, lambda: self._handle_test_error("테스트 시작 실패"))
            
        except Exception as e:
            logger.error(f"❌ 테스트 실행 중 오류: {e}")
            self.main_app.after(0, lambda: self._handle_test_error(f"테스트 오류: {e}"))
            logger.exception("테스트 실행 상세 오류:")
            self.main_app.after(0, lambda: self._handle_test_error(str(e)))
        finally:
            self.main_app.is_testing = False
            self.main_app.after(0, lambda: self._update_ui_for_testing(False))
    
    def _handle_test_results(self, results):
        """테스트 결과 처리"""
        try:
            logger.info("📊 테스트 결과 처리 시작")
            
            # 차트 생성
            charts = self.main_app.chart_generator.generate_all_charts(results)
            
            if charts:
                # 시각화 탭에 차트 추가
                self.main_app.chart_handler.add_charts_to_visualization(charts)
                
                # 시각화 탭으로 전환
                self.main_app.notebook.select(1)
                
                logger.info("✅ 테스트 결과 처리 완료")
            else:
                logger.warning("차트 생성 실패")
                
        except Exception as e:
            logger.error(f"테스트 결과 처리 오류: {e}")
            logger.exception("결과 처리 상세 오류:")
    
    def _handle_test_error(self, error_message):
        """테스트 오류 처리"""
        messagebox.showerror("테스트 오류", f"테스트 중 오류가 발생했습니다:\n{error_message}")
    
    def stop_test(self):
        """테스트 중지"""
        if self.main_app.monkey_runner:
            self.main_app.monkey_runner.stop_test()
        self.main_app.is_testing = False
        self._update_ui_for_testing(False)
        logger.info("🛑 테스트 중지됨")
    
    def _on_test_completion(self, success: bool, message: str):
        """테스트 완료 콜백"""
        try:
            logger.info(f"테스트 완료: {'성공' if success else '실패'} - {message}")
            
            if success:
                # 결과 처리 및 차트 생성
                results = self.main_app.monkey_runner.get_test_results()
                self.main_app.after(0, lambda: self._handle_test_results(results))
            else:
                # 실패 처리
                self.main_app.after(0, lambda: self._handle_test_error(message))
                
            self.main_app.is_testing = False
            self.main_app.after(0, lambda: self._update_ui_for_testing(False))
            
        except Exception as e:
            logger.error(f"테스트 완료 콜백 오류: {e}")
    
    def _on_status_update(self, status: str):
        """상태 업데이트 콜백"""
        try:
            self.main_app.after(0, lambda: self.main_app.status_label.config(text=status))
        except Exception as e:
            logger.error(f"상태 업데이트 콜백 오류: {e}")
    
    def _update_progress(self, status: str, current: int, total: int):
        """진행률 업데이트 (수정된 시그니처)"""
        try:
            progress = (current / total) * 100 if total > 0 else 0
            self.main_app.after(0, lambda: self.main_app.progress_var.set(progress))
            self.main_app.after(0, lambda: self.main_app.status_label.config(text=f"{status}: {current}/{total}"))
        except Exception as e:
            logger.error(f"진행률 업데이트 오류: {e}")
