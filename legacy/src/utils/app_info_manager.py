#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 정보 관리 유틸리티
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class AppInfoManager:
    """앱 정보 관리 클래스"""
    
    def __init__(self):
        self.apps_data = {}
        self.load_apps_json()
    
    def load_apps_json(self):
        """apps.json 파일 로드"""
        try:
            import sys
            # apps.json 파일 경로 찾기
            json_paths = []
            
            if getattr(sys, 'frozen', False):
                # EXE 환경
                exe_dir = Path(sys.executable).parent
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller 임시 디렉토리
                    temp_dir = Path(getattr(sys, '_MEIPASS'))
                    json_paths.extend([
                        temp_dir / "apps.json",
                        exe_dir / "apps.json",
                        exe_dir / "_internal" / "apps.json",
                    ])
                else:
                    json_paths.append(exe_dir / "apps.json")
            else:
                # 개발 환경
                project_root = Path(__file__).parent.parent.parent
                json_paths.extend([
                    Path.cwd() / "apps.json",  # 현재 작업 디렉토리
                    project_root / "apps.json",  # 프로젝트 루트
                ])
            
            # 절대 경로도 시도
            json_paths.extend([
                Path("C:/monkey/apps.json"),
                Path("C:/monkey/github_repo/apps.json"),
            ])
            
            apps_json_path = None
            for path in json_paths:
                if path.exists():
                    apps_json_path = path
                    break
            
            if apps_json_path:
                with open(apps_json_path, 'r', encoding='utf-8') as f:
                    self.apps_data = json.load(f)
                logger.info(f"앱 정보 로드 완료: {len(self.apps_data)}개 앱 ({apps_json_path})")
            else:
                logger.warning(f"apps.json 파일을 찾을 수 없습니다. 시도한 경로: {[str(p) for p in json_paths]}")
                self.apps_data = {}
                
        except Exception as e:
            logger.error(f"apps.json 로드 실패: {e}")
            self.apps_data = {}
    
    def get_app_display_name(self, package_name: str) -> str:
        """패키지명에 대한 표시용 이름 반환"""
        if package_name in self.apps_data:
            app_info = self.apps_data[package_name]
            
            # 앱 이름 찾기 (여러 키워드 확인)
            app_name = None
            name_keys = ['name', 'app_name', 'display_name', 'title', 'label']
            
            for key in name_keys:
                if key in app_info and app_info[key]:
                    app_name = str(app_info[key]).strip()
                    break
            
            # keywords에서 앱 이름 찾기 (첫 번째 키워드를 이름으로 간주)
            if not app_name and 'keywords' in app_info and app_info['keywords']:
                if isinstance(app_info['keywords'], list) and app_info['keywords']:
                    app_name = str(app_info['keywords'][0]).strip()
            
            if app_name:
                return f"{app_name} ({package_name})"
        
        # 앱 이름이 없으면 패키지명만 반환
        return package_name
    
    def get_app_name_only(self, package_name: str) -> Optional[str]:
        """패키지명에 대한 앱 이름만 반환 (없으면 None)"""
        if package_name in self.apps_data:
            app_info = self.apps_data[package_name]
            
            # 앱 이름 찾기
            name_keys = ['name', 'app_name', 'display_name', 'title', 'label']
            
            for key in name_keys:
                if key in app_info and app_info[key]:
                    return str(app_info[key]).strip()
            
            # keywords에서 앱 이름 찾기
            if 'keywords' in app_info and app_info['keywords']:
                if isinstance(app_info['keywords'], list) and app_info['keywords']:
                    return str(app_info['keywords'][0]).strip()
        
        return None
    
    def search_apps(self, query: str, package_list: List[str]) -> List[Tuple[str, str]]:
        """앱 검색 (앱 이름과 패키지명 모두 검색)
        
        Returns:
            List[Tuple[str, str]]: (표시명, 패키지명) 튜플 리스트
        """
        if not query:
            # 검색어가 없으면 모든 앱 반환
            results = []
            for package in package_list:
                display_name = self.get_app_display_name(package)
                results.append((display_name, package))
            return results
        
        query_lower = query.lower().strip()
        results = []
        
        for package in package_list:
            display_name = self.get_app_display_name(package)
            app_name = self.get_app_name_only(package)
            
            # 검색 조건 확인
            match = False
            
            # 1. 패키지명에서 검색 (대소문자 구분 안함)
            if query_lower in package.lower():
                match = True
            
            # 2. 앱 이름에서 검색 (대소문자 구분 안함)
            if app_name and query_lower in app_name.lower():
                match = True
            
            # 3. 표시명에서 검색 (앱 이름 + 패키지명 조합)
            if query_lower in display_name.lower():
                match = True
            
            # 4. keywords에서 검색
            if package in self.apps_data:
                app_info = self.apps_data[package]
                if 'keywords' in app_info and app_info['keywords']:
                    if isinstance(app_info['keywords'], list):
                        for keyword in app_info['keywords']:
                            if keyword and query_lower in str(keyword).lower():
                                match = True
                                break
            
            if match:
                results.append((display_name, package))
        
        # 정확한 매치를 우선순위로 정렬
        def sort_key(item):
            display_name, package = item
            app_name = self.get_app_name_only(package) or ""
            
            # 정확한 매치 우선순위 (숫자가 낮을수록 우선)
            if app_name.lower() == query_lower:
                return (0, app_name.lower())
            elif package.lower() == query_lower:
                return (1, package.lower())
            elif app_name.lower().startswith(query_lower):
                return (2, app_name.lower())
            elif package.lower().startswith(query_lower):
                return (3, package.lower())
            elif query_lower in app_name.lower():
                return (4, app_name.lower())
            elif query_lower in package.lower():
                return (5, package.lower())
            else:
                return (6, display_name.lower())
        
        results.sort(key=sort_key)
        return results
    
    def get_popular_apps(self, package_list: List[str], limit: int = 20) -> List[Tuple[str, str]]:
        """인기 앱 목록 반환 (자주 사용되는 앱들 우선)"""
        # 인기 앱 패키지명 목록 (일반적으로 테스트에 많이 사용되는 앱들)
        popular_packages = [
            'com.android.chrome',
            'com.kakao.talk', 
            'com.google.android.apps.photos',
            'com.google.android.gms',
            'com.samsung.android.messaging',
            'com.android.settings',
            'com.google.android.googlequicksearchbox',
            'com.android.vending',
            'com.google.android.apps.maps',
            'com.netflix.mediaclient',
            'com.google.android.youtube',
            'com.facebook.katana',
            'com.instagram.android',
            'com.whatsapp',
            'com.lguplus.aicallagent',
        ]
        
        results = []
        added_packages = set()
        
        # 먼저 인기 앱들 추가
        for package in popular_packages:
            if package in package_list and package not in added_packages:
                display_name = self.get_app_display_name(package)
                results.append((display_name, package))
                added_packages.add(package)
                if len(results) >= limit:
                    break
        
        # 남은 자리에 다른 앱들 추가
        for package in package_list:
            if package not in added_packages:
                display_name = self.get_app_display_name(package)
                results.append((display_name, package))
                added_packages.add(package)
                if len(results) >= limit:
                    break
        
        return results

# 전역 앱 정보 관리자 인스턴스
_app_info_manager = None

def get_app_info_manager() -> AppInfoManager:
    """앱 정보 관리자 싱글톤 인스턴스 반환"""
    global _app_info_manager
    if _app_info_manager is None:
        _app_info_manager = AppInfoManager()
    return _app_info_manager
