#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 검색 상태 관리 클래스
빠른 검색을 위한 인덱싱 및 캐싱 기능
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import threading

logger = logging.getLogger(__name__)

class AppSearchManager:
    """앱 검색을 위한 상태 관리 클래스"""
    
    def __init__(self):
        self.apps_data = {}  # JSON 데이터
        self.installed_packages = set()  # 실제 설치된 패키지 목록
        self.search_index = {}  # 검색 인덱스 (키워드 -> 패키지명들)
        self.display_names = {}  # 패키지명 -> 표시명 매핑
        self.loaded = False
        self._lock = threading.Lock()
        
        self.load_apps_data()
    
    def load_apps_data(self):
        """apps.json 파일 로드 및 인덱스 구축"""
        try:
            # apps.json 파일 경로 찾기
            json_paths = self._get_json_paths()
            
            apps_json_path = None
            for path in json_paths:
                if path.exists():
                    apps_json_path = path
                    break
            
            if apps_json_path:
                with open(apps_json_path, 'r', encoding='utf-8') as f:
                    self.apps_data = json.load(f)
                logger.info(f"✅ 앱 정보 로드 완료: {len(self.apps_data)}개 앱 ({apps_json_path})")
                self._build_search_index()
                self.loaded = True
            else:
                logger.warning(f"❌ apps.json 파일을 찾을 수 없습니다. 시도한 경로: {[str(p) for p in json_paths]}")
                self.loaded = False
                
        except Exception as e:
            logger.error(f"❌ apps.json 로드 실패: {e}")
            self.loaded = False
    
    def _get_json_paths(self) -> List[Path]:
        """가능한 apps.json 파일 경로들 반환"""
        import sys
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
                Path.cwd() / "apps.json",
                project_root / "apps.json",
            ])
        
        # 절대 경로도 시도
        json_paths.extend([
            Path("C:/monkey/apps.json"),
            Path("C:/monkey/github_repo/apps.json"),
        ])
        
        return json_paths
    
    def _build_search_index(self):
        """검색 인덱스 구축 (키워드별로 패키지명들 매핑)"""
        logger.info("🔍 검색 인덱스 구축 시작...")
        
        self.search_index.clear()
        self.display_names.clear()
        
        for package_name, app_info in self.apps_data.items():
            # 앱 이름 추출
            app_name = self._get_app_name(app_info)
            
            # 표시명 생성
            if app_name and app_name.strip():
                display_name = f"{app_name.strip()} ({package_name})"
            else:
                display_name = package_name
            
            self.display_names[package_name] = display_name
            
            # 검색 키워드들 수집
            search_terms = set()
            
            # 1. 패키지명의 각 부분 (점으로 분리)
            for part in package_name.lower().split('.'):
                if part:
                    search_terms.add(part)
                    # 부분 문자열도 추가 (2글자 이상)
                    for i in range(len(part)):
                        for j in range(i + 1, len(part) + 1):
                            if j - i >= 1:  # 1글자부터 인덱싱
                                search_terms.add(part[i:j])
            
            # 2. 앱 이름
            if app_name and app_name.strip():
                app_name_clean = app_name.strip().lower()
                search_terms.add(app_name_clean)
                
                # 한글/영문 단어별로 분리
                words = self._extract_words(app_name_clean)
                for word in words:
                    if word:
                        search_terms.add(word)
                        # 부분 문자열도 추가 (1글자부터)
                        for i in range(len(word)):
                            for j in range(i + 1, len(word) + 1):
                                if j - i >= 1:  # 1글자부터 인덱싱
                                    search_terms.add(word[i:j])
            
            # 3. keywords 배열
            if 'keywords' in app_info and isinstance(app_info['keywords'], list):
                for keyword in app_info['keywords']:
                    if keyword and str(keyword).strip():
                        keyword_clean = str(keyword).strip().lower()
                        search_terms.add(keyword_clean)
                        
                        # 키워드도 부분 문자열 인덱싱 (1글자부터)
                        for i in range(len(keyword_clean)):
                            for j in range(i + 1, len(keyword_clean) + 1):
                                if j - i >= 1:
                                    search_terms.add(keyword_clean[i:j])
            
            # 인덱스에 추가
            for term in search_terms:
                if term not in self.search_index:
                    self.search_index[term] = set()
                self.search_index[term].add(package_name)
        
        logger.info(f"✅ 검색 인덱스 구축 완료: {len(self.search_index)}개 키워드")
    
    def _extract_words(self, text: str) -> List[str]:
        """텍스트에서 한글/영문 단어들 추출"""
        import re
        
        # 한글, 영문, 숫자만 추출
        words = []
        
        # 공백으로 분리된 단어들
        space_words = text.split()
        for word in space_words:
            if word:
                words.append(word)
        
        # 특수문자로 분리된 단어들도 추출
        parts = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', text)
        words.extend(parts)
        
        return list(set(words))  # 중복 제거
    
    def _get_app_name(self, app_info: dict) -> Optional[str]:
        """앱 정보에서 앱 이름 추출"""
        if not isinstance(app_info, dict):
            return None
            
        # 우선순위: app_name -> name -> display_name -> title -> label
        name_keys = ['app_name', 'name', 'display_name', 'title', 'label']
        
        for key in name_keys:
            if key in app_info and app_info[key]:
                name = str(app_info[key]).strip()
                if name and name != "Unknown":
                    return name
        
        # keywords에서 첫 번째 키워드를 이름으로 간주
        if 'keywords' in app_info and isinstance(app_info['keywords'], list) and app_info['keywords']:
            first_keyword = str(app_info['keywords'][0]).strip()
            if first_keyword and first_keyword != "Unknown":
                return first_keyword
        
        return None
    
    def set_installed_packages(self, packages: List[str]):
        """설치된 패키지 목록 설정"""
        with self._lock:
            self.installed_packages = set(packages)
            logger.info(f"✅ 설치된 패키지 목록 업데이트: {len(packages)}개")
    
    def search(self, query: str, limit: int = 100) -> List[Tuple[str, str]]:
        """앱 검색 수행
        
        Args:
            query: 검색어 (1글자부터 가능)
            limit: 결과 개수 제한
            
        Returns:
            List[Tuple[str, str]]: (표시명, 패키지명) 튜플 리스트
        """
        if not self.loaded or not query or not query.strip():
            return self._get_all_installed_apps(limit)
        
        query_clean = query.strip().lower()
        
        # 검색 결과 수집
        found_packages = set()
        
        # 1. 정확한 키워드 매치
        if query_clean in self.search_index:
            found_packages.update(self.search_index[query_clean])
        
        # 2. 부분 매치 (키워드에 검색어가 포함된 경우)
        for keyword in self.search_index:
            if query_clean in keyword:
                found_packages.update(self.search_index[keyword])
        
        # 3. 설치된 패키지만 필터링
        installed_matches = []
        for package in found_packages:
            if package in self.installed_packages:
                display_name = self.display_names.get(package, package)
                installed_matches.append((display_name, package))
        
        # 4. 우선순위 정렬
        def sort_key(item):
            display_name, package = item
            app_name = self._get_app_name(self.apps_data.get(package, {})) or ""
            
            # 정확한 매치 우선
            if app_name.lower() == query_clean:
                return (0, app_name.lower())
            elif package.lower() == query_clean:
                return (1, package.lower())
            elif app_name.lower().startswith(query_clean):
                return (2, app_name.lower())
            elif package.lower().startswith(query_clean):
                return (3, package.lower())
            elif query_clean in app_name.lower():
                return (4, app_name.lower())
            elif query_clean in package.lower():
                return (5, package.lower())
            else:
                return (6, display_name.lower())
        
        installed_matches.sort(key=sort_key)
        return installed_matches[:limit]
    
    def _get_all_installed_apps(self, limit: int) -> List[Tuple[str, str]]:
        """설치된 모든 앱 반환 (인기 앱 우선)"""
        # 인기 앱 패키지명 (자주 테스트되는 앱들)
        popular_packages = [
            'com.android.chrome',
            'com.kakao.talk',
            'com.google.android.apps.photos',
            'com.samsung.android.messaging',
            'com.android.settings',
            'com.google.android.googlequicksearchbox',
            'com.android.vending',
            'com.google.android.apps.maps',
            'com.netflix.mediaclient',
            'com.lguplus.aicallagent',
            'com.naver.vibe',
            'com.samsung.android.calendar',
            'com.samsung.android.video',
        ]
        
        results = []
        added = set()
        
        # 먼저 인기 앱들 추가
        for package in popular_packages:
            if package in self.installed_packages and package not in added:
                display_name = self.display_names.get(package, package)
                results.append((display_name, package))
                added.add(package)
                if len(results) >= limit:
                    break
        
        # 나머지 설치된 앱들 추가
        for package in sorted(self.installed_packages):
            if package not in added:
                display_name = self.display_names.get(package, package)
                results.append((display_name, package))
                added.add(package)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_display_name(self, package_name: str) -> str:
        """패키지명에 대한 표시명 반환"""
        return self.display_names.get(package_name, package_name)

# 전역 검색 관리자 인스턴스
_app_search_manager = None

def get_app_search_manager() -> AppSearchManager:
    """앱 검색 관리자 싱글톤 인스턴스 반환"""
    global _app_search_manager
    if _app_search_manager is None:
        _app_search_manager = AppSearchManager()
    return _app_search_manager
