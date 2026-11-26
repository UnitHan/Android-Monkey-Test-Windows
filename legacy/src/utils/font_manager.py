#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
폰트 관리 유틸리티
프로그램 전체에서 사용할 폰트 설정 관리
"""
import os
import sys
import tkinter as tk
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FontManager:
    """폰트 관리 클래스"""
    
    def __init__(self):
        self.fonts_dir = None
        self.korean_font_family = None
        self.korean_font_files = {}
        self._discover_fonts()
    
    def _discover_fonts(self):
        """폰트 파일 발견 및 등록"""
        try:
            # 프로젝트 내 fonts 폴더 찾기
            if getattr(sys, 'frozen', False):
                # EXE 환경 - 여러 경로 시도
                possible_paths = []
                
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller 임시 디렉토리
                    base_dir = getattr(sys, '_MEIPASS')  # type: ignore
                    possible_paths.append(os.path.join(str(base_dir), "fonts"))
                
                # 실행 파일과 같은 폴더
                exe_dir = os.path.dirname(sys.executable)
                possible_paths.extend([
                    os.path.join(exe_dir, "fonts"),
                    os.path.join(exe_dir, "_internal", "fonts"),  # PyInstaller onedir 모드
                ])
                
                # 첫 번째 존재하는 폰트 폴더 사용
                self.fonts_dir = None
                for path in possible_paths:
                    if os.path.exists(path):
                        self.fonts_dir = path
                        break
                
                if not self.fonts_dir:
                    self.fonts_dir = possible_paths[0]  # 기본값으로 첫 번째 경로 사용
                    
            else:
                # 개발 환경
                base_dir = Path(__file__).parent.parent.parent
                self.fonts_dir = os.path.join(str(base_dir), "fonts")
            
            if os.path.exists(self.fonts_dir):
                logger.info(f"폰트 디렉토리 발견: {self.fonts_dir}")
                self._register_fonts()
            else:
                logger.warning(f"폰트 디렉토리를 찾을 수 없습니다: {self.fonts_dir}")
                self._set_fallback_font()
                
        except Exception as e:
            logger.error(f"폰트 발견 중 오류: {e}")
            self._set_fallback_font()
    
    def _register_fonts(self):
        """폰트 파일 등록"""
        try:
            # Noto Sans KR 폰트 파일들 찾기
            noto_files = {
                'regular': '',
                'medium': '',
                'bold': ''
            }
            
            for file_name in os.listdir(self.fonts_dir):
                if file_name.startswith('NotoSansKR') and file_name.endswith(('.otf', '.ttf')):
                    file_path = os.path.join(str(self.fonts_dir), file_name)
                    
                    if 'Regular' in file_name:
                        noto_files['regular'] = file_path
                    elif 'Medium' in file_name:
                        noto_files['medium'] = file_path
                    elif 'Bold' in file_name:
                        noto_files['bold'] = file_path
            
            # 폰트 파일이 있으면 등록
            if any(path for path in noto_files.values() if path):
                self._register_noto_fonts(noto_files)
                self.korean_font_family = "Noto Sans KR"
                logger.info("✅ Noto Sans KR 폰트 등록 완료")
            else:
                logger.warning("Noto Sans KR 폰트 파일을 찾을 수 없습니다.")
                self._set_fallback_font()
                
        except Exception as e:
            logger.error(f"폰트 등록 중 오류: {e}")
            self._set_fallback_font()
    
    def _register_noto_fonts(self, noto_files):
        """Noto Sans KR 폰트 등록"""
        try:
            # Windows에서 폰트 등록
            if os.name == 'nt':
                import ctypes
                from ctypes import wintypes
                
                gdi32 = ctypes.windll.gdi32
                
                for weight, font_path in noto_files.items():
                    if font_path and os.path.exists(font_path):
                        try:
                            # AddFontResourceEx 함수 사용
                            result = gdi32.AddFontResourceExW(
                                ctypes.c_wchar_p(font_path),
                                0x10,  # FR_PRIVATE
                                0
                            )
                            if result:
                                self.korean_font_files[weight] = font_path
                                logger.info(f"폰트 등록 성공: {weight} - {font_path}")
                            else:
                                logger.warning(f"폰트 등록 실패: {weight} - {font_path}")
                        except Exception as e:
                            logger.warning(f"폰트 등록 중 오류 ({weight}): {e}")
            else:
                # Linux/Mac에서는 파일 경로만 저장
                for weight, font_path in noto_files.items():
                    if font_path and os.path.exists(font_path):
                        self.korean_font_files[weight] = font_path
                        logger.info(f"폰트 경로 저장: {weight} - {font_path}")
                        
        except Exception as e:
            logger.error(f"Noto 폰트 등록 중 오류: {e}")
    
    def _set_fallback_font(self):
        """대체 폰트 설정"""
        if os.name == 'nt':  # Windows
            self.korean_font_family = "Malgun Gothic"
        else:  # Linux/Mac
            self.korean_font_family = "DejaVu Sans"
        
        logger.info(f"대체 폰트 사용: {self.korean_font_family}")
    
    def get_font_family(self):
        """한글 폰트 패밀리 이름 반환"""
        return self.korean_font_family or "Noto Sans KR"
    
    def get_font_path(self, weight='regular'):
        """폰트 파일 경로 반환 (matplotlib용)"""
        return self.korean_font_files.get(weight)
    
    def configure_tkinter_fonts(self, root=None):
        """tkinter 기본 폰트 설정"""
        try:
            if not self.korean_font_family:
                return
            
            import tkinter.font as tkFont
            
            # 기본 폰트들 재정의
            default_font = tkFont.nametofont("TkDefaultFont")
            default_font.configure(family=self.korean_font_family)
            
            text_font = tkFont.nametofont("TkTextFont")
            text_font.configure(family=self.korean_font_family)
            
            fixed_font = tkFont.nametofont("TkFixedFont")
            # 고정폭 폰트는 유지하되, 한글이 필요한 경우를 위해 fallback 설정
            
            menu_font = tkFont.nametofont("TkMenuFont")
            menu_font.configure(family=self.korean_font_family)
            
            caption_font = tkFont.nametofont("TkCaptionFont")
            caption_font.configure(family=self.korean_font_family)
            
            small_caption_font = tkFont.nametofont("TkSmallCaptionFont")
            small_caption_font.configure(family=self.korean_font_family)
            
            icon_font = tkFont.nametofont("TkIconFont")
            icon_font.configure(family=self.korean_font_family)
            
            tooltip_font = tkFont.nametofont("TkTooltipFont")
            tooltip_font.configure(family=self.korean_font_family)
            
            logger.info(f"✅ tkinter 기본 폰트 설정 완료: {self.korean_font_family}")
            
        except Exception as e:
            logger.error(f"tkinter 폰트 설정 중 오류: {e}")
    
    def configure_matplotlib_fonts(self):
        """matplotlib 폰트 설정"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
            
            font_path = self.get_font_path('regular')
            
            if font_path and os.path.exists(font_path):
                # 폰트 파일 직접 등록
                fm.fontManager.addfont(font_path)
                
                # 폰트 패밀리 이름 가져오기
                font_prop = fm.FontProperties(fname=font_path)
                font_family = font_prop.get_name()
                
                # matplotlib 설정
                plt.rcParams['font.family'] = font_family
                plt.rcParams['axes.unicode_minus'] = False
                
                logger.info(f"✅ matplotlib 폰트 설정 완료: {font_family}")
            else:
                # 대체 폰트 설정
                if os.name == 'nt':
                    plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans']
                else:
                    plt.rcParams['font.family'] = ['DejaVu Sans']
                
                plt.rcParams['axes.unicode_minus'] = False
                logger.info("matplotlib 대체 폰트 설정 완료")
                
        except ImportError:
            logger.info("matplotlib이 설치되지 않음")
        except Exception as e:
            logger.error(f"matplotlib 폰트 설정 중 오류: {e}")
    
    def apply_all_fonts(self, root=None):
        """모든 폰트 설정 적용"""
        logger.info("🔤 전체 폰트 설정 적용 시작")
        
        self.configure_tkinter_fonts(root)
        self.configure_matplotlib_fonts()
        
        logger.info("✅ 전체 폰트 설정 적용 완료")


# 전역 폰트 매니저 인스턴스
_font_manager = None

def get_font_manager():
    """전역 폰트 매니저 인스턴스 반환"""
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager

def setup_fonts(root=None):
    """폰트 설정 초기화 (메인 앱에서 호출)"""
    font_manager = get_font_manager()
    font_manager.apply_all_fonts(root)
    return font_manager

def get_korean_font_family():
    """한글 폰트 패밀리 이름 반환"""
    return get_font_manager().get_font_family()

def get_korean_font_path(weight='regular'):
    """한글 폰트 파일 경로 반환"""
    return get_font_manager().get_font_path(weight)


if __name__ == "__main__":
    # 테스트 실행
    print("폰트 매니저 테스트...")
    
    font_manager = FontManager()
    print(f"한글 폰트 패밀리: {font_manager.get_font_family()}")
    print(f"Regular 폰트 경로: {font_manager.get_font_path('regular')}")
    print(f"Bold 폰트 경로: {font_manager.get_font_path('bold')}")
    
    # matplotlib 설정 테스트
    font_manager.configure_matplotlib_fonts()
    print("matplotlib 폰트 설정 완료")
