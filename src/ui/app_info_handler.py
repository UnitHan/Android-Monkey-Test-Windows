#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 정보 처리 핸들러
main_app.py에서 분리된 앱 정보 관련 기능들
"""
import logging
import threading
import requests
from PIL import Image, ImageTk
from io import BytesIO
from src.utils.app_info_fetcher import AppInfoFetcher

logger = logging.getLogger(__name__)

class AppInfoHandler:
    """앱 정보 처리를 담당하는 핸들러"""
    
    def __init__(self, main_app):
        self.main_app = main_app
        
    def fetch_app_info(self, package_name):
        """앱 정보 가져오기 시작"""
        if not package_name or package_name.strip() == "":
            logger.warning("빈 패키지명으로 앱 정보 조회 시도")
            return
            
        logger.info(f"🔍 앱 정보 조회 시작: {package_name}")
        
        # UI 상태를 로딩 중으로 변경
        self.main_app.app_name_label.config(text="앱 정보를 가져오는 중...", foreground="blue")
        self.main_app.app_developer_label.config(text="로딩 중...")
        self.main_app.app_category_label.config(text="로딩 중...")
        self.main_app.app_version_label.config(text="로딩 중...")
        self.main_app.store_version_label.config(text="로딩 중...")
        self.main_app.update_status_label.config(text="로딩 중...")
        
        # 기존 아이콘 제거
        if hasattr(self.main_app, 'app_icon_label') and self.main_app.app_icon_label:
            self.main_app.app_icon_label.config(image='')
        
        # 백그라운드 스레드에서 앱 정보 가져오기
        thread = threading.Thread(
            target=self._fetch_app_info_thread, 
            args=(package_name,), 
            daemon=True
        )
        thread.start()
        
    def _fetch_app_info_thread(self, package_name):
        """백그라운드에서 앱 정보 가져오기 (버전 정보 포함)"""
        try:
            logger.info(f"📱 앱 정보 조회 시작: {package_name}")
            
            # AppInfoFetcher를 사용하여 Play Store에서 정보 가져오기
            app_info = AppInfoFetcher.get_app_info_from_package(package_name)
            
            # ADB로 버전 정보도 가져오기
            version_info = None
            if self.main_app.adb_client:
                try:
                    version_info = self.main_app.adb_client.get_app_version_info(package_name)
                except Exception as e:
                    logger.warning(f"버전 정보 조회 실패: {e}")
            
            if app_info is None:
                logger.warning(f"⚠️ 앱 정보 조회 실패: {package_name} - Play Store에서 찾을 수 없음")
                app_name = package_name.split('.')[-1].title()
                if len(app_name) < 3:
                    app_name = package_name.replace('.', ' ').title()
                app_info = {
                    'package_name': package_name,
                    'app_name': app_name,
                    'developer': '개발자 정보 없음',
                    'category': '정보 없음',
                    'store_version': '알 수 없음'
                }
            
            # 버전 정보 병합
            if version_info:
                app_info['version_name'] = version_info.get('version_name', '알 수 없음')
                app_info['version_code'] = version_info.get('version_code', '알 수 없음')
            else:
                app_info['version_name'] = '알 수 없음'
                app_info['version_code'] = '알 수 없음'
            
            # 아이콘 다운로드 (백그라운드에서 수행하되 메인 스레드로 UI 업데이트)
            icon_image = None
            if app_info.get('icon_url'):
                self.main_app.after(0, lambda: self.main_app.app_developer_label.config(text="아이콘을 다운로드하는 중..."))
                try:
                    icon_image = self._download_app_icon(app_info['icon_url'])
                except Exception as icon_error:
                    logger.warning(f"아이콘 다운로드 실패: {icon_error}")
                    icon_image = None
            
            # UI 업데이트를 메인 스레드에서 수행 (변수 캡처)
            self.main_app.after(0, lambda info=app_info, img=icon_image: self._update_app_info_ui(info, img))
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ 앱 정보 조회 타임아웃: {package_name}")
            self.main_app.after(0, lambda: self._update_app_info_error(package_name, "요청 시간 초과"))
        except requests.exceptions.RequestException as req_error:
            logger.error(f"❌ 네트워크 오류로 앱 정보 조회 실패: {req_error}")
            self.main_app.after(0, lambda: self._update_app_info_error(package_name, f"네트워크 오류: {req_error}"))
        except Exception as e:
            logger.error(f"❌ 앱 정보 조회 중 예외 발생: {e}")
            logger.exception("앱 정보 조회 상세 오류:")
            self.main_app.after(0, lambda: self._update_app_info_error(package_name, f"조회 오류: {e}"))
    
    def _update_app_info_ui(self, app_info, icon_image=None):
        """앱 정보 UI 업데이트 (메인 스레드에서 호출, 버전 정보 포함)"""
        try:
            app_name = app_info.get('app_name', app_info.get('package_name', 'Unknown'))
            self.main_app.app_name_label.config(text=app_name, foreground="black")
            
            developer = app_info.get('developer', 'Unknown')
            if developer and developer != 'Unknown':
                self.main_app.app_developer_label.config(text=f"개발자: {developer}")
            else:
                self.main_app.app_developer_label.config(text="개발자: 정보 없음")
            
            category = app_info.get('category', 'Unknown')
            if category and category != 'Unknown':
                self.main_app.app_category_label.config(text=f"카테고리: {category}")
            else:
                self.main_app.app_category_label.config(text="카테고리: 정보 없음")
            
            # 디바이스에 설치된 버전 정보 표시
            version_name = app_info.get('version_name', '알 수 없음')
            version_code = app_info.get('version_code', '알 수 없음')
            
            if version_name != '알 수 없음' or version_code != '알 수 없음':
                self.main_app.app_version_label.config(text=f"📱 설치된 버전: v{version_name} ({version_code})")
            else:
                self.main_app.app_version_label.config(text="📱 설치된 버전: 알 수 없음")
            
            # 스토어 버전 정보 표시
            store_version = app_info.get('store_version', app_info.get('current_version', '알 수 없음'))
            if store_version and store_version != '알 수 없음' and store_version != 'Unknown':
                self.main_app.store_version_label.config(text=f"🛒 스토어 최신 버전: {store_version}")
                
                # 버전 비교 (간단한 텍스트 비교)
                if version_name != '알 수 없음' and store_version != version_name:
                    if self._compare_versions(version_name, store_version):
                        self.main_app.update_status_label.config(text="🆙 업데이트 가능", foreground="orange")
                    else:
                        self.main_app.update_status_label.config(text="✅ 최신 버전", foreground="green")
                else:
                    self.main_app.update_status_label.config(text="✅ 최신 버전", foreground="green")
            else:
                self.main_app.store_version_label.config(text="🛒 스토어 버전: 알 수 없음")
                self.main_app.update_status_label.config(text="❓ 업데이트 확인 불가", foreground="gray")
            
            # 아이콘 표시
            if icon_image and hasattr(self.main_app, 'app_icon_label') and self.main_app.app_icon_label:
                self.main_app.app_icon_label.config(image=icon_image)
                self.main_app.app_icon_label.image = icon_image  # 참조 유지
            
            logger.info(f"✅ 앱 정보 UI 업데이트 완료: {app_name}")
            
        except Exception as e:
            logger.error(f"앱 정보 UI 업데이트 실패: {e}")
            logger.exception("앱 정보 UI 업데이트 상세 오류:")
    
    def _download_app_icon(self, icon_url):
        """앱 아이콘 다운로드 (백그라운드에서 호출)"""
        try:
            logger.debug(f"아이콘 다운로드 시작: {icon_url}")
            response = requests.get(icon_url, timeout=10, stream=True)
            response.raise_for_status()
            
            # PIL을 사용하여 이미지 처리
            image = Image.open(BytesIO(response.content))
            image = image.resize((64, 64), Image.Resampling.LANCZOS)
            
            # tkinter용 ImageTk.PhotoImage로 변환
            icon_image = ImageTk.PhotoImage(image)
            
            logger.debug("아이콘 다운로드 및 변환 완료")
            return icon_image
            
        except Exception as e:
            logger.warning(f"아이콘 다운로드 실패: {e}")
            return None
    
    def _update_app_info_error(self, package_name, error_message):
        """앱 정보 로딩 오류 상태 표시"""
        try:
            self.main_app.app_name_label.config(text=package_name or "알 수 없는 앱", foreground="red")
            self.main_app.app_developer_label.config(text=f"오류: {error_message}")
            self.main_app.app_category_label.config(text="정보 없음")
            self.main_app.app_version_label.config(text="버전 정보 없음")
            self.main_app.store_version_label.config(text="스토어 정보 없음")
            self.main_app.update_status_label.config(text="❌ 조회 실패", foreground="red")
            
            if hasattr(self.main_app, 'app_icon_label') and self.main_app.app_icon_label:
                self.main_app.app_icon_label.config(image='')
                
        except Exception as e:
            logger.error(f"앱 정보 오류 표시 실패: {e}")
    
    def _compare_versions(self, current_version, store_version):
        """간단한 버전 비교 (업데이트 필요 여부 반환)"""
        try:
            # 간단한 문자열 비교로 시작
            return current_version != store_version
        except Exception:
            return False