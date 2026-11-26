#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 정보 표시 UI 컴포넌트
old_main_app.py의 앱 정보 관련 로직을 완전 분리
"""
import logging
import threading
from tkinter import ttk
from typing import Optional
from PIL import Image, ImageTk
import io

logger = logging.getLogger(__name__)

class AppInfoDisplay:
    """앱 정보 표시를 담당하는 UI 컴포넌트"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        
        # 앱 정보 관련 위젯들
        self.app_icon_label: Optional[ttk.Label] = None
        self.app_name_label: Optional[ttk.Label] = None
        self.app_developer_label: Optional[ttk.Label] = None
        self.app_category_label: Optional[ttk.Label] = None
        self.app_version_label: Optional[ttk.Label] = None
        self.store_version_label: Optional[ttk.Label] = None
        self.update_status_label: Optional[ttk.Label] = None
        
        # 앱 정보 데이터
        self.current_app_info = None
        self.app_icon_image = None
    
    def create_app_info_frame(self, parent_frame):
        """앱 정보 표시 프레임 생성 (원본과 100% 동일)"""
        # 앱 정보 표시 프레임
        app_info_frame = ttk.Frame(parent_frame)
        app_info_frame.pack(fill="x", pady=5)
        
        # 디버깅용: 프레임 참조 저장
        self.app_info_frame = app_info_frame
        logger.debug(f"🔍 앱 정보 프레임 생성됨: {app_info_frame}")
        
        # 앱 아이콘과 정보를 담을 프레임
        info_left_frame = ttk.Frame(app_info_frame)
        info_left_frame.pack(side="left", padx=5)
        
        # 앱 아이콘 레이블 (기본 64x64 크기)
        self.app_icon_label = ttk.Label(info_left_frame, text="📱", font=("Noto Sans KR", 24))
        self.app_icon_label.pack(side="left", padx=5)
        
        # 앱 정보 텍스트
        info_text_frame = ttk.Frame(app_info_frame)
        info_text_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        self.app_name_label = ttk.Label(info_text_frame, text="앱을 선택하면 정보가 표시됩니다", 
                                       font=("Noto Sans KR", 10, "bold"))
        self.app_name_label.pack(anchor="w")
        logger.debug(f"🔍 앱 이름 라벨 생성됨: {self.app_name_label}")
        
        self.app_developer_label = ttk.Label(info_text_frame, text="", 
                                           font=("Noto Sans KR", 8))
        self.app_developer_label.pack(anchor="w")
        
        self.app_category_label = ttk.Label(info_text_frame, text="", 
                                          font=("Noto Sans KR", 8))
        self.app_category_label.pack(anchor="w")
        
        # 설치된 버전 정보
        self.app_version_label = ttk.Label(info_text_frame, text="", 
                                         font=("Noto Sans KR", 8), 
                                         foreground="blue")
        self.app_version_label.pack(anchor="w")
        
        # 스토어 버전 정보
        self.store_version_label = ttk.Label(info_text_frame, text="", 
                                           font=("Noto Sans KR", 8), 
                                           foreground="green")
        self.store_version_label.pack(anchor="w")
        
        logger.info("앱 정보 표시 프레임 생성 완료")
    
    def on_app_selected(self, selected_package: str):
        """앱이 선택되었을 때 호출되는 이벤트 핸들러"""
        logger.debug(f"🔍 AppInfoDisplay.on_app_selected 호출됨: {selected_package}")
        if selected_package and selected_package not in ["테스트할 앱을 선택하세요", "앱 없음", "연결 실패", "오류 발생", "업데이트 실패"]:
            logger.info(f"앱 선택됨: {selected_package}")
            self.fetch_app_info_async(selected_package)
        else:
            logger.debug(f"🔍 앱 정보 조회 생략 - 유효하지 않은 패키지: {selected_package}")
            # 유효하지 않은 패키지가 선택되어도 기존 정보를 유지 (초기화하지 않음)
    
    def fetch_app_info_async(self, package_name: str):
        """비동기로 앱 정보를 조회합니다 (원본과 100% 동일)"""
        def _fetch_info_thread():
            try:
                logger.info(f"앱 정보 조회 시작: {package_name}")
                self.main_app.after(0, lambda: self.update_app_info_ui("조회 중...", "앱 정보를 가져오는 중입니다...", "", "", None))
                
                # 1. Google Play 스토어에서 앱 정보 조회
                from src.utils.app_info_fetcher import AppInfoFetcher
                app_info = AppInfoFetcher.get_app_info_from_package(package_name)
                
                # 2. ADB를 통해 앱 버전 정보 조회
                version_info = None
                if hasattr(self.main_app, 'adb_client') and self.main_app.adb_client:
                    version_info = self.main_app.adb_client.get_app_version_info(package_name)
                
                if app_info:
                    self.current_app_info = app_info
                    
                    # 아이콘 다운로드
                    icon_data = None
                    if app_info.get('icon_url'):
                        icon_data = AppInfoFetcher.download_icon(app_info['icon_url'])
                    
                    # 버전 정보 문자열 생성 (설치된 버전 + 버전코드)
                    version_text = ""
                    if version_info:
                        if version_info['version_code'] != "알 수 없음":
                            version_text = f"📄 설치된 버전: {version_info['version_name']} ({version_info['version_code']})"
                        else:
                            version_text = f"📄 설치된 버전: {version_info['version_name']}"
                    
                    # UI 업데이트를 메인 스레드에서 실행
                    self.main_app.after(0, lambda: self.update_app_info_ui(
                        app_info.get('app_name', package_name),
                        f"개발자: {app_info.get('developer', '알 수 없음')}",
                        f"카테고리: {app_info.get('category', '알 수 없음')}",
                        version_text,
                        icon_data
                    ))
                else:
                    # Google Play에서 정보를 찾을 수 없는 경우
                    version_text = ""
                    if version_info:
                        if version_info['version_code'] != "알 수 없음":
                            version_text = f"📄 설치된 버전: {version_info['version_name']} ({version_info['version_code']})"
                        else:
                            version_text = f"📄 설치된 버전: {version_info['version_name']}"
                    
                    self.main_app.after(0, lambda: self.update_app_info_ui(
                        package_name,
                        "Google Play에서 정보를 찾을 수 없습니다",
                        "패키지명으로만 표시됩니다",
                        version_text,
                        None
                    ))
                    
            except Exception as e:
                logger.error(f"앱 정보 조회 오류: {e}")
                self.main_app.after(0, lambda: self.update_app_info_ui(
                    package_name,
                    f"정보 조회 실패: {str(e)}",
                    "",
                    "",
                    None
                ))
        
        threading.Thread(target=_fetch_info_thread, daemon=True).start()

    def update_app_info_ui(self, app_name: str, developer_info: str, category_info: str, version_info: str, icon_data: Optional[bytes] = None):
        """앱 정보 UI를 업데이트합니다 (원본과 100% 동일)"""
        try:
            logger.debug(f"🔍 앱 정보 UI 업데이트 호출됨: {app_name}")
            
            # 디버깅용: 위젯 상태 확인
            if self.app_name_label:
                try:
                    visible = self.app_name_label.winfo_viewable()
                    mapped = self.app_name_label.winfo_ismapped()
                    logger.debug(f"🔍 앱 이름 라벨 상태 - visible: {visible}, mapped: {mapped}")
                except Exception as e:
                    logger.debug(f"🔍 앱 이름 라벨 상태 확인 오류: {e}")
            
            # 앱 이름 업데이트
            if self.app_name_label:
                logger.debug(f"🔍 앱 이름 라벨 변경: '{self.app_name_label.cget('text')}' → '{app_name}'")
                self.app_name_label.config(text=app_name)
            
            # 개발자 정보 업데이트
            if self.app_developer_label:
                self.app_developer_label.config(text=developer_info)
            
            # 카테고리 정보 업데이트
            if self.app_category_label:
                self.app_category_label.config(text=category_info)
            
            # 버전 정보 업데이트
            if self.app_version_label:
                self.app_version_label.config(text=version_info)
            
            # 스토어 버전 정보 및 업데이트 상태 표시
            if self.store_version_label:
                if self.current_app_info:
                    store_version = self.current_app_info.get('store_version', '알 수 없음')
                    
                    # 간단한 버전 비교
                    update_status = ""
                    if version_info and store_version != '알 수 없음':
                        try:
                            # 설치된 버전에서 버전명만 추출
                            installed_ver = version_info.replace("📄 설치된 버전: ", "").split(" (")[0].strip()
                            store_ver = store_version.strip()
                            
                            if installed_ver == store_ver:
                                update_status = "✅ 최신"
                            else:
                                update_status = "⚠️ 업데이트 필요"
                        except:
                            update_status = ""
                    
                    store_text = f"🛍️스토어 최신 버전: {store_version}{update_status}"
                    self.store_version_label.config(text=store_text)
                else:
                    self.store_version_label.config(text="")
            
            # 아이콘 업데이트
            if icon_data and self.app_icon_label:
                try:
                    # PIL을 사용해서 이미지 처리
                    image = Image.open(io.BytesIO(icon_data))
                    # 아이콘 크기를 64x64로 조정
                    image = image.resize((64, 64), Image.Resampling.LANCZOS)
                    
                    # tkinter용 이미지로 변환
                    self.app_icon_image = ImageTk.PhotoImage(image)
                    self.app_icon_label.config(image=self.app_icon_image, text="")
                    
                except Exception as e:
                    logger.warning(f"아이콘 처리 오류: {e}")
                    if self.app_icon_label:
                        self.app_icon_label.config(image="", text="📱")
            else:
                # 기본 아이콘 사용
                if self.app_icon_label:
                    self.app_icon_label.config(image="", text="📱")
                
        except Exception as e:
            logger.error(f"앱 정보 UI 업데이트 오류: {e}")
