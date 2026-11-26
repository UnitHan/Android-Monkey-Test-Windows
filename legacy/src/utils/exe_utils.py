#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE 빌드 시 리소스 파일 접근을 위한 유틸리티
"""
import os
import sys
from pathlib import Path

def get_resource_path(relative_path):
    """리소스 파일의 절대 경로를 반환 (EXE 환경 고려)"""
    try:
        # PyInstaller 임시 폴더
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
    except Exception:
        pass
    
    # 개발 환경 또는 일반 실행
    return os.path.join(os.path.abspath("."), relative_path)

def is_exe_environment():
    """EXE 환경에서 실행 중인지 확인"""
    return getattr(sys, 'frozen', False)

def get_exe_directory():
    """EXE 파일이 위치한 디렉토리 반환"""
    if is_exe_environment():
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def ensure_directory_exists(directory_path):
    """디렉토리가 존재하는지 확인하고 없으면 생성"""
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except (PermissionError, OSError) as e:
        print(f"디렉토리 생성 실패: {directory_path} - {e}")
        return False

def check_file_permissions(file_path):
    """파일 권한 확인"""
    try:
        # 읽기 권한 확인
        if os.access(file_path, os.R_OK):
            return True
        else:
            print(f"파일 읽기 권한 없음: {file_path}")
            return False
    except Exception as e:
        print(f"파일 권한 확인 실패: {file_path} - {e}")
        return False

def get_safe_temp_directory():
    """안전하게 사용할 수 있는 임시 디렉토리 반환"""
    import tempfile
    
    temp_dirs = [
        Path.home() / "AppData" / "Local" / "MonkeyTest",
        Path.home() / "Documents" / "MonkeyTest", 
        Path(tempfile.gettempdir()) / "MonkeyTest"
    ]
    
    for temp_dir in temp_dirs:
        if ensure_directory_exists(temp_dir):
            try:
                # 쓰기 테스트
                test_file = temp_dir / "write_test.tmp"
                test_file.write_text("test")
                test_file.unlink()
                return temp_dir
            except Exception:
                continue
    
    # 최후의 수단
    return Path(tempfile.gettempdir())
