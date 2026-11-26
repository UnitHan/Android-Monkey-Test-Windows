"""
Windows subprocess 콘솔 창 숨김 유틸리티
EXE 모드에서 subprocess 호출 시 CMD 창이 나타나지 않도록 하는 공통 함수
"""
import subprocess
import sys
import os

def get_subprocess_startupinfo():
    """
    Windows에서 subprocess 호출 시 콘솔 창을 숨기기 위한 startupinfo 반환
    EXE 모드에서만 적용
    """
    startupinfo = None
    creationflags = 0
    
    # EXE 모드이고 Windows인 경우에만 콘솔 창 숨김
    if getattr(sys, 'frozen', False) and os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        # CREATE_NO_WINDOW 플래그 추가 (더 강력한 창 숨김)
        creationflags = subprocess.CREATE_NO_WINDOW
    
    return startupinfo, creationflags

def run_hidden_subprocess(*args, **kwargs):
    """
    콘솔 창을 숨기고 subprocess.run 실행
    """
    startupinfo, creationflags = get_subprocess_startupinfo()
    if startupinfo is not None:
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = creationflags
    
    return subprocess.run(*args, **kwargs)

def popen_hidden_subprocess(*args, **kwargs):
    """
    콘솔 창을 숨기고 subprocess.Popen 실행
    """
    startupinfo, creationflags = get_subprocess_startupinfo()
    if startupinfo is not None:
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = creationflags
    
    return subprocess.Popen(*args, **kwargs)

def call_hidden_subprocess(*args, **kwargs):
    """
    콘솔 창을 숨기고 subprocess.call 실행
    """
    startupinfo, creationflags = get_subprocess_startupinfo()
    if startupinfo is not None:
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = creationflags
    
    return subprocess.call(*args, **kwargs)

def check_output_hidden(*args, **kwargs):
    """
    콘솔 창을 숨기고 subprocess.check_output 실행
    """
    startupinfo, creationflags = get_subprocess_startupinfo()
    if startupinfo is not None:
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = creationflags
    
    return subprocess.check_output(*args, **kwargs)
