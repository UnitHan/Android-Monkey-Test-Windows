#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android Monkey 테스트 자동화 프로그램 v3.0
"""
import sys
import os
import logging
from pathlib import Path

# EXE 모드에서 콘솔 출력 억제
if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 EXE 모드
    import io
    
    # stdout/stderr를 null로 리다이렉트 (콘솔 창 방지)
    class NullWriter:
        def write(self, *args, **kwargs):
            pass
        def flush(self, *args, **kwargs):
            pass
        def close(self, *args, **kwargs):
            pass
    
    # 심각한 오류만 표시하고 나머지는 억제
    original_stderr = sys.stderr
    sys.stdout = NullWriter()
    # stderr는 중요한 오류를 위해 유지하되, 필요시 억제 가능
    # sys.stderr = NullWriter()

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ui.main_app import MonkeyTestApp
from src.utils.logger import setup_logger
from src.utils.font_manager import setup_fonts

# EXE 모드에서는 로거 레벨을 더 높게 설정
logger = setup_logger(__name__)
if getattr(sys, 'frozen', False):
    # EXE 모드에서는 WARNING 이상만 표시
    logger.setLevel(logging.WARNING)
    # 루트 로거도 WARNING으로 설정
    logging.getLogger().setLevel(logging.WARNING)

def main():
    """메인 함수"""
    try:
        # EXE 모드에서는 시작 로그 억제
        if not getattr(sys, 'frozen', False):
            logger.info("Monkey 테스트 자동화 프로그램 v3.0 시작")
        
        # 메인 앱 생성 (폰트 초기화는 앱 내부에서 처리)
        app = MonkeyTestApp()
        
        # 안전한 종료를 위한 signal 핸들러 설정 (EXE 모드에서만)
        if getattr(sys, 'frozen', False):
            import signal
            import atexit
            
            def safe_exit_handler(*args):
                """안전한 종료 핸들러"""
                try:
                    if hasattr(app, 'on_closing'):
                        app.on_closing()
                except:
                    pass
                # 정상 종료 시도
                try:
                    app.quit()
                except:
                    pass
                try:
                    app.destroy()
                except:
                    pass
            
            # SIGTERM, SIGINT 핸들러 등록
            try:
                signal.signal(signal.SIGTERM, safe_exit_handler)
                signal.signal(signal.SIGINT, safe_exit_handler)
            except (ValueError, OSError):
                pass  # 일부 환경에서는 signal 설정이 불가능
            
            # atexit 핸들러도 등록
            atexit.register(safe_exit_handler)
        
        # 메인루프 실행
        app.mainloop()
        
    except Exception as e:
        # EXE 모드에서는 오류 다이얼로그 억제, 개발 모드에서만 표시
        if getattr(sys, 'frozen', False):
            # EXE 모드: 조용히 종료 (팝업 억제)
            pass
        else:
            # 개발 모드: 로그와 콘솔 출력 모두
            logger.error(f"프로그램 실행 중 오류: {e}")
            try:
                from src.utils.gui_utils import messagebox
                messagebox.showerror("오류", f"프로그램 실행 중 오류가 발생했습니다: {e}")
            except:
                print(f"치명적 오류: {e}")
    finally:
        # 최종 정리
        try:
            if getattr(sys, 'frozen', False):
                # EXE 모드에서는 간단하게 종료
                pass
            else:
                # 개발 모드에서는 정상 종료
                logger.info("Monkey 테스트 자동화 프로그램 종료")
        except:
            pass

if __name__ == "__main__":
    main()
