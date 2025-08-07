#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey 테스트 자동화 도구 빌드 스크립트
"""
import os
import shutil
import requests
import zipfile
import platform
from pathlib import Path

def download_adb_tools():
    """ADB 도구 다운로드"""
    print("ADB 도구 다운로드 중...")
    
    # 운영체제에 따른 ADB 다운로드 URL
    if platform.system() == "Windows":
        adb_url = "https://dl.google.com/android/repository/platform-tools_r34.0.5-windows.zip"
        folder_name = "platform-tools"
    else:
        print("현재 Windows만 지원됩니다.")
        return False
    
    # adb_tools 디렉토리 생성
    adb_dir = Path("adb_tools")
    adb_dir.mkdir(exist_ok=True)
    
    # 이미 다운로드되어 있으면 스킵
    if (adb_dir / folder_name / "adb.exe").exists():
        print("ADB 도구가 이미 존재합니다.")
        return True
    
    try:
        # ADB 도구 다운로드
        print(f"다운로드 중: {adb_url}")
        response = requests.get(adb_url, stream=True)
        response.raise_for_status()
        
        zip_path = adb_dir / "platform-tools.zip"
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 압축 해제
        print("압축 해제 중...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(adb_dir)
        
        # 압축 파일 삭제
        zip_path.unlink()
        
        print("ADB 도구 다운로드 완료!")
        return True
        
    except Exception as e:
        print(f"ADB 도구 다운로드 실패: {e}")
        return False

def prepare_build():
    """빌드 준비"""
    print("빌드 준비 중...")
    
    # ADB 도구 다운로드
    if not download_adb_tools():
        return False
    
    # 빌드에 필요한 디렉토리 생성
    build_dirs = ["dist", "build"]
    for dir_name in build_dirs:
        Path(dir_name).mkdir(exist_ok=True)
    
    print("빌드 준비 완료!")
    return True

if __name__ == "__main__":
    prepare_build()
