#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
패키지 처리 핸들러
main_app.py에서 분리된 패키지 로딩 관련 기능들
"""
import logging
import threading
import time
from src.utils.gui_utils import messagebox

logger = logging.getLogger(__name__)

class PackageHandler:
    """패키지 처리를 담당하는 핸들러"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        self.package_loading_in_progress = False
        
    def load_app_packages(self):
        """연결된 장치에서 설치된 앱 패키지 목록을 가져옵니다. (중복 호출 방지)"""
        if self.package_loading_in_progress:
            logger.warning("패키지 로딩이 이미 진행 중입니다")
            # 재부팅 후 자동 호출인 경우 팝업 표시하지 않음
            if not getattr(self, '_is_auto_refresh', False):
                messagebox.showwarning("로딩 중", "패키지 목록을 이미 가져오는 중입니다. 잠시 기다려주세요.")
            return
        
        if not self.main_app.adb_client:
            logger.error("ADB 클라이언트가 연결되지 않았습니다")
            messagebox.showerror("연결 오류", "ADB 클라이언트가 연결되지 않았습니다.")
            return
        
        self.package_loading_in_progress = True
        
        # UI 상태 업데이트 (안전성 검사 추가)
        if hasattr(self.main_app, 'refresh_button') and self.main_app.refresh_button:
            self.main_app.refresh_button.config(state="disabled", text="로딩 중...")
        
        if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
            self.main_app.package_combobox.config(state="disabled")
        
        # 패키지 상태 라벨은 업데이트하지 않음 (재연결 시 불필요한 메시지 방지)
        # if hasattr(self.main_app, 'package_status_label') and self.main_app.package_status_label:
        #     self.main_app.package_status_label.config(
        #         text="📱 설치된 앱 목록을 가져오는 중...", 
        #         foreground="blue"
        #     )
        
        # 백그라운드에서 패키지 로딩
        thread = threading.Thread(
            target=self._load_packages_background, 
            daemon=True
        )
        thread.start()
        
    def _load_packages_background(self):
        """백그라운드에서 패키지 목록 로딩"""
        try:
            logger.info("📱 설치된 앱 패키지 목록 조회 시작")
            start_time = time.time()
            
            # ADB를 통해 패키지 목록 가져오기
            packages = self.main_app.adb_client.get_installed_packages()
            
            if packages:
                elapsed_time = time.time() - start_time
                logger.info(f"✅ 패키지 목록 조회 완료: {len(packages)}개 (소요시간: {elapsed_time:.2f}초)")
                
                # 메인 스레드에서 UI 업데이트
                self.main_app.after(0, lambda: self._update_package_list_ui(packages))
            else:
                logger.warning("⚠️ 패키지 목록이 비어있습니다")
                # 빈 목록도 연결 문제일 가능성이 높으므로 조용히 처리
                self.main_app.after(0, self._restore_ui_state_only)
                
        except Exception as e:
            logger.error(f"❌ 패키지 목록 조회 실패: {e}")
            logger.exception("패키지 로딩 상세 오류:")
            
            # 자동 새로고침 중이거나 연결 문제인지 확인
            is_auto_refresh = getattr(self, '_is_auto_refresh', False)
            error_msg = str(e).lower()
            is_connection_error = any(keyword in error_msg for keyword in [
                "연결", "connection", "device", "adb", "timeout", "끊어", "없습니다", "offline"
            ])
            
            if is_auto_refresh or is_connection_error:
                logger.info("자동 새로고침 중이거나 연결 문제로 인한 패키지 조회 실패 - 팝업 표시하지 않음")
                # UI 상태만 복원하고 팝업은 표시하지 않음
                self.main_app.after(0, self._restore_ui_state_only)
            else:
                # 수동 새로고침 시 일반적인 오류만 팝업으로 표시
                self.main_app.after(0, lambda: self._handle_package_loading_error(f"조회 오류: {str(e)[:50]}"))
        finally:
            self.package_loading_in_progress = False
    
    def _update_package_list_ui(self, packages):
        """패키지 목록 UI 업데이트 (메인 스레드에서 호출)"""
        try:
            # 현재 선택된 패키지 기억
            current_selection = None
            if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
                current_selection = self.main_app.package_combobox.get()
                logger.info(f"현재 선택된 패키지: {current_selection}")
            
            # 재연결 후 보존된 선택이 있는지 확인
            preserved_selection = getattr(self.main_app, '_preserved_package_selection', None)
            if preserved_selection:
                current_selection = preserved_selection
                self.main_app._preserved_package_selection = None  # 사용 후 제거
                logger.info(f"재연결 후 보존된 패키지 선택 복원: {preserved_selection}")
            
            # 패키지 목록을 콤보박스에 설정 (안전성 검사)
            if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
                self.main_app.package_combobox.config(values=packages, state="readonly")
                
                # 이전에 선택된 패키지가 새 목록에 있으면 복원, 없으면 첫 번째 패키지 선택
                if packages:
                    if current_selection and current_selection in packages:
                        # 이전 선택 복원
                        self.main_app.package_combobox.set(current_selection)
                        logger.info(f"이전 선택 패키지 복원: {current_selection}")
                    else:
                        # 첫 번째 패키지 선택
                        self.main_app.package_combobox.set(packages[0])
                        logger.info(f"첫 번째 패키지로 설정: {packages[0]}")
                        
                        # 새로 선택된 패키지의 앱 정보 가져오기 (이전 선택과 다른 경우만)
                        if current_selection != packages[0] and hasattr(self.main_app, 'app_info_handler'):
                            self.main_app.app_info_handler.fetch_app_info(packages[0])
            
            # UI 상태 복원 (안전성 검사 추가)
            if hasattr(self.main_app, 'refresh_button') and self.main_app.refresh_button:
                self.main_app.refresh_button.config(state="normal", text="새로고침")
            
            if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
                self.main_app.package_combobox.config(state="readonly")
            
            if hasattr(self.main_app, 'package_status_label') and self.main_app.package_status_label:
                self.main_app.package_status_label.config(
                    text=f"✅ {len(packages)}개 앱 패키지 로드됨", 
                    foreground="green"
                )
            
            logger.info(f"✅ 패키지 목록 UI 업데이트 완료: {len(packages)}개")
            
        except Exception as e:
            logger.error(f"패키지 목록 UI 업데이트 실패: {e}")
            # 연결 문제가 아닌 경우에만 오류 처리 호출
            if "NoneType" not in str(e) and "config" not in str(e):
                self._handle_package_loading_error(f"UI 업데이트 오류: {str(e)[:50]}")
            else:
                logger.info("UI 위젯 접근 실패 (연결 끊어짐 상태) - 무시함")
    
    def _handle_package_loading_error(self, error_message):
        """패키지 로딩 오류 처리 (메인 스레드에서 호출)"""
        try:
            # UI 상태 복원 (안전성 검사 추가)
            if hasattr(self.main_app, 'refresh_button') and self.main_app.refresh_button:
                self.main_app.refresh_button.config(state="normal", text="새로고침")
            
            if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
                self.main_app.package_combobox.config(state="readonly")
            
            if hasattr(self.main_app, 'package_status_label') and self.main_app.package_status_label:
                self.main_app.package_status_label.config(
                    text=f"❌ 패키지 로딩 실패: {error_message}", 
                    foreground="red"
                )
            
            # 사용자에게 오류 알림 (연결 관련 문제는 팝업 표시 안 함)
            connection_keywords = ["연결", "끊어", "connection", "device", "adb", "timeout", "없습니다", "비어있습니다"]
            is_connection_related = any(keyword in error_message.lower() for keyword in connection_keywords)
            
            if not is_connection_related:
                messagebox.showerror("패키지 로딩 오류", f"앱 패키지 목록을 가져오는데 실패했습니다.\n\n{error_message}")
            else:
                logger.info(f"연결 관련 문제로 인한 패키지 로딩 실패 - 팝업 표시 안 함: {error_message}")
            
        except Exception as e:
            logger.error(f"패키지 로딩 오류 처리 실패: {e}")
    
    def refresh_app_packages(self):
        """앱 패키지 목록 새로고침"""
        logger.info("🔄 앱 패키지 목록 새로고침")
        self.load_app_packages()
    
    def _restore_ui_state_only(self):
        """UI 상태만 복원 (오류 메시지나 팝업 없이)"""
        try:
            # UI 상태 복원 (안전성 검사 추가)
            if hasattr(self.main_app, 'refresh_button') and self.main_app.refresh_button:
                self.main_app.refresh_button.config(state="normal", text="새로고침")
            
            if hasattr(self.main_app, 'package_combobox') and self.main_app.package_combobox:
                self.main_app.package_combobox.config(state="readonly")
            
            # 상태 라벨은 업데이트하지 않음 (연결 상태 표시 유지)
            logger.info("UI 상태만 복원 완료 (연결 문제로 인한 조용한 복원)")
            
        except Exception as e:
            logger.debug(f"UI 상태 복원 실패: {e}")  # debug 레벨로 로깅
    
    def on_package_selected(self, event=None):
        """패키지 선택 시 호출되는 이벤트 핸들러"""
        try:
            selected_package = self.main_app.package_combobox.get()
            if selected_package and hasattr(self.main_app, 'app_info_handler'):
                logger.info(f"📱 패키지 선택됨: {selected_package}")
                self.main_app.app_info_handler.fetch_app_info(selected_package)
        except Exception as e:
            logger.error(f"패키지 선택 처리 오류: {e}")
            
    def refresh_app_packages_quiet(self):
        """조용한 패키지 새로고침 (팝업 없이 진행)"""
        logger.info("조용한 패키지 새로고침 시작")
        self._is_auto_refresh = True
        try:
            self.load_app_packages()
        finally:
            # 새로고침 완료 후 플래그 해제
            self.main_app.after(5000, lambda: setattr(self, '_is_auto_refresh', False))  # 5초 후 플래그 해제