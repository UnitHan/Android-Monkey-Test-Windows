#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
사용자 정의 폰트 설정
Arial을 Noto Sans KR로 직접 대체
"""
import os
import sys
import logging
import tkinter as tk
import tkinter.font as tkFont

logger = logging.getLogger(__name__)

def setup_noto_sans_kr_fonts():
    """Noto Sans KR 폰트를 등록하고 기본 폰트로 설정"""
    try:
        # 폰트 디렉토리 찾기 (여러 경로 시도)
        font_paths_to_try = []
        
        if getattr(sys, 'frozen', False):
            # EXE 환경에서 여러 경로 시도
            if hasattr(sys, '_MEIPASS'):
                font_paths_to_try.append(os.path.join(getattr(sys, '_MEIPASS'), "fonts"))
            
            exe_dir = os.path.dirname(sys.executable)
            font_paths_to_try.extend([
                os.path.join(exe_dir, "fonts"),
                os.path.join(exe_dir, "_internal", "fonts"),
                os.path.join(exe_dir, "..", "fonts")  # 상위 디렉토리도 확인
            ])
        else:
            # 개발 환경
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            font_paths_to_try.append(os.path.join(base_dir, "fonts"))
        
        fonts_dir = None
        for path in font_paths_to_try:
            if os.path.exists(path):
                fonts_dir = path
                logger.info(f"폰트 디렉토리 발견: {fonts_dir}")
                break
        
        if not os.path.exists(fonts_dir):
            logger.warning(f"폰트 디렉토리를 찾을 수 없습니다: {fonts_dir}")
            return False
        
        # OTF 파일들 찾기
        noto_files = []
        for file_name in os.listdir(fonts_dir):
            if file_name.startswith('NotoSansKR') and file_name.endswith('.otf'):
                file_path = os.path.join(fonts_dir, file_name)
                noto_files.append(file_path)
        
        if not noto_files:
            logger.warning("Noto Sans KR OTF 파일을 찾을 수 없습니다.")
            return False
        
        # Windows에서 폰트 등록
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            
            gdi32 = ctypes.windll.gdi32
            success_count = 0
            
            for font_path in noto_files:
                try:
                    result = gdi32.AddFontResourceExW(
                        ctypes.c_wchar_p(font_path),
                        0x10,  # FR_PRIVATE
                        0
                    )
                    if result:
                        success_count += 1
                        logger.info(f"폰트 등록 성공: {font_path}")
                    else:
                        logger.warning(f"폰트 등록 실패: {font_path}")
                except Exception as e:
                    logger.warning(f"폰트 등록 중 오류: {e}")
            
            if success_count > 0:
                logger.info(f"✅ {success_count}개 Noto Sans KR 폰트 등록 완료")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"폰트 설정 중 오류: {e}")
        return False

def apply_noto_sans_kr_as_default(root=None):
    """Noto Sans KR을 기본 폰트로 설정"""
    try:
        # tkinter 기본 폰트들을 Noto Sans KR로 변경
        font_names = [
            "TkDefaultFont",
            "TkTextFont", 
            "TkMenuFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont"
        ]
        
        for font_name in font_names:
            try:
                font = tkFont.nametofont(font_name)
                font.configure(family="Noto Sans KR")
                logger.debug(f"폰트 변경: {font_name} -> Noto Sans KR")
            except Exception as e:
                logger.warning(f"폰트 {font_name} 변경 실패: {e}")
        
        logger.info("✅ tkinter 기본 폰트를 Noto Sans KR로 변경 완료")
        return True
        
    except Exception as e:
        logger.error(f"기본 폰트 설정 중 오류: {e}")
        return False

def replace_arial_with_noto_sans_kr():
    """전체 시스템에서 Arial을 Noto Sans KR로 대체"""
    success = False
    
    # 1. 폰트 등록
    if setup_noto_sans_kr_fonts():
        logger.info("Noto Sans KR 폰트 등록 성공")
        success = True
    
    # 2. 기본 폰트 설정
    if apply_noto_sans_kr_as_default():
        logger.info("기본 폰트 Noto Sans KR 설정 성공")
        success = True
    
    return success

if __name__ == "__main__":
    # 테스트 실행
    print("Noto Sans KR 폰트 설정 테스트...")
    
    root = tk.Tk()
    root.withdraw()  # 창 숨김
    
    success = replace_arial_with_noto_sans_kr()
    
    if success:
        print("✅ 폰트 설정 성공")
        
        # 테스트 창 생성
        test_window = tk.Toplevel()
        test_window.title("폰트 테스트")
        test_window.geometry("400x300")
        
        # 다양한 폰트 크기로 테스트
        tk.Label(test_window, text="Noto Sans KR 32pt", font=("Noto Sans KR", 32)).pack(pady=5)
        tk.Label(test_window, text="Noto Sans KR 14pt Bold", font=("Noto Sans KR", 14, "bold")).pack(pady=5)
        tk.Label(test_window, text="Noto Sans KR 10pt", font=("Noto Sans KR", 10)).pack(pady=5)
        tk.Label(test_window, text="Noto Sans KR 8pt", font=("Noto Sans KR", 8)).pack(pady=5)
        
        # 기본 폰트 테스트
        tk.Label(test_window, text="기본 폰트 (변경된 상태)", font=("TkDefaultFont",)).pack(pady=5)
        
        test_window.mainloop()
    else:
        print("❌ 폰트 설정 실패")
    
    root.destroy()
