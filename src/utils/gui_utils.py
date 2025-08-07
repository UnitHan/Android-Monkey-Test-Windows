# -*- coding: utf-8 -*-
"""
GUI 유틸리티 - EXE 모드에서 팝업 억제
"""
import sys
from tkinter import messagebox as original_messagebox

def is_exe_mode():
    """EXE 모드 여부 확인"""
    return getattr(sys, 'frozen', False)

class SafeMessageBox:
    """EXE 모드에서 팝업을 억제하는 messagebox 래퍼"""
    
    @staticmethod
    def showerror(title, message):
        """에러 다이얼로그 - EXE 모드에서는 억제"""
        if not is_exe_mode():
            return original_messagebox.showerror(title, message)
        return None
    
    @staticmethod
    def showwarning(title, message):
        """경고 다이얼로그 - EXE 모드에서는 억제"""
        if not is_exe_mode():
            return original_messagebox.showwarning(title, message)
        return None
    
    @staticmethod
    def showinfo(title, message):
        """정보 다이얼로그 - EXE 모드에서는 억제"""
        if not is_exe_mode():
            return original_messagebox.showinfo(title, message)
        return None
    
    @staticmethod
    def askyesno(title, message):
        """예/아니오 다이얼로그 - EXE 모드에서는 기본값 반환"""
        if not is_exe_mode():
            return original_messagebox.askyesno(title, message)
        # EXE 모드에서는 기본적으로 'No' 반환 (안전한 선택)
        return False
    
    @staticmethod
    def askokcancel(title, message):
        """확인/취소 다이얼로그 - EXE 모드에서는 기본값 반환"""
        if not is_exe_mode():
            return original_messagebox.askokcancel(title, message)
        # EXE 모드에서는 기본적으로 'Cancel' 반환 (안전한 선택)
        return False
    
    @staticmethod
    def askretrycancel(title, message):
        """재시도/취소 다이얼로그 - EXE 모드에서는 기본값 반환"""
        if not is_exe_mode():
            return original_messagebox.askretrycancel(title, message)
        # EXE 모드에서는 기본적으로 'Cancel' 반환 (안전한 선택)
        return False
    
    @staticmethod
    def askyesnocancel(title, message):
        """예/아니오/취소 다이얼로그 - EXE 모드에서는 기본값 반환"""
        if not is_exe_mode():
            return original_messagebox.askyesnocancel(title, message)
        # EXE 모드에서는 기본적으로 None 반환 (취소)
        return None

# 편의를 위한 별칭
messagebox = SafeMessageBox
